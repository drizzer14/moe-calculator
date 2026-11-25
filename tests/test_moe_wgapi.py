# -*- coding: utf-8 -*-
"""Tests for the pure logic of the WG-API MoE provider + the garage roster.

The engine-facing fetch/poll/persist code is exercised in-client; here we cover the pieces
that need no game engine:
  - moe_wgapi.parse_response  : WG /tanks/mastery JSON -> {int_cd: {percentile: dmg}}
  - moe_wgapi.fresh_table     : per-day cache envelope validity (fresh adopts / stale drops),
                                INCLUDING the v3->v4 re-key guard
  - garage_roster.rank_by_recency : top-N owned intCDs by last-battle time (most recent first)
"""
import json

import pytest

from moe_calculator.adapter import moe_wgapi
from moe_calculator.adapter import garage_roster


# --- parse_response ----------------------------------------------------------
# The table is keyed by PERCENTILE, not by mark count: WG stores 8 anchors and we request all
# of them. 65/85/95/100 are REQUIRED (a row missing any of them is dropped whole); 20/40/55/75
# are optional enrichment that sharpens the in-battle interpolator's low end.

_OK = {
    "status": "ok",
    "data": {
        "distribution": {
            "69153": {"65": 2544, "85": 3634, "95": 4512, "100": 5229},
            "1": {"65": 709, "85": 1064, "95": 1367, "100": 1500},
        },
        "updated_at": 1783468800,
    },
}

# A full 8-anchor row -- the live EU table for int_cd 54657 (see test_battle_builder's
# back-test regression pins).
_EIGHT = {20: 528, 40: 1163, 55: 1549, 65: 1799, 75: 2104, 85: 2494, 95: 3042, 100: 3482}


def _dist(row, tid="54657", updated_at=1783468800):
    return json.dumps({"status": "ok", "data": {
        "distribution": {tid: dict((str(k), v) for k, v in row.items())},
        "updated_at": updated_at}})


def test_parse_response_keys_the_row_by_percentile():
    # NOT by mark count: the row's keys ARE WG's percentile values, so nothing is remapped on
    # the way in (the v4 store re-key).
    table, updated_at = moe_wgapi.parse_response(json.dumps(_OK))
    assert table[69153] == {65: 2544, 85: 3634, 95: 4512, 100: 5229}
    assert table[1] == {65: 709, 85: 1064, 95: 1367, 100: 1500}
    assert updated_at == 1783468800


def test_parse_response_keeps_all_eight_anchors_when_present():
    table, _ = moe_wgapi.parse_response(_dist(_EIGHT))
    assert table[54657] == _EIGHT


def test_parse_response_accepts_a_legacy_four_only_row():
    # 20/40/55/75 are enrichment, not requirements: a row carrying only the four the consumers
    # need is still admitted (exactly as the old 4-percentile fetch was).
    legacy = {65: 1799, 85: 2494, 95: 3042, 100: 3482}
    assert moe_wgapi.parse_response(_dist(legacy))[0] == {54657: legacy}


@pytest.mark.parametrize("missing", [65, 85, 95, 100])
def test_parse_response_drops_a_row_missing_any_required_anchor(missing):
    # All-or-nothing on 65/85/95/100 -- a partial row would half-draw both bars.
    row = dict(_EIGHT)
    del row[missing]
    assert moe_wgapi.parse_response(_dist(row))[0] == {}


@pytest.mark.parametrize("bad", [0, -50, None, "x"])
def test_parse_response_drops_a_row_whose_required_anchor_is_unusable(bad):
    row = dict(_EIGHT)
    row[95] = bad
    assert moe_wgapi.parse_response(_dist(row))[0] == {}


@pytest.mark.parametrize("bad", [0, -50, None, "x"])
def test_parse_response_omits_an_unusable_enrichment_anchor(bad):
    # An enrichment anchor that didn't parse (or came back 0) must be ABSENT from the row, never
    # stored as 0 -- a 0-damage anchor at the 40th percentile would flatten the interpolator's
    # whole low end onto the origin.
    row = dict(_EIGHT)
    row[40] = bad
    parsed = moe_wgapi.parse_response(_dist(row))[0][54657]
    assert 40 not in parsed
    assert parsed == dict((k, v) for k, v in _EIGHT.items() if k != 40)


def test_parse_response_keys_are_ints():
    table, _ = moe_wgapi.parse_response(json.dumps(_OK))
    assert all(isinstance(cd, int) for cd in table)
    assert all(isinstance(pct, int) for row in table.values() for pct in row)


def test_parse_response_skips_tank_missing_a_percentile():
    payload = {"status": "ok", "data": {"distribution": {
        "42": {"65": 100, "85": 200, "95": 300},  # no "100" -> unusable for the battle interp
    }}}
    assert moe_wgapi.parse_response(json.dumps(payload))[0] == {}


def test_parse_response_error_status_is_empty():
    payload = {"status": "error", "error": {"message": "INVALID_APPLICATION_ID"}}
    assert moe_wgapi.parse_response(json.dumps(payload)) == ({}, None)


def test_parse_response_malformed_json_is_empty():
    assert moe_wgapi.parse_response("not json") == ({}, None)
    assert moe_wgapi.parse_response("") == ({}, None)
    assert moe_wgapi.parse_response(None) == ({}, None)


def test_parse_response_missing_distribution_is_empty():
    assert moe_wgapi.parse_response(json.dumps({"status": "ok", "data": None}))[0] == {}
    assert moe_wgapi.parse_response(json.dumps({"status": "ok", "data": {}}))[0] == {}


# --- _response_ok (authoritative-success vs transient-failure discriminator) --

def test_response_ok_true_for_well_formed_ok_envelope():
    assert moe_wgapi._response_ok(json.dumps(_OK)) is True
    # ok with an EMPTY distribution is STILL authoritative (those tanks genuinely have no data).
    assert moe_wgapi._response_ok(json.dumps({"status": "ok", "data": {}})) is True


def test_response_ok_false_for_transient_failures():
    assert moe_wgapi._response_ok(None) is False           # network failure (no body)
    assert moe_wgapi._response_ok("") is False
    assert moe_wgapi._response_ok("not json") is False      # bad JSON
    # WG error envelope (rate-limit / bad application_id) -> retry-able, NOT authoritative.
    assert moe_wgapi._response_ok(json.dumps(
        {"status": "error", "error": {"message": "REQUEST_LIMIT_EXCEEDED"}})) is False
    assert moe_wgapi._response_ok(json.dumps({"status": "ok", "data": None})) is False


# --- _poll state machine: transient-failure retry vs authoritative no-data ----
# The engine seams (BigWorld.callback) are no-op stubs (conftest), so _poll runs its branch
# logic synchronously; we drive it with a fake finished worker and inspect module state.

class _FakeThread(object):
    def __init__(self, chunk, ok=False, result=None, updated_at=None, error=None, attempt=0):
        self.chunk = chunk
        self.ok = ok
        self.result = result
        self.updated_at = updated_at
        self.error = error
        self.attempt = attempt

    def is_alive(self):
        return False


def _reset_fetch_state(monkeypatch, app_id="app-id", **kw):
    monkeypatch.setattr(moe_wgapi, "APP_ID", app_id)
    monkeypatch.setattr(moe_wgapi, "_seen", set())
    monkeypatch.setattr(moe_wgapi, "_inflight", set(kw.get("inflight", ())))
    monkeypatch.setattr(moe_wgapi, "_table", dict(kw.get("table", {})))
    monkeypatch.setattr(moe_wgapi, "_queue", [])
    monkeypatch.setattr(moe_wgapi, "_want", {})
    monkeypatch.setattr(moe_wgapi, "_busy", True)
    monkeypatch.setattr(moe_wgapi, "_loaded", False)
    monkeypatch.setattr(moe_wgapi, "_updated_at", 0)
    monkeypatch.setattr(moe_wgapi, "_fetched_at", 0)
    monkeypatch.setattr(moe_wgapi, "_ready_listeners", [])
    monkeypatch.setattr(moe_wgapi, "_save_cache", lambda: None)
    monkeypatch.setattr(moe_wgapi, "_now_epoch", lambda: 1000)


def test_poll_transient_failure_does_not_mark_seen_and_retries(monkeypatch):
    # A network blip / rate-limit on the FIRST attempt: ids must NOT be marked _seen (retry-able)
    # and must stay in _inflight while the bounded retry is scheduled -- the headline fix.
    _reset_fetch_state(monkeypatch, inflight=(10, 20))
    monkeypatch.setattr(moe_wgapi, "_thread", _FakeThread([10, 20], ok=False, result={}, attempt=0))
    moe_wgapi._poll()
    assert moe_wgapi._seen == set()             # NOT doomed to the estimator
    assert moe_wgapi._inflight == {10, 20}      # still tracked (retry pending, no double-enqueue)


def test_poll_gives_up_after_max_retries(monkeypatch):
    # Sustained outage: on the final attempt the chunk is given up -> marked _seen (degrade to the
    # estimator for the session) and cleared from _inflight, rather than retrying forever.
    _reset_fetch_state(monkeypatch, inflight=(10, 20))
    monkeypatch.setattr(moe_wgapi, "_thread",
                        _FakeThread([10, 20], ok=False, result={}, attempt=moe_wgapi._MAX_FETCH_RETRIES))
    moe_wgapi._poll()
    assert moe_wgapi._seen == {10, 20}
    assert moe_wgapi._inflight == set()


def test_poll_authoritative_ok_marks_seen_even_when_tank_absent(monkeypatch):
    # A successful WG 'ok' response that simply doesn't include the tank IS authoritative: the tank
    # genuinely has no MoE data -> mark _seen so the caller degrades to the estimator (no refetch).
    _reset_fetch_state(monkeypatch, inflight=(99,))
    monkeypatch.setattr(moe_wgapi, "_thread", _FakeThread([99], ok=True, result={}, attempt=0))
    moe_wgapi._poll()
    assert moe_wgapi._seen == {99}
    assert moe_wgapi._inflight == set()
    assert moe_wgapi.needs_estimate(99) is True   # -> estimator fallback


def test_poll_authoritative_ok_with_data_caches_and_seen(monkeypatch):
    _reset_fetch_state(monkeypatch, inflight=(69153,))
    row = {65: 2544, 85: 3634, 95: 4512, 100: 5229}
    monkeypatch.setattr(moe_wgapi, "_thread",
                        _FakeThread([69153], ok=True, result={69153: row}, updated_at=123, attempt=0))
    moe_wgapi._poll()
    assert moe_wgapi._table[69153] == row
    assert moe_wgapi._seen == {69153}
    assert moe_wgapi.needs_estimate(69153) is False   # real data -> no estimate


def test_needs_estimate_true_when_no_app_id(monkeypatch):
    # No application_id configured -> no fetch is ever issued, so the estimator is the only path.
    monkeypatch.setattr(moe_wgapi, "APP_ID", "")
    monkeypatch.setattr(moe_wgapi, "_seen", set())
    monkeypatch.setattr(moe_wgapi, "_table", {})
    assert moe_wgapi.needs_estimate(1073) is True
    assert moe_wgapi.needs_estimate(0) is False       # no vehicle -> not an estimate


def test_enqueue_noop_without_app_id(monkeypatch):
    monkeypatch.setattr(moe_wgapi, "APP_ID", "")
    monkeypatch.setattr(moe_wgapi, "_queue", [])
    monkeypatch.setattr(moe_wgapi, "_inflight", set())
    monkeypatch.setattr(moe_wgapi, "_seen", set())
    monkeypatch.setattr(moe_wgapi, "_table", {})
    moe_wgapi._enqueue([1073, 2049])
    assert moe_wgapi._queue == []                      # no doomed HTTP round-trip queued
    assert moe_wgapi._inflight == set()


# --- fresh_table (threshold cache envelope, revalidated at fetched_at + 24h) ---

_UPD = 1783468800      # WG's own updated_at (epoch s) -- stored, but NOT the freshness anchor
_FETCHED = 1783600000  # when WE fetched it (epoch s) -- the freshness anchor


_ROW = {65: 2544, 85: 3634, 95: 4512, 100: 5229}


_CURRENT = object()      # sentinel: `version=None` must stay usable as a real (bad) value


def _blob(fetched_at=_FETCHED, updated_at=_UPD, region="eu", version=_CURRENT, row=None):
    return {"version": moe_wgapi._STORE_VERSION if version is _CURRENT else version,
            "updated_at": updated_at, "fetched_at": fetched_at, "region": region,
            "table": {"69153": dict((str(k), v) for k, v in (row or _ROW).items())}}


def test_fresh_table_within_window_adopts():
    # 1h after WE fetched -> still inside the 24h revalidation window.
    table = moe_wgapi.fresh_table(_blob(), _FETCHED + 3600, "eu")
    assert table == {69153: _ROW}


def test_fresh_table_past_revalidation_is_empty():
    assert moe_wgapi.fresh_table(_blob(), _FETCHED + moe_wgapi._REVALIDATE_SECONDS + 1, "eu") == {}


def test_fresh_table_stale_updated_at_still_adopts():
    # WG publishes with a lag, so updated_at can be days old; freshness is anchored to fetched_at,
    # so a recently-fetched cache is adopted even when its updated_at is far in the past.
    table = moe_wgapi.fresh_table(_blob(updated_at=_UPD - 5 * 24 * 3600), _FETCHED + 3600, "eu")
    assert table == {69153: _ROW}


# --- THE v3 -> v4 re-key guard (the hazard of the percentile re-key) ----------
# A v3 row was keyed by MARK COUNT ({1,2,3,100}). Read as percentiles it maps D65/D85/D95 onto
# the 1st/2nd/3rd percentile -- a still-fresh envelope full of garbage, silently. The ONLY thing
# standing between a user's on-disk v3 cache and that misread is the store-version bump, so pin
# it hard: the version is 4, a v3 envelope is DISCARDED WHOLE (never merged, never partially
# adopted), and a v4 envelope is adopted.

def test_store_version_is_four():
    assert moe_wgapi._STORE_VERSION == 4


def test_fresh_table_rejects_a_v3_envelope_whole():
    v3 = _blob(version=3, row={1: 2544, 2: 3634, 3: 4512, 100: 5229})
    # ...even though it is otherwise perfectly fresh and same-region.
    assert moe_wgapi.fresh_table(v3, _FETCHED + 3600, "eu") == {}


def test_fresh_table_adopts_the_v4_envelope():
    assert moe_wgapi.fresh_table(_blob(version=4), _FETCHED + 3600, "eu") == {69153: _ROW}


@pytest.mark.parametrize("version", [None, 0, 1, 2, 3, "4", 5])
def test_fresh_table_rejects_every_other_store_version(version):
    # Forward AND backward: only the exact current int version is adopted, so a future re-key
    # bump can't be read by this build either.
    assert moe_wgapi.fresh_table(_blob(version=version), _FETCHED + 3600, "eu") == {}


def test_load_cache_discards_a_v3_file_on_disk(monkeypatch, tmp_path):
    # End-to-end through the real read path: a v3 file written by an older build must leave
    # _table EMPTY (-> refetch), not populate it with mark-count keys.
    _use_tmp(monkeypatch, tmp_path)
    moe_wgapi.write_json(moe_wgapi._store_path(),
                         _blob(version=3, row={1: 2544, 2: 3634, 3: 4512, 100: 5229}))
    monkeypatch.setattr(moe_wgapi, "_now_epoch", lambda: _FETCHED + 3600)
    moe_wgapi._load_cache()
    assert moe_wgapi._table == {}
    assert moe_wgapi._updated_at == 0        # nothing adopted -> no stamps carried over either
    assert moe_wgapi._fetched_at == 0


def test_fresh_table_other_region_is_empty():
    assert moe_wgapi.fresh_table(_blob(region="na"), _FETCHED + 3600, "eu") == {}


def test_fresh_table_version_mismatch_is_empty():
    blob = _blob()
    blob["version"] = moe_wgapi._STORE_VERSION + 99
    assert moe_wgapi.fresh_table(blob, _FETCHED + 3600, "eu") == {}


def test_fresh_table_missing_fetched_at_is_empty():
    blob = _blob()
    del blob["fetched_at"]
    assert moe_wgapi.fresh_table(blob, _FETCHED + 3600, "eu") == {}


def test_fresh_table_junk_is_empty():
    assert moe_wgapi.fresh_table(None, _FETCHED, "eu") == {}
    assert moe_wgapi.fresh_table({}, _FETCHED, "eu") == {}


# --- valid_list (persistent fetch-list envelope; no time window) -------------

def _list_blob(region="eu", ids=None):
    return {"version": moe_wgapi._LIST_VERSION, "region": region,
            "ids": ids if ids is not None else {"69153": 1700000000, "1": 1699999999}}


def test_valid_list_adopts_and_coerces_ints():
    assert moe_wgapi.valid_list(_list_blob(), "eu") == {69153: 1700000000, 1: 1699999999}


def test_valid_list_version_mismatch_is_empty():
    blob = _list_blob()
    blob["version"] = moe_wgapi._LIST_VERSION + 99
    assert moe_wgapi.valid_list(blob, "eu") == {}


def test_valid_list_other_region_is_empty():
    assert moe_wgapi.valid_list(_list_blob(region="na"), "eu") == {}


def test_valid_list_junk_is_empty():
    assert moe_wgapi.valid_list(None, "eu") == {}
    assert moe_wgapi.valid_list({}, "eu") == {}
    assert moe_wgapi.valid_list(_list_blob(ids={}), "eu") == {}


def test_valid_list_drops_unparseable_rows():
    blob = _list_blob(ids={"42": 1700000000, "bad": "x", "7": "nope"})
    assert moe_wgapi.valid_list(blob, "eu") == {42: 1700000000}


# --- rank_by_recency ---------------------------------------------------------

def test_rank_by_recency_orders_most_recent_first():
    recency = {10: 100, 20: 300, 30: 200}
    assert garage_roster.rank_by_recency([10, 20, 30], recency) == [20, 30, 10]


def test_rank_by_recency_respects_limit():
    recency = {10: 100, 20: 300, 30: 200}
    assert garage_roster.rank_by_recency([10, 20, 30], recency, limit=2) == [20, 30]


def test_rank_by_recency_never_played_sorts_last_deterministically():
    # Missing recency -> 0; ties (both never played) break by intCD ascending for stability.
    recency = {5: 500}
    assert garage_roster.rank_by_recency([7, 5, 3], recency) == [5, 3, 7]


def test_rank_by_recency_empty():
    assert garage_roster.rank_by_recency([], {}) == []


# --- reconcile_ownership (buy/sell as an owned-set diff) ----------------------
# Not pure (module state + engine read), but driven entirely via monkeypatched seams -- no game
# engine -- like the other adapter tests. Guards the crux buy/sell detection.

def test_reconcile_ownership_seeds_then_diffs(monkeypatch):
    owned = {1, 2, 3}
    monkeypatch.setattr(moe_wgapi.garage_roster, "owned_int_cds", lambda: list(owned))
    bought, sold = [], []
    monkeypatch.setattr(moe_wgapi, "on_vehicle_bought", lambda cd: bought.append(cd))
    monkeypatch.setattr(moe_wgapi, "on_vehicle_sold", lambda cd: sold.append(cd))
    monkeypatch.setattr(moe_wgapi, "_owned", None)

    moe_wgapi.reconcile_ownership()            # first call only seeds the baseline
    assert bought == [] and sold == []

    owned.clear(); owned.update({2, 3, 4})     # buy 4, sell 1
    moe_wgapi.reconcile_ownership()
    assert bought == [4]
    assert sold == [1]


def test_reconcile_ownership_empty_is_noop(monkeypatch):
    monkeypatch.setattr(moe_wgapi.garage_roster, "owned_int_cds", lambda: [])
    monkeypatch.setattr(moe_wgapi, "_owned", None)
    calls = []
    monkeypatch.setattr(moe_wgapi, "on_vehicle_bought", lambda cd: calls.append(cd))
    monkeypatch.setattr(moe_wgapi, "on_vehicle_sold", lambda cd: calls.append(cd))
    moe_wgapi.reconcile_ownership()            # unsynced roster -> no seed, no diff
    assert moe_wgapi._owned is None
    assert calls == []


# --- shared prefs-dir helpers (data_dir / read_json / write_json) -------------
# REGRESSION: both persisted stores were rewritten onto these three shared helpers (now also
# used by adapter/sample_log), so the round-trips below guard that the refactor kept serving the
# threshold cache and the fetch list. `data_dir` is the injection seam -- it imports `helpers`
# lazily, so pointing it at tmp_path is all it takes to run the real disk path game-closed.

def _use_tmp(monkeypatch, tmp_path):
    monkeypatch.setattr(moe_wgapi, "data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(moe_wgapi, "_table", {})
    monkeypatch.setattr(moe_wgapi, "_want", {})
    monkeypatch.setattr(moe_wgapi, "_updated_at", 0)
    monkeypatch.setattr(moe_wgapi, "_fetched_at", 0)
    monkeypatch.setattr(moe_wgapi, "_now_epoch", lambda: _FETCHED)


def test_read_json_write_json_round_trip(monkeypatch, tmp_path):
    path = str(tmp_path / "sub" / "blob.json")
    moe_wgapi.write_json(path, {"a": 1, "b": [2, 3]})     # creates the directory
    assert moe_wgapi.read_json(path) == {"a": 1, "b": [2, 3]}


def test_read_json_missing_is_none(tmp_path):
    assert moe_wgapi.read_json(str(tmp_path / "nope.json")) is None


def test_read_json_corrupt_is_none(tmp_path):
    path = tmp_path / "bad.json"
    path.write_bytes(b'{"a": 1')                          # truncated
    assert moe_wgapi.read_json(str(path)) is None


def test_write_json_overwrites_and_leaves_no_tmp(tmp_path):
    path = str(tmp_path / "blob.json")
    moe_wgapi.write_json(path, {"gen": 1})
    moe_wgapi.write_json(path, {"gen": 2})
    assert moe_wgapi.read_json(path) == {"gen": 2}
    assert not (tmp_path / "blob.json.tmp").exists()      # tmp+rename left nothing behind


def test_write_json_fails_soft(tmp_path):
    # An unwritable target (the path is a directory) degrades to in-memory-only, never raises.
    (tmp_path / "dir.json").mkdir()
    moe_wgapi.write_json(str(tmp_path / "dir.json"), {"a": 1})


def test_threshold_cache_save_load_round_trip(monkeypatch, tmp_path):
    _use_tmp(monkeypatch, tmp_path)
    monkeypatch.setattr(moe_wgapi, "REGION", "eu")
    row = dict(_EIGHT)                                    # a full 8-anchor row round-trips
    monkeypatch.setattr(moe_wgapi, "_table", {69153: dict(row)})
    monkeypatch.setattr(moe_wgapi, "_updated_at", _UPD)
    monkeypatch.setattr(moe_wgapi, "_fetched_at", _FETCHED)
    moe_wgapi._save_cache()

    monkeypatch.setattr(moe_wgapi, "_table", {})
    monkeypatch.setattr(moe_wgapi, "_updated_at", 0)
    monkeypatch.setattr(moe_wgapi, "_fetched_at", 0)
    monkeypatch.setattr(moe_wgapi, "_now_epoch", lambda: _FETCHED + 3600)
    moe_wgapi._load_cache()
    assert moe_wgapi._table == {69153: row}               # int keys restored
    assert moe_wgapi._updated_at == _UPD
    assert moe_wgapi._fetched_at == _FETCHED


def test_threshold_cache_stale_on_disk_is_not_adopted(monkeypatch, tmp_path):
    _use_tmp(monkeypatch, tmp_path)
    monkeypatch.setattr(moe_wgapi, "_table", {69153: {65: 1, 85: 2, 95: 3, 100: 4}})
    monkeypatch.setattr(moe_wgapi, "_fetched_at", _FETCHED)
    moe_wgapi._save_cache()

    monkeypatch.setattr(moe_wgapi, "_table", {})
    monkeypatch.setattr(moe_wgapi, "_now_epoch",
                        lambda: _FETCHED + moe_wgapi._REVALIDATE_SECONDS + 1)
    moe_wgapi._load_cache()
    assert moe_wgapi._table == {}                         # past the window -> refetch


def test_threshold_cache_load_without_a_file_is_a_noop(monkeypatch, tmp_path):
    _use_tmp(monkeypatch, tmp_path)
    moe_wgapi._load_cache()
    assert moe_wgapi._table == {}


# --- Race #2 STEP 2: stale-serve while a threshold refetch is in flight ------
# A disk cache past _REVALIDATE_SECONDS but under the hard _STALE_SERVE_SECONDS cap is held in
# _stale_table (never _table, so _enqueue's dedup still fires the refetch) and get_thresholds
# falls back to it on a _table miss. Past the cap, nothing is adopted / served at all.

def test_load_cache_adopts_stale_but_capped_into_stale_table(monkeypatch, tmp_path):
    _use_tmp(monkeypatch, tmp_path)
    monkeypatch.setattr(moe_wgapi, "REGION", "eu")
    monkeypatch.setattr(moe_wgapi, "_stale_table", {})
    monkeypatch.setattr(moe_wgapi, "_stale_fetched_at", 0)
    monkeypatch.setattr(moe_wgapi, "_table", {69153: {65: 1, 85: 2, 95: 3, 100: 4}})
    monkeypatch.setattr(moe_wgapi, "_fetched_at", _FETCHED)
    moe_wgapi._save_cache()

    monkeypatch.setattr(moe_wgapi, "_table", {})
    now = _FETCHED + moe_wgapi._REVALIDATE_SECONDS + 1     # stale for _table...
    assert now - _FETCHED < moe_wgapi._STALE_SERVE_SECONDS  # ...but still under the hard cap
    monkeypatch.setattr(moe_wgapi, "_now_epoch", lambda: now)
    moe_wgapi._load_cache()
    assert moe_wgapi._table == {}                          # fresh-table dedup must still fire
    assert moe_wgapi._stale_table == {69153: {65: 1, 85: 2, 95: 3, 100: 4}}
    assert moe_wgapi._stale_fetched_at == _FETCHED


def test_load_cache_does_not_adopt_stale_beyond_the_hard_cap(monkeypatch, tmp_path):
    _use_tmp(monkeypatch, tmp_path)
    monkeypatch.setattr(moe_wgapi, "_stale_table", {})
    monkeypatch.setattr(moe_wgapi, "_stale_fetched_at", 0)
    monkeypatch.setattr(moe_wgapi, "_table", {69153: {65: 1, 85: 2, 95: 3, 100: 4}})
    monkeypatch.setattr(moe_wgapi, "_fetched_at", _FETCHED)
    moe_wgapi._save_cache()

    monkeypatch.setattr(moe_wgapi, "_table", {})
    now = _FETCHED + moe_wgapi._STALE_SERVE_SECONDS + 1     # past the hard cap entirely
    monkeypatch.setattr(moe_wgapi, "_now_epoch", lambda: now)
    moe_wgapi._load_cache()
    assert moe_wgapi._table == {}
    assert moe_wgapi._stale_table == {}
    assert moe_wgapi._stale_fetched_at == 0


def _reset_get_thresholds_state(monkeypatch, now, table=None, stale_table=None,
                                stale_fetched_at=0, app_id="app-id"):
    monkeypatch.setattr(moe_wgapi, "APP_ID", app_id)
    monkeypatch.setattr(moe_wgapi, "_started", True)        # skip start(): drive get_thresholds only
    monkeypatch.setattr(moe_wgapi, "_list_ready", True)      # no-op _ensure_list_ready
    monkeypatch.setattr(moe_wgapi, "_table", dict(table or {}))
    monkeypatch.setattr(moe_wgapi, "_stale_table", dict(stale_table or {}))
    monkeypatch.setattr(moe_wgapi, "_stale_fetched_at", stale_fetched_at)
    monkeypatch.setattr(moe_wgapi, "_seen", set())
    monkeypatch.setattr(moe_wgapi, "_inflight", set())
    monkeypatch.setattr(moe_wgapi, "_queue", [])
    monkeypatch.setattr(moe_wgapi, "_now_epoch", lambda: now)
    # _pump would spin up a real fetch thread; stub it so we can assert the queue state it would
    # have consumed, without touching the network.
    calls = []
    monkeypatch.setattr(moe_wgapi, "_pump", lambda: calls.append(1))
    return calls


def test_get_thresholds_serves_stale_row_on_table_miss_within_cap_and_enqueues_refetch(monkeypatch):
    now = 2000
    stale_fetched_at = now - (moe_wgapi._STALE_SERVE_SECONDS - 1)   # just inside the cap
    pump_calls = _reset_get_thresholds_state(monkeypatch, now, stale_table={69153: _ROW},
                                             stale_fetched_at=stale_fetched_at)
    assert moe_wgapi.get_thresholds(69153) == _ROW
    # ...and a real refetch was enqueued, not just a served stale value -- a no-op enqueue would
    # leave both empty.
    assert 69153 in moe_wgapi._inflight
    assert moe_wgapi._queue == [([69153], 0)]
    assert pump_calls == [1]


def test_get_thresholds_blanks_when_stale_row_is_beyond_the_cap(monkeypatch):
    now = 2000
    stale_fetched_at = now - (moe_wgapi._STALE_SERVE_SECONDS + 1)   # just past the cap
    _reset_get_thresholds_state(monkeypatch, now, stale_table={69153: _ROW},
                                stale_fetched_at=stale_fetched_at)
    assert moe_wgapi.get_thresholds(69153) == {}
    assert 69153 in moe_wgapi._inflight   # still enqueues the refetch, just serves nothing meanwhile


def test_poll_evicts_only_the_superseded_stale_row(monkeypatch):
    # Two stale rows on file; a fetch result covering only one of them must drop that one from
    # _stale_table (superseded by fresh data) and leave the other's stale fallback intact.
    _reset_fetch_state(monkeypatch, inflight=(69153,))
    monkeypatch.setattr(moe_wgapi, "_stale_table", {69153: {65: 1, 85: 2, 95: 3, 100: 4}, 1: _ROW})
    row = dict(_EIGHT)
    monkeypatch.setattr(moe_wgapi, "_thread",
                        _FakeThread([69153], ok=True, result={69153: row}, updated_at=123, attempt=0))
    moe_wgapi._poll()
    assert moe_wgapi._table[69153] == row
    assert 69153 not in moe_wgapi._stale_table   # superseded -> dropped
    assert moe_wgapi._stale_table == {1: _ROW}   # the other tank's stale fallback survives


def test_fetch_list_save_load_round_trip(monkeypatch, tmp_path):
    _use_tmp(monkeypatch, tmp_path)
    monkeypatch.setattr(moe_wgapi, "REGION", "eu")
    monkeypatch.setattr(moe_wgapi, "_want", {69153: 1700000000, 1: 1699999999})
    moe_wgapi._save_list()

    monkeypatch.setattr(moe_wgapi, "_want", {})
    moe_wgapi._load_list()
    assert moe_wgapi._want == {69153: 1700000000, 1: 1699999999}


def test_fetch_list_load_without_a_file_keeps_the_list_empty(monkeypatch, tmp_path):
    _use_tmp(monkeypatch, tmp_path)
    moe_wgapi._load_list()
    assert moe_wgapi._want == {}


def test_fetch_list_corrupt_on_disk_keeps_the_list_empty(monkeypatch, tmp_path):
    _use_tmp(monkeypatch, tmp_path)
    (tmp_path / "moe_fetch_list.json").write_bytes(b"not json at all")
    moe_wgapi._load_list()
    assert moe_wgapi._want == {}


def test_the_two_stores_and_the_recorder_are_separate_files(monkeypatch, tmp_path):
    # One shared data_dir, four distinct filenames -- a path collision would have one store
    # silently overwrite another.
    _use_tmp(monkeypatch, tmp_path)
    names = {moe_wgapi._store_path(), moe_wgapi._list_store_path()}
    assert len(names) == 2
    assert all(str(tmp_path) in n for n in names)
