# -*- coding: utf-8 -*-
"""Tests for the pure logic of the WG-API MoE provider + the garage roster.

The engine-facing fetch/poll/persist code is exercised in-client; here we cover the pieces
that need no game engine:
  - moe_wgapi.parse_response  : WG /tanks/mastery JSON -> {int_cd: {1,2,3,100: dmg}}
  - moe_wgapi.fresh_table     : per-day cache envelope validity (fresh adopts / stale drops)
  - garage_roster.rank_by_recency : top-N owned intCDs by last-battle time (most recent first)
"""
import json

from moe_calculator.adapter import moe_wgapi
from moe_calculator.adapter import garage_roster


# --- parse_response ----------------------------------------------------------

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


def test_parse_response_maps_percentiles_to_mark_keys():
    table, updated_at = moe_wgapi.parse_response(json.dumps(_OK))
    assert table[69153] == {1: 2544, 2: 3634, 3: 4512, 100: 5229}
    assert table[1] == {1: 709, 2: 1064, 3: 1367, 100: 1500}
    assert updated_at == 1783468800


def test_parse_response_keys_are_ints():
    table, _ = moe_wgapi.parse_response(json.dumps(_OK))
    assert all(isinstance(cd, int) for cd in table)


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
    row = {1: 2544, 2: 3634, 3: 4512, 100: 5229}
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


def _blob(fetched_at=_FETCHED, updated_at=_UPD, region="eu"):
    return {"version": moe_wgapi._STORE_VERSION, "updated_at": updated_at,
            "fetched_at": fetched_at, "region": region,
            "table": {"69153": {"1": 2544, "2": 3634, "3": 4512, "100": 5229}}}


def test_fresh_table_within_window_adopts():
    # 1h after WE fetched -> still inside the 24h revalidation window.
    table = moe_wgapi.fresh_table(_blob(), _FETCHED + 3600, "eu")
    assert table == {69153: {1: 2544, 2: 3634, 3: 4512, 100: 5229}}


def test_fresh_table_past_revalidation_is_empty():
    assert moe_wgapi.fresh_table(_blob(), _FETCHED + moe_wgapi._REVALIDATE_SECONDS + 1, "eu") == {}


def test_fresh_table_stale_updated_at_still_adopts():
    # WG publishes with a lag, so updated_at can be days old; freshness is anchored to fetched_at,
    # so a recently-fetched cache is adopted even when its updated_at is far in the past.
    table = moe_wgapi.fresh_table(_blob(updated_at=_UPD - 5 * 24 * 3600), _FETCHED + 3600, "eu")
    assert table == {69153: {1: 2544, 2: 3634, 3: 4512, 100: 5229}}


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
