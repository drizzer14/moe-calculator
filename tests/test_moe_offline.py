# -*- coding: utf-8 -*-
"""Tests for adapter/moe_offline: the sample store (guards, dedup, cap), the on-disk
round-trip, and threshold estimation from accumulated samples. `_store_path` is monkeypatched
to a tmp file so no real prefs dir / `helpers` import is needed; module state is reset per
test. Runs on plain Python 3."""
import os

import pytest

from moe_calculator.adapter import moe_offline as mo


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch, tmp_path):
    """Fresh module state + a tmp-file store for every test."""
    monkeypatch.setattr(mo, "_samples", {})
    monkeypatch.setattr(mo, "_cache", {})
    monkeypatch.setattr(mo, "_loaded", False)
    store = tmp_path / "moe_samples.json"
    monkeypatch.setattr(mo, "_store_path", lambda: str(store))
    return store


# --- record_sample guards -----------------------------------------------------

@pytest.mark.parametrize("cd,pct,dmg", [
    (0, 80.0, 1500),      # falsy int_cd
    (1073, 80.0, 0),      # avg_damage <= 0
    (1073, 0.0, 1500),    # percentile <= 0
    (1073, 100.0, 1500),  # percentile >= 100 (impossible / degenerate)
])
def test_record_sample_rejects_degenerate(cd, pct, dmg):
    mo.record_sample(cd, pct, dmg)
    assert mo._samples == {}


def test_record_sample_appends_valid():
    mo.record_sample(1073, 80.0, 1500)
    assert mo._samples[1073] == [(1500.0, 80.0)]


# --- dedup + cap --------------------------------------------------------------

def test_dedup_collapses_near_identical_reads():
    mo.record_sample(1073, 80.0, 1500)
    mo.record_sample(1073, 80.02, 1500.5)   # within dedup tolerance -> ignored
    assert len(mo._samples[1073]) == 1
    mo.record_sample(1073, 82.0, 1600)      # real change -> appended
    assert len(mo._samples[1073]) == 2


def test_cap_keeps_newest():
    for i in range(25):
        mo.record_sample(1073, 50.0 + i * 0.2, 1000 + i * 10)
    rows = mo._samples[1073]
    assert len(rows) == mo._MAX_SAMPLES
    assert rows[-1] == (1000 + 24 * 10, 50.0 + 24 * 0.2)   # last recorded retained


# --- persistence round-trip ---------------------------------------------------

def test_store_round_trip(monkeypatch):
    for p, d in [(60.0, 1200), (75.0, 1600), (90.0, 2100)]:
        mo.record_sample(1073, p, d)
    assert os.path.isfile(mo._store_path())

    # Wipe in-memory state and reload from disk.
    monkeypatch.setattr(mo, "_samples", {})
    monkeypatch.setattr(mo, "_cache", {})
    monkeypatch.setattr(mo, "_loaded", False)
    mo.start()
    assert mo._samples[1073] == [(1200.0, 60.0), (1600.0, 75.0), (2100.0, 90.0)]
    out = mo.get_thresholds(1073)
    assert out and out[1] < out[2] < out[3] < out[100]


def test_get_thresholds_unknown_tank_is_empty():
    mo.record_sample(1073, 80.0, 1500)
    assert mo.get_thresholds(9999) == {}


# --- estimation behaviour -----------------------------------------------------

def test_single_sample_yields_estimate_via_prior():
    mo.record_sample(1073, 80.0, 1500)
    out = mo.get_thresholds(1073)
    assert set(out.keys()) == {1, 2, 3, 100}
    assert out[1] < out[2] < out[3] < out[100]


def test_more_samples_refine_and_invalidate_cache():
    mo.record_sample(1073, 80.0, 1500)
    first = mo.get_thresholds(1073)          # memoized (prior)
    mo.record_sample(1073, 90.0, 2000)       # a spread sample -> cache invalidated
    mo.record_sample(1073, 65.0, 1100)
    second = mo.get_thresholds(1073)         # now a real fit
    assert second and second != first


def test_never_played_tank_has_no_thresholds():
    assert mo.get_thresholds(1073) == {}


# --- misc surface -------------------------------------------------------------

def test_add_ready_listener_fires_immediately_and_is_guarded():
    fired = []
    mo.add_ready_listener(lambda: fired.append(True))
    assert fired == [True]
    mo.add_ready_listener(lambda: (_ for _ in ()).throw(RuntimeError("boom")))  # must not raise


def test_start_is_idempotent():
    mo.start()
    assert mo.is_loaded() is True
    mo.start()   # no raise, no reload side effects
