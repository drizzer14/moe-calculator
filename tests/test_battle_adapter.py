# -*- coding: utf-8 -*-
"""Branch-logic tests for adapter/battle_adapter.build_battle_snapshot -- the baseline
fallback that is the heart of BUG B, plus the gating-flag passthrough. battle_adapter
imports BigWorld at top (stubbed in conftest); each test monkeypatches the adapter's own
read seams so the snapshot-assembly logic is exercisable with the client closed."""
from moe_calculator.adapter import battle_adapter as ba
from moe_calculator.adapter import baseline_cache


def teardown_function(_):
    baseline_cache.clear()


def _patch_reads(monkeypatch, cd=1073, eff=(2000, 500, 0), thr=None,
                 in_battle=True, spectating=False, nation="germany"):
    monkeypatch.setattr(ba, "_player_vehicle_descr", lambda: object())
    monkeypatch.setattr(ba, "_player_vehicle_int_cd", lambda d: cd)
    monkeypatch.setattr(ba, "_read_efficiency", lambda: eff)
    monkeypatch.setattr(ba, "_player_nation", lambda d: nation)
    monkeypatch.setattr(ba, "_in_battle", lambda: in_battle)
    monkeypatch.setattr(ba, "_is_spectating", lambda: spectating)
    monkeypatch.setattr(ba.moe_data, "get_thresholds",
                        lambda c: dict(thr or {1: 1, 2: 2, 3: 3, 100: 4}))
    # In battle the lobby dossier is None -> engine_adapter._read_moe returns zeros; the
    # baseline must come from the garage cache instead.
    monkeypatch.setattr(ba.engine_adapter, "_read_moe", lambda c: (0, 0.0, 0))


def test_snapshot_falls_back_to_garage_baseline(monkeypatch):
    _patch_reads(monkeypatch)
    baseline_cache.remember(1073, 73.7, 1800)
    snap = ba.build_battle_snapshot()
    assert snap.has_vehicle is True
    assert snap.pre_percentile == 73.7
    assert snap.pre_avg_damage == 1800
    assert snap.damage == 2000 and snap.assist == 500


def test_snapshot_no_baseline_when_never_garaged(monkeypatch):
    # BUG B: replay / relogin straight into battle, tank never seen in the garage this
    # session -> the cache is empty -> the baseline reads empty. build_battle_model then
    # flags has_baseline=False (see test_battle_builder) and the overlay dashes the metrics.
    _patch_reads(monkeypatch)
    snap = ba.build_battle_snapshot()
    assert snap.pre_percentile == 0.0
    assert snap.pre_avg_damage == 0


def test_snapshot_no_vehicle_hides(monkeypatch):
    _patch_reads(monkeypatch, cd=0)
    snap = ba.build_battle_snapshot()
    assert snap.has_vehicle is False


def test_snapshot_carries_gating_flags(monkeypatch):
    _patch_reads(monkeypatch, spectating=True, in_battle=True)
    snap = ba.build_battle_snapshot()
    assert snap.is_spectating is True
    assert snap.in_battle is True
