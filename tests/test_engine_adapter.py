# -*- coding: utf-8 -*-
"""Branch-logic tests for adapter/engine_adapter.build_snapshot. The module imports
`CurrentVehicle` at top (stubbed in conftest so it imports under pytest); each test drives
behavior by monkeypatching the adapter's own seam functions (_read_moe, moe_data,
g_currentVehicle) rather than the lazy dossier machinery. Mirrors the test_i18n.py fake
pattern."""
from moe_calculator.adapter import engine_adapter as ea
from moe_calculator.adapter import baseline_cache


def teardown_function(_):
    baseline_cache.clear()


class _Veh(object):
    intCD = 1073
    nationName = "germany"


class _CV(object):
    def __init__(self, present, item=None):
        self._present = present
        self.item = item

    def isPresent(self):
        return self._present


def test_build_snapshot_no_vehicle_hides(monkeypatch):
    monkeypatch.setattr(ea, "g_currentVehicle", _CV(present=False))
    snap = ea.build_snapshot()
    assert snap.has_vehicle is False


def test_build_snapshot_happy_path_and_remembers_baseline(monkeypatch):
    monkeypatch.setattr(ea, "g_currentVehicle", _CV(present=True, item=_Veh()))
    monkeypatch.setattr(ea, "_read_moe", lambda cd: (2, 73.7, 1800))
    monkeypatch.setattr(ea.moe_data, "get_thresholds",
                        lambda cd: {1: 1, 2: 2, 3: 3, 100: 4})
    snap = ea.build_snapshot()
    assert snap.has_vehicle is True
    assert snap.vehicle_int_cd == 1073
    assert snap.nation == "germany"
    assert snap.marks == 2
    assert snap.cur_percentile == 73.7
    assert snap.cur_avg_damage == 1800
    assert snap.thresholds == {1: 1, 2: 2, 3: 3, 100: 4}
    # The career baseline is snapshotted for the in-battle overlay (garage -> battle bridge).
    assert baseline_cache.get(1073) == (73.7, 1800)


def test_build_snapshot_estimates_when_request_errored(monkeypatch):
    # WG request completed with no data (needs_estimate True) -> fall back to the offline
    # estimator's extrapolation from the player's own dossier point.
    monkeypatch.setattr(ea, "g_currentVehicle", _CV(present=True, item=_Veh()))
    monkeypatch.setattr(ea, "_read_moe", lambda cd: (1, 60.0, 1500))
    monkeypatch.setattr(ea.moe_data, "get_thresholds", lambda cd: {})
    monkeypatch.setattr(ea.moe_data, "needs_estimate", lambda cd: True)
    calls = []
    monkeypatch.setattr(ea, "_estimate_thresholds",
                        lambda pct, dmg: calls.append((pct, dmg)) or {1: 11, 2: 22, 3: 33, 100: 44})
    snap = ea.build_snapshot()
    assert snap.thresholds == {1: 11, 2: 22, 3: 33, 100: 44}
    assert calls == [(60.0, 1500)]


def test_build_snapshot_waits_when_fetch_pending(monkeypatch):
    # WG fetch still pending (needs_estimate False) -> do NOT estimate; leave thresholds empty
    # and let the ready-listener re-push fill them in when the fetch lands.
    monkeypatch.setattr(ea, "g_currentVehicle", _CV(present=True, item=_Veh()))
    monkeypatch.setattr(ea, "_read_moe", lambda cd: (1, 60.0, 1500))
    monkeypatch.setattr(ea.moe_data, "get_thresholds", lambda cd: {})
    monkeypatch.setattr(ea.moe_data, "needs_estimate", lambda cd: False)
    called = []
    monkeypatch.setattr(ea, "_estimate_thresholds", lambda pct, dmg: called.append(1) or {})
    snap = ea.build_snapshot()
    assert snap.thresholds == {}
    assert called == []


def test_build_snapshot_tail_guard_degrades_on_raise(monkeypatch):
    # small-correctness #3: the tail (baseline_cache.remember / get_thresholds / snapshot
    # construction) now sits INSIDE the try/except, so an unexpected raise degrades to a
    # hidden bar (has_vehicle=False) instead of propagating into the hangar mount.
    monkeypatch.setattr(ea, "g_currentVehicle", _CV(present=True, item=_Veh()))
    monkeypatch.setattr(ea, "_read_moe", lambda cd: (2, 73.7, 1800))

    def boom(cd):
        raise RuntimeError("threshold source down")

    monkeypatch.setattr(ea.moe_data, "get_thresholds", boom)
    snap = ea.build_snapshot()
    assert snap.has_vehicle is False
