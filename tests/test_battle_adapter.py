# -*- coding: utf-8 -*-
"""Branch-logic tests for adapter/battle_adapter.build_battle_snapshot -- the baseline
fallback that is the heart of BUG B, plus the gating-flag passthrough. battle_adapter
imports BigWorld at top (stubbed in conftest); each test monkeypatches the adapter's own
read seams so the snapshot-assembly logic is exercisable with the client closed."""
from moe_calculator.adapter import battle_adapter as ba
from moe_calculator.adapter import baseline_cache
from moe_calculator.adapter import calib_cache
from moe_calculator.domain.constants import EWMA_K


def teardown_function(_):
    baseline_cache.clear()
    calib_cache.clear()


def _no_disk_calib(monkeypatch):
    """Keep the k-calibration cache off real disk in these tests: start clean and stub the
    disk-touching mutator to a no-op. current_k stays fail-soft (returns EWMA_K)."""
    calib_cache.clear()
    monkeypatch.setattr(calib_cache, "complete", lambda *a, **k: None)


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
    _no_disk_calib(monkeypatch)


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
    assert snap.baseline_known is False


def test_snapshot_baseline_known_first_battle_zero_career(monkeypatch):
    # First-ever battle in a freshly-bought tank: the garage DID read it this session
    # (marking it seen with an all-zero career), so the baseline is genuinely 0 -- NOT the
    # untrusted 0 of a replay. baseline_known must be True so the overlay projects from 0
    # instead of dashing.
    _patch_reads(monkeypatch)
    baseline_cache.remember(1073, 0.0, 0)   # garage read of a 0-career tank
    snap = ba.build_battle_snapshot()
    assert snap.pre_percentile == 0.0       # genuine zero baseline
    assert snap.pre_avg_damage == 0
    assert snap.baseline_known is True


def test_snapshot_baseline_known_with_cached_value(monkeypatch):
    # Normal flow: a real >0 baseline is cached -> both value and seen-marker present.
    _patch_reads(monkeypatch)
    baseline_cache.remember(1073, 73.7, 1800)
    snap = ba.build_battle_snapshot()
    assert snap.baseline_known is True


def test_snapshot_no_vehicle_hides(monkeypatch):
    _patch_reads(monkeypatch, cd=0)
    snap = ba.build_battle_snapshot()
    assert snap.has_vehicle is False


def test_snapshot_carries_gating_flags(monkeypatch):
    _patch_reads(monkeypatch, spectating=True, in_battle=True)
    snap = ba.build_battle_snapshot()
    assert snap.is_spectating is True
    assert snap.in_battle is True


def test_snapshot_carries_assist_split(monkeypatch):
    # The server battle-events summary split (track, spot) rides into the snapshot.
    _patch_reads(monkeypatch)
    monkeypatch.setattr(ba, "_read_assist_split", lambda: (900, 400))
    snap = ba.build_battle_snapshot()
    assert snap.track_assist == 900 and snap.spot_assist == 400


def test_snapshot_assist_split_defaults_zero(monkeypatch):
    # With the client closed _read_assist_split fails soft to (0, 0) -> snapshot carries 0/0
    # (the merged live `assist` covers combined damage until the split arrives).
    _patch_reads(monkeypatch)
    snap = ba.build_battle_snapshot()
    assert snap.track_assist == 0 and snap.spot_assist == 0


def test_snapshot_k_from_calib_cache(monkeypatch):
    # The learned per-account EWMA coefficient rides into the snapshot from calib_cache.
    _patch_reads(monkeypatch)
    monkeypatch.setattr(ba.calib_cache, "current_k", lambda: 0.03)
    snap = ba.build_battle_snapshot()
    assert snap.k == 0.03


def test_snapshot_k_defaults_when_calib_raises(monkeypatch):
    # A raising current_k must not break the snapshot assembly: the whole body is guarded, so
    # it fails soft (a hidden-vehicle snapshot is acceptable). It must simply not raise.
    _patch_reads(monkeypatch)

    def boom():
        raise RuntimeError("calib cache down")

    monkeypatch.setattr(ba.calib_cache, "current_k", boom)
    snap = ba.build_battle_snapshot()   # must not raise
    assert snap is not None
    # Fail-soft: either the guarded body degraded to a hidden snapshot (default k) or the
    # field carries the default; either way k stays the community default, never junk.
    assert snap.k == EWMA_K
