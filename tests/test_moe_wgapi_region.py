# -*- coding: utf-8 -*-
"""Region-aware WG-API endpoint + cache: realm -> host, unknown realm => no fetch, and a
persisted cache / fetch list stamped for another region is never adopted."""
import importlib
import os
import sys
import types

import pytest

from moe_calculator import build_config
from moe_calculator.adapter import moe_wgapi

_NOW = 10 ** 9
_ROW = {"65": 1, "85": 2, "95": 3, "100": 4}


@pytest.mark.parametrize("realm,region", [("EU", "eu"), ("NA", "com"), ("ASIA", "asia")])
def test_region_for_realm_maps_known_realms(realm, region):
    assert moe_wgapi.region_for_realm(realm) == region


@pytest.mark.parametrize("realm", ["CT", "RU", "DEV", None, "", "junk", "eu"])
def test_region_for_realm_unknown_is_none(realm):
    assert moe_wgapi.region_for_realm(realm) is None


def _state(monkeypatch, region, app_id):
    monkeypatch.setattr(moe_wgapi, "REGION", region)
    monkeypatch.setattr(moe_wgapi, "APP_ID", app_id)
    monkeypatch.setattr(moe_wgapi, "_table", {})
    monkeypatch.setattr(moe_wgapi, "_stale_table", {})
    monkeypatch.setattr(moe_wgapi, "_seen", set())
    monkeypatch.setattr(moe_wgapi, "_inflight", set())
    monkeypatch.setattr(moe_wgapi, "_queue", [])
    monkeypatch.setattr(moe_wgapi, "_busy", True)  # _pump must not start a thread
    monkeypatch.setattr(moe_wgapi, "_want", {})
    monkeypatch.setattr(moe_wgapi, "_now_epoch", lambda: _NOW)
    monkeypatch.setattr(moe_wgapi, "_store_path", lambda: "cache")
    monkeypatch.setattr(moe_wgapi, "_list_store_path", lambda: "list")


def test_unknown_realm_needs_estimate_and_enqueues_nothing(monkeypatch):
    _state(monkeypatch, None, "")
    assert moe_wgapi.needs_estimate(5) is True
    moe_wgapi._enqueue([5])
    assert moe_wgapi._queue == [] and moe_wgapi._inflight == set()


def test_known_realm_enqueues(monkeypatch):  # control for the test above
    _state(monkeypatch, "eu", "app")
    assert moe_wgapi.needs_estimate(5) is False
    moe_wgapi._enqueue([5])
    assert moe_wgapi._queue == [([5], 0)]


def _cache_blob(region, age):
    return {"version": moe_wgapi._STORE_VERSION, "region": region, "updated_at": 1,
            "fetched_at": _NOW - age, "table": {"7": _ROW}}


@pytest.mark.parametrize("age,attr", [
    (100, "_table"),                                       # fresh path
    (moe_wgapi._REVALIDATE_SECONDS + 10, "_stale_table"),  # stale-serve path
])
def test_load_cache_adopts_matching_region(monkeypatch, age, attr):
    _state(monkeypatch, "com", "app")
    monkeypatch.setattr(moe_wgapi, "read_json", lambda p: _cache_blob("com", age))
    moe_wgapi._load_cache()
    assert getattr(moe_wgapi, attr) == {7: {65: 1, 85: 2, 95: 3, 100: 4}}


@pytest.mark.parametrize("age", [100, moe_wgapi._REVALIDATE_SECONDS + 10])
def test_load_cache_rejects_other_region(monkeypatch, age):
    _state(monkeypatch, "com", "app")
    monkeypatch.setattr(moe_wgapi, "read_json", lambda p: _cache_blob("eu", age))
    moe_wgapi._load_cache()
    assert moe_wgapi._table == {} and moe_wgapi._stale_table == {}


def _list_blob(region):
    return {"version": moe_wgapi._LIST_VERSION, "region": region, "ids": {"7": 123}}


def test_load_list_adopts_matching_region(monkeypatch):
    _state(monkeypatch, "com", "app")
    monkeypatch.setattr(moe_wgapi, "read_json", lambda p: _list_blob("com"))
    moe_wgapi._load_list()
    assert moe_wgapi._want == {7: 123}


def test_load_list_rejects_other_region(monkeypatch):
    _state(monkeypatch, "com", "app")
    monkeypatch.setattr(moe_wgapi, "read_json", lambda p: _list_blob("eu"))
    moe_wgapi._load_list()
    assert moe_wgapi._want == {}


@pytest.mark.parametrize("region", ["eu", "com", "asia"])
def test_build_url_uses_api_url(monkeypatch, region):
    monkeypatch.setattr(moe_wgapi, "API_URL", "https://api.worldoftanks.%s/wot/tanks/mastery/" % region)
    monkeypatch.setattr(moe_wgapi, "APP_ID", "app")
    url = moe_wgapi._build_url([1, 2])
    assert url.startswith("https://api.worldoftanks.%s/wot/tanks/mastery/?" % region)
    assert "tank_id=1,2" in url


@pytest.fixture
def reload_with_realm():
    saved = sys.modules.get("constants")

    def _go(realm):
        sys.modules["constants"] = types.SimpleNamespace(CURRENT_REALM=realm)
        return importlib.reload(moe_wgapi)

    yield _go
    if saved is None:
        sys.modules.pop("constants", None)
    else:
        sys.modules["constants"] = saved
    importlib.reload(moe_wgapi)


def test_module_load_na_realm_resolves_com_host(reload_with_realm):
    m = reload_with_realm("NA")
    assert m.REGION == "com"
    assert "api.worldoftanks.com" in m.API_URL
    assert m.APP_ID == build_config.WG_APPLICATION_ID


def test_module_load_unmapped_realm_disables_fetching(reload_with_realm):
    m = reload_with_realm("CT")
    assert m.REGION is None
    assert m.API_URL == ""
    assert m.APP_ID == ""


def test_unmapped_region_saves_leave_existing_files_untouched(monkeypatch, tmp_path):
    monkeypatch.setattr(moe_wgapi, "data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(moe_wgapi, "REGION", None)
    monkeypatch.setattr(moe_wgapi, "_table", {1: {65: 1, 85: 2, 95: 3, 100: 4}})
    monkeypatch.setattr(moe_wgapi, "_want", {1: 5})
    for save, path in ((moe_wgapi._save_cache, moe_wgapi._store_path()),
                       (moe_wgapi._save_list, moe_wgapi._list_store_path())):
        save()
        assert not os.path.exists(path)          # absent stays absent
        with open(path, "wb") as f:
            f.write(b'{"keep": "me"}')
        save()
        with open(path, "rb") as f:
            assert f.read() == b'{"keep": "me"}'
