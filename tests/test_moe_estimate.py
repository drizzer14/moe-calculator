# -*- coding: utf-8 -*-
"""Unit tests for the pure offline MoE estimator (domain/moe_estimate). Runs on plain
Python 3 -- no game imports. Covers the inverse-normal CDF accuracy, the OLS fit recovering
a known (mu, sigma), and thresholds_from_samples across its branches (fit / single-sample
prior / degrade-to-empty)."""
import pytest

from moe_calculator.domain import moe_estimate as me

# Reference probit values (from scipy.stats.norm.ppf), for the CDF accuracy check.
_KNOWN = {
    0.5: 0.0,
    0.65: 0.38532046640756773,
    0.85: 1.0364333894937898,
    0.95: 1.6448536269514722,
    0.975: 1.9599639845400545,
    0.99: 2.3263478740408408,
}


# --- inv_norm_cdf -------------------------------------------------------------

@pytest.mark.parametrize("p,z", sorted(_KNOWN.items()))
def test_inv_norm_cdf_matches_known(p, z):
    assert me.inv_norm_cdf(p) == pytest.approx(z, abs=1e-6)


def test_inv_norm_cdf_symmetry():
    for p in (0.6, 0.75, 0.9, 0.99):
        assert me.inv_norm_cdf(p) == pytest.approx(-me.inv_norm_cdf(1.0 - p), abs=1e-9)


def test_inv_norm_cdf_clamps_extremes():
    # 0 and 1 would be -/+ infinity; the clamp keeps them large-but-finite, not a crash.
    assert me.inv_norm_cdf(0.0) < -5.0
    assert me.inv_norm_cdf(1.0) > 5.0


# --- norm_cdf (forward CDF, inverse of inv_norm_cdf) --------------------------

@pytest.mark.parametrize("p,z", sorted(_KNOWN.items()))
def test_norm_cdf_matches_known(p, z):
    # Phi(z) == p for the reference (p, z) pairs.
    assert me.norm_cdf(z) == pytest.approx(p, abs=1e-6)


def test_norm_cdf_zero_is_half():
    assert me.norm_cdf(0.0) == pytest.approx(0.5, abs=1e-12)


def test_norm_cdf_symmetry():
    for z in (0.25, 0.8, 1.5, 2.5):
        assert me.norm_cdf(-z) == pytest.approx(1.0 - me.norm_cdf(z), abs=1e-12)


def test_norm_cdf_round_trips_inverse():
    for p in (0.05, 0.35, 0.65, 0.9, 0.99):
        assert me.norm_cdf(me.inv_norm_cdf(p)) == pytest.approx(p, abs=1e-6)


def test_norm_cdf_extremes_dont_raise():
    # Far tails clamp to ~0 / ~1 without overflow.
    assert 0.0 <= me.norm_cdf(-40.0) < 1e-6
    assert 1.0 - 1e-6 < me.norm_cdf(40.0) <= 1.0


# --- fit_mu_sigma -------------------------------------------------------------

def test_fit_recovers_known_mu_sigma():
    mu, sigma = 986.0, 790.0
    samples = [(mu + sigma * me.inv_norm_cdf(p), p) for p in (0.55, 0.65, 0.8, 0.9, 0.95)]
    fit = me.fit_mu_sigma(samples)
    assert fit is not None
    assert fit[0] == pytest.approx(mu, abs=1e-3)
    assert fit[1] == pytest.approx(sigma, abs=1e-3)


def test_fit_none_with_single_sample():
    assert me.fit_mu_sigma([(1500, 0.8)]) is None


def test_fit_none_when_clustered():
    # Two points at (near-)identical percentile: no z-spread -> not enough to fit a slope.
    assert me.fit_mu_sigma([(1500, 0.840), (1510, 0.842)]) is None


# --- thresholds_from_samples --------------------------------------------------

def test_thresholds_recovered_from_fit_are_ascending():
    mu, sigma = 1000.0, 500.0
    samples = [(mu + sigma * me.inv_norm_cdf(p), p) for p in (0.6, 0.75, 0.9)]
    out = me.thresholds_from_samples(samples)
    assert set(out.keys()) == {1, 2, 3, 100}
    assert out[1] < out[2] < out[3] < out[100]
    # 1-mark threshold sits at the 65th percentile of the fitted line.
    assert out[1] == pytest.approx(mu + sigma * me.inv_norm_cdf(0.65), abs=1.0)


def test_thresholds_single_sample_uses_prior():
    # One point -> non-empty estimate via the universal prior (the "show estimate early" path).
    out = me.thresholds_from_samples([(1500, 0.80)])
    assert set(out.keys()) == {1, 2, 3, 100}
    assert out[1] < out[2] < out[3] < out[100]


def test_thresholds_clustered_still_estimates_via_prior():
    out = me.thresholds_from_samples([(1500, 0.840), (1510, 0.842)])
    assert out and out[1] < out[2] < out[3] < out[100]


def test_thresholds_empty_when_no_samples():
    assert me.thresholds_from_samples([]) == {}
    assert me.thresholds_from_samples(None) == {}


def test_thresholds_empty_when_all_degenerate():
    # damage <= 0 or percentile outside (0,1) -> filtered out -> nothing usable.
    assert me.thresholds_from_samples([(0, 0.8), (-5, 0.9), (1200, 0.0), (1200, 1.0)]) == {}


def test_thresholds_empty_when_slope_non_increasing():
    # Higher percentile with LOWER damage -> negative slope -> sigma <= 0 -> refuse.
    samples = [(2000, 0.6), (1500, 0.8), (1000, 0.95)]
    assert me.thresholds_from_samples(samples) == {}


def test_thresholds_prior_refused_for_very_low_percentile():
    # A percentile so low the normal extrapolation to the marks collapses -> {} (no nonsense).
    assert me.thresholds_from_samples([(300, 0.02)]) == {}


@pytest.mark.parametrize("p", [0.11, 0.12, 0.13, 0.14])
def test_thresholds_prior_refused_in_blowup_band(p):
    # The prior singularity band (p0 in ~(0.108, 0.14)): mu = d0/(1 + CV*z0) blows up as the
    # denominator shrinks, producing 5-figure "required" damage that is still positive and
    # ascending. The plausibility ceiling must refuse it -> {} rather than display nonsense.
    out = me.thresholds_from_samples([(400, p)])
    assert out == {}, "expected refusal, got %r" % (out,)


def test_thresholds_prior_sane_just_above_blowup_band():
    # Just above the band (p0 ~ 0.20) the prior is back to a sane range (out[1] ~ 1600 for
    # d0=400): must still produce a bounded, ascending estimate -- the ceiling must not over-reject.
    out = me.thresholds_from_samples([(400, 0.20)])
    assert set(out.keys()) == {1, 2, 3, 100}
    assert out[1] < out[2] < out[3] < out[100]
    assert out[100] <= me.PRIOR_MAX_MU_MULTIPLE * 400 * 3  # comfortably bounded, not 5-figure
