# -*- coding: utf-8 -*-
"""Tests for the persistent per-account k-calibration cache (adapter/calib_cache.py).

Mirrors tests/test_moe_wgapi.py's idiom: the pure envelope parser (valid_blob) is exercised
directly with no I/O; the behavioural entry points (remember_pending/complete/current_k/
load/save) are exercised with _store_path/save/load monkeypatched so nothing touches real
disk.
"""
import json

import pytest

from moe_calculator.adapter import calib_cache
from moe_calculator.domain import k_estimator
from moe_calculator.domain.constants import EWMA_K


@pytest.fixture(autouse=True)
def _reset():
    calib_cache.clear()
    yield
    calib_cache.clear()


def _no_disk(monkeypatch):
    """Keep load()/save() from touching real disk while still exercising the real logic that
    calls them (state lives only in module globals for the duration of the test)."""
    monkeypatch.setattr(calib_cache, "_store_path", lambda: "<no-disk>")
    monkeypatch.setattr(calib_cache, "save", lambda: None)
    monkeypatch.setattr(calib_cache, "load", lambda: None)
    calib_cache._loaded = True  # load() is stubbed to a no-op -> mark as already-loaded


# --- remember_pending / complete happy path -----------------------------------

def test_remember_then_complete_emits_one_sample(monkeypatch):
    _no_disk(monkeypatch)
    calib_cache.remember_pending(1073, 1800.0, 3000)
    calib_cache.complete(1073, 1824.0)
    assert len(calib_cache._samples) == 1
    assert abs(calib_cache._samples[0] - 0.02) < 1e-9
    assert 1073 not in calib_cache._pending


def test_enough_clean_samples_moves_current_k_off_default(monkeypatch):
    _no_disk(monkeypatch)
    # Feed MIN_SAMPLES clean (avg_before, cd, avg_after) tuples that all resolve to k=0.02.
    for i in range(k_estimator.MIN_SAMPLES):
        cd_int = 1000 + i
        calib_cache.remember_pending(cd_int, 1800.0, 3000)
        calib_cache.complete(cd_int, 1824.0)
    assert len(calib_cache._samples) == k_estimator.MIN_SAMPLES
    result = calib_cache.current_k()
    assert result != EWMA_K
    expected = k_estimator.aggregate_k(calib_cache._samples, EWMA_K)
    assert result == expected
    assert abs(result - 0.02) < 1e-9


def test_remember_pending_on_fresh_cache_preserves_existing_persisted_samples(monkeypatch, tmp_path):
    """remember_pending must load() before mutating/saving -- otherwise a fresh-session call
    (no prior current_k()/complete() to have loaded the cache) would save() an empty _samples,
    wiping whatever was already accumulated on disk."""
    store_path = tmp_path / "moe_calibration.json"
    envelope = {
        "version": calib_cache._STORE_VERSION,
        "pending": {},
        "samples": [0.02, 0.021, 0.019],
    }
    store_path.write_bytes(json.dumps(envelope).encode("utf-8"))
    monkeypatch.setattr(calib_cache, "_store_path", lambda: str(store_path))
    calib_cache.clear()  # fresh cache: _loaded=False, nothing adopted from disk yet

    calib_cache.remember_pending(4242, 1800.0, 3000)

    with open(str(store_path), "rb") as fh:
        persisted = json.loads(fh.read().decode("utf-8"))
    assert persisted["samples"] == [0.02, 0.021, 0.019]
    assert persisted["pending"].get("4242") == [1800.0, 3000]


# --- complete with no pending record -------------------------------------------

def test_complete_with_no_pending_record_is_noop(monkeypatch):
    _no_disk(monkeypatch)
    calib_cache.complete(9999, 1234.0)
    assert calib_cache._samples == []
    assert calib_cache.current_k() == EWMA_K


# --- complete with avg_after == avg_before (dossier not synced yet) ------------

def test_complete_keeps_pending_when_avg_unchanged_then_completes_later(monkeypatch):
    _no_disk(monkeypatch)
    calib_cache.remember_pending(2048, 1800.0, 3000)
    # dossier hasn't synced yet -> avg_after == avg_before -> keep pending, no sample
    calib_cache.complete(2048, 1800.0)
    assert calib_cache._samples == []
    assert 2048 in calib_cache._pending
    # next read brings the real avg_after -> now it completes
    calib_cache.complete(2048, 1824.0)
    assert len(calib_cache._samples) == 1
    assert 2048 not in calib_cache._pending


def test_complete_with_unusable_sample_still_retires_pending(monkeypatch):
    _no_disk(monkeypatch)
    # near-average battle -> observed_k returns None, but the pending record must still retire.
    calib_cache.remember_pending(55, 3000.0, 3100)
    calib_cache.complete(55, 3002.0)
    assert calib_cache._samples == []
    assert 55 not in calib_cache._pending


# --- valid_blob (pure envelope parser) -----------------------------------------

def test_valid_blob_correct_version_parses_pending_and_samples():
    blob = {
        "version": calib_cache._STORE_VERSION,
        "pending": {"1073": [1800.0, 3000]},
        "samples": [0.02, 0.021, 0.019],
    }
    pending, samples = calib_cache.valid_blob(blob)
    assert pending == {1073: (1800.0, 3000)}
    assert samples == [0.02, 0.021, 0.019]


def test_valid_blob_wrong_version_is_empty():
    blob = {"version": calib_cache._STORE_VERSION + 1, "pending": {"1": [1.0, 2]}, "samples": [0.02]}
    assert calib_cache.valid_blob(blob) == ({}, [])


def test_valid_blob_missing_version_is_empty():
    assert calib_cache.valid_blob({"pending": {}, "samples": []}) == ({}, [])


def test_valid_blob_junk_top_level_is_empty():
    assert calib_cache.valid_blob(None) == ({}, [])
    assert calib_cache.valid_blob([]) == ({}, [])
    assert calib_cache.valid_blob("nope") == ({}, [])


def test_valid_blob_drops_junk_pending_rows():
    blob = {
        "version": calib_cache._STORE_VERSION,
        "pending": {
            "1073": [1800.0, 3000],
            "bad": "not-a-row",
            "77": [None, 3000],
            "88": "x",
        },
        "samples": [],
    }
    pending, _ = calib_cache.valid_blob(blob)
    assert pending == {1073: (1800.0, 3000)}


def test_valid_blob_drops_out_of_band_samples_via_clamp():
    blob = {
        "version": calib_cache._STORE_VERSION,
        "pending": {},
        "samples": [0.02, "junk", None, float("nan"), 0.021],
    }
    _, samples = calib_cache.valid_blob(blob)
    assert samples == [0.02, 0.021]


def test_valid_blob_non_dict_pending_is_empty_not_raising():
    blob = {"version": calib_cache._STORE_VERSION, "pending": "oops-a-string", "samples": [0.02]}
    pending, samples = calib_cache.valid_blob(blob)
    assert pending == {}
    assert samples == [0.02]


def test_valid_blob_non_list_samples_is_empty_not_raising():
    blob = {"version": calib_cache._STORE_VERSION, "pending": {}, "samples": 5}
    pending, samples = calib_cache.valid_blob(blob)
    assert pending == {}
    assert samples == []


def test_valid_blob_caps_samples_to_sample_cap():
    blob = {
        "version": calib_cache._STORE_VERSION,
        "pending": {},
        "samples": [0.02] * (k_estimator.SAMPLE_CAP + 50),
    }
    _, samples = calib_cache.valid_blob(blob)
    assert len(samples) == k_estimator.SAMPLE_CAP


# --- ring-buffer cap enforcement on _samples -----------------------------------

def test_samples_ring_buffer_capped_at_sample_cap(monkeypatch):
    _no_disk(monkeypatch)
    for i in range(k_estimator.SAMPLE_CAP + 10):
        cd_int = 5000 + i
        calib_cache.remember_pending(cd_int, 1800.0, 3000)
        calib_cache.complete(cd_int, 1824.0)
    assert len(calib_cache._samples) == k_estimator.SAMPLE_CAP


# --- fail-soft: save()/_store_path() raising must not propagate ---------------

def test_remember_pending_fail_soft_when_save_raises(monkeypatch):
    monkeypatch.setattr(calib_cache, "_store_path", lambda: "<no-disk>")

    def _boom():
        raise IOError("disk full")

    monkeypatch.setattr(calib_cache, "save", _boom)
    monkeypatch.setattr(calib_cache, "load", lambda: None)
    calib_cache._loaded = True
    # Must not raise.
    calib_cache.remember_pending(42, 1800.0, 3000)
    assert calib_cache.current_k() == EWMA_K


def test_complete_fail_soft_when_save_raises(monkeypatch):
    monkeypatch.setattr(calib_cache, "_store_path", lambda: "<no-disk>")
    monkeypatch.setattr(calib_cache, "load", lambda: None)
    calib_cache._loaded = True
    calib_cache._pending[42] = (1800.0, 3000)

    def _boom():
        raise IOError("disk full")

    monkeypatch.setattr(calib_cache, "save", _boom)
    # Must not raise, even though a sample would otherwise have been computed.
    calib_cache.complete(42, 1824.0)
    assert calib_cache.current_k() == EWMA_K


def test_current_k_fail_soft_returns_default_on_exception(monkeypatch):
    monkeypatch.setattr(calib_cache, "load", lambda: None)

    def _boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(k_estimator, "aggregate_k", _boom)
    assert calib_cache.current_k() == EWMA_K


# --- clear() -------------------------------------------------------------------

def test_clear_resets_pending_samples_and_loaded():
    calib_cache._pending[1] = (1.0, 2)
    calib_cache._samples.append(0.02)
    calib_cache._loaded = True
    calib_cache.clear()
    assert calib_cache._pending == {}
    assert calib_cache._samples == []
    assert calib_cache._loaded is False
