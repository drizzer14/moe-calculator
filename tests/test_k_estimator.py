# -*- coding: utf-8 -*-
"""Tests for the pure EWMA-coefficient estimator (domain/k_estimator.py).

No monkeypatching, no I/O -- every function here is a total function of numbers, so these
tests run identically on the client's Python 2.7 and the dev Python 3.13 interpreter.
"""
from moe_calculator.domain import k_estimator


# --- observed_k ---------------------------------------------------------------

def test_observed_k_known_tuple():
    # denom = 3000-1800=1200, numer = 1824-1800=24, k = 24/1200 = 0.02
    k = k_estimator.observed_k(1800, 3000, 1824)
    assert k is not None
    assert abs(k - 0.02) < 1e-9


def test_observed_k_denominator_guard_rejects_near_average_battle():
    # |cd - avg_before| = |3100-3000| = 100 < MIN_DENOM=300 -> None
    assert k_estimator.observed_k(3000, 3100, 3002) is None


def test_observed_k_sign_guard_above_average_battle_avg_fell():
    # cd > avg_before (above-average battle) but avg_after < avg_before (avg FELL) -> reject
    assert k_estimator.observed_k(3000, 4000, 2900) is None


def test_observed_k_sign_guard_below_average_battle_avg_rose():
    # cd < avg_before (below-average battle) but avg_after > avg_before (avg ROSE) -> reject
    assert k_estimator.observed_k(3000, 2000, 3100) is None


def test_observed_k_numerator_zero_avg_did_not_move():
    assert k_estimator.observed_k(3000, 4000, 3000) is None


def test_observed_k_outlier_band_first_ever_battle():
    # first-ever battle: avg_after == cd (the average IS the single sample) -> k ~= 1, outlier
    assert k_estimator.observed_k(0, 3000, 3000) is None


def test_observed_k_outlier_band_above_kmax():
    # denom=1000, numer=100 -> k=0.1 > K_MAX=0.05
    assert k_estimator.observed_k(1000, 2000, 1100) is None


def test_observed_k_junk_inputs():
    assert k_estimator.observed_k(float("nan"), 3000, 1824) is None
    assert k_estimator.observed_k(1800, float("nan"), 1824) is None
    assert k_estimator.observed_k(1800, 3000, float("nan")) is None
    assert k_estimator.observed_k(None, 3000, 1824) is None
    assert k_estimator.observed_k(1800, "not-a-number", 1824) is None
    assert k_estimator.observed_k(1800, 3000, None) is None
    assert k_estimator.observed_k(float("inf"), 3000, 1824) is None


# --- clamp_k --------------------------------------------------------------

def test_clamp_k_below_min_clamps_up():
    assert k_estimator.clamp_k(0.001) == k_estimator.K_MIN


def test_clamp_k_above_max_clamps_down():
    assert k_estimator.clamp_k(0.5) == k_estimator.K_MAX


def test_clamp_k_in_band_unchanged():
    assert k_estimator.clamp_k(0.02) == 0.02


def test_clamp_k_junk_is_none():
    assert k_estimator.clamp_k(None) is None
    assert k_estimator.clamp_k("nope") is None
    assert k_estimator.clamp_k(float("nan")) is None
    assert k_estimator.clamp_k(float("inf")) is None
    assert k_estimator.clamp_k(float("-inf")) is None


# --- aggregate_k ------------------------------------------------------------

_DEFAULT = 2.0 / 101  # EWMA_K, N=100


def test_aggregate_k_empty_returns_default():
    assert k_estimator.aggregate_k([], _DEFAULT) == _DEFAULT


def test_aggregate_k_below_min_samples_returns_default():
    samples = [0.02] * (k_estimator.MIN_SAMPLES - 1)
    assert k_estimator.aggregate_k(samples, _DEFAULT) == _DEFAULT


def test_aggregate_k_at_min_samples_returns_clamped_median():
    samples = [0.02] * k_estimator.MIN_SAMPLES
    assert k_estimator.aggregate_k(samples, _DEFAULT) == 0.02


def test_aggregate_k_odd_count_median():
    samples = [0.01, 0.02, 0.03, 0.015, 0.025, 0.018, 0.022, 0.03, 0.02]  # 9 values
    result = k_estimator.aggregate_k(samples, _DEFAULT)
    expected = k_estimator.clamp_k(sorted(samples)[4])
    assert result == expected


def test_aggregate_k_even_count_median():
    samples = [0.01, 0.02, 0.03, 0.015, 0.025, 0.018, 0.022, 0.03]  # 8 values
    result = k_estimator.aggregate_k(samples, _DEFAULT)
    s = sorted(samples)
    expected = k_estimator.clamp_k(0.5 * (s[3] + s[4]))
    assert result == expected


def test_aggregate_k_outlier_in_list_still_yields_sane_clamped_median():
    # one wild out-of-band value mixed with 8 good ones -- median should stay near the good cluster
    samples = [0.02, 0.021, 0.019, 0.022, 0.018, 0.02, 0.021, 0.019, 5.0]
    result = k_estimator.aggregate_k(samples, _DEFAULT)
    assert result is not None
    assert k_estimator.K_MIN <= result <= k_estimator.K_MAX
    assert abs(result - 0.02) < 0.01


def test_aggregate_k_non_numeric_entries_dropped_defensively():
    samples = [0.02] * k_estimator.MIN_SAMPLES + [None, "junk", float("nan")]
    assert k_estimator.aggregate_k(samples, _DEFAULT) == 0.02


def test_aggregate_k_none_default_used_when_below_min_samples():
    assert k_estimator.aggregate_k(None, _DEFAULT) == _DEFAULT
