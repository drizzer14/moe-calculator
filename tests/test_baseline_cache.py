# -*- coding: utf-8 -*-
"""Tests for the pre-battle baseline cache (pure, engine-free -- runs on Python 3)."""
from moe_calculator.adapter import baseline_cache


def setup_function(_):
    baseline_cache.clear()


def test_remember_then_get_roundtrips():
    baseline_cache.remember(1073, 73.67, 1850)
    assert baseline_cache.get(1073) == (73.67, 1850)


def test_get_unknown_is_none():
    assert baseline_cache.get(9999) is None


def test_empty_read_does_not_overwrite_good_baseline():
    baseline_cache.remember(1073, 73.67, 1850)
    baseline_cache.remember(1073, 0.0, 0)   # transient empty read -> ignored
    assert baseline_cache.get(1073) == (73.67, 1850)


def test_empty_read_stores_nothing():
    baseline_cache.remember(1073, 0.0, 0)
    assert baseline_cache.get(1073) is None


def test_percentile_only_is_remembered():
    # A tank with a standing but no moving-avg record still yields a usable baseline.
    baseline_cache.remember(1073, 12.5, 0)
    assert baseline_cache.get(1073) == (12.5, 0)


def test_falsy_key_is_noop():
    baseline_cache.remember(0, 50.0, 1000)
    assert baseline_cache.get(0) is None


def test_coerces_types():
    baseline_cache.remember("1073", 73.67, 1850.9)
    # key normalized to int, percentile float, avg truncated to int
    assert baseline_cache.get(1073) == (73.67, 1850)


# --- seen(): "was this tank read in the garage this session?" ----------------
# Distinct from get(): a first-ever-battle tank has a GENUINE 0/0 career, so get()
# stays None (no >0 value stored) but seen() must be True -- the garage DID read it.

def test_seen_true_even_for_all_zero_read():
    # Freshly-bought, 0-career tank viewed in the garage: value is not stored (get None)
    # but the read happened, so the tank is marked seen.
    baseline_cache.remember(1073, 0.0, 0)
    assert baseline_cache.get(1073) is None
    assert baseline_cache.seen(1073) is True


def test_seen_true_for_real_baseline():
    baseline_cache.remember(1073, 73.67, 1850)
    assert baseline_cache.seen(1073) is True


def test_seen_false_when_never_remembered():
    assert baseline_cache.seen(9999) is False


def test_seen_false_on_falsy_key():
    baseline_cache.remember(0, 0.0, 0)
    assert baseline_cache.seen(0) is False


def test_seen_coerces_key_type():
    baseline_cache.remember("1073", 0.0, 0)
    assert baseline_cache.seen(1073) is True


def test_clear_resets_seen():
    baseline_cache.remember(1073, 0.0, 0)
    baseline_cache.clear()
    assert baseline_cache.seen(1073) is False
