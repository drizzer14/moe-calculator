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


# --- fresh_table (per-day cache envelope, revalidated at updated_at + 24h) ----

_UPD = 1783468800  # the data's own updated_at (epoch s)


def _blob(updated_at=_UPD, region="eu"):
    return {"version": moe_wgapi._STORE_VERSION, "updated_at": updated_at, "region": region,
            "table": {"69153": {"1": 2544, "2": 3634, "3": 4512, "100": 5229}}}


def test_fresh_table_within_window_adopts():
    # 1h after updated_at -> still inside the 24h revalidation window.
    table = moe_wgapi.fresh_table(_blob(), _UPD + 3600, "eu")
    assert table == {69153: {1: 2544, 2: 3634, 3: 4512, 100: 5229}}


def test_fresh_table_past_revalidation_is_empty():
    assert moe_wgapi.fresh_table(_blob(), _UPD + moe_wgapi._REVALIDATE_SECONDS + 1, "eu") == {}


def test_fresh_table_other_region_is_empty():
    assert moe_wgapi.fresh_table(_blob(region="na"), _UPD + 3600, "eu") == {}


def test_fresh_table_version_mismatch_is_empty():
    blob = _blob()
    blob["version"] = moe_wgapi._STORE_VERSION + 99
    assert moe_wgapi.fresh_table(blob, _UPD + 3600, "eu") == {}


def test_fresh_table_missing_updated_at_is_empty():
    blob = _blob()
    del blob["updated_at"]
    assert moe_wgapi.fresh_table(blob, _UPD + 3600, "eu") == {}


def test_fresh_table_junk_is_empty():
    assert moe_wgapi.fresh_table(None, _UPD, "eu") == {}
    assert moe_wgapi.fresh_table({}, _UPD, "eu") == {}


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
