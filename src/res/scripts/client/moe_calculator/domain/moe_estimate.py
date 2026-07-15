# -*- coding: utf-8 -*-
"""Offline Marks-of-Excellence threshold ESTIMATOR. Pure and engine-free (2/3-compatible).

WG never sends the per-tank population combined-damage thresholds to the client (they are
computed server-side). But the client dossier DOES expose, per tank, the player's own
`movingAvgDamage` (an EWMA combined damage) and `damageRating` (the official MoE percentile
that damage occupies in the tank's population). Each such pair is therefore ONE point on
that tank's combined-damage -> percentile curve. Given a few points we can fit the curve and
read off the 1/2/3-mark thresholds (the 65/85/95 percentiles) plus a high-percentile goalpost.

Model: assume each tank's population of EMA combined damage is approximately normal, so
    d = mu + sigma * z(p),   z(p) = inv_norm_cdf(p)   (the probit / inverse-normal CDF).
- With >= MIN_SAMPLES spread-out points we fit (mu, sigma) by ordinary least squares of d on z.
- With a single point (or points too clustered in percentile to fit a slope) we fall back to a
  baked universal prior: assume sigma = UNIVERSAL_CV * mu and solve for mu from the one point,
  so an estimate appears from the very first sample (marked "~" in the widget), sharpening once
  a second, percentile-spread sample lands.

Everything here is arithmetic only (no numpy/scipy, none exist in the client) and unit-tested
on Python 3. The normal assumption is the dominant approximation -- honest caveat: it is
weakest in the tails, and extrapolating far above the player's current standing is unreliable.
"""
import math

from moe_calculator.domain.constants import MARK_PERCENTS, MARK_COUNTS, GOALPOST_PERCENTILE
from moe_calculator.domain.rounding import iround_half_away

# Minimum distinct samples needed for a per-tank least-squares fit; below this we use the
# single-sample prior.
MIN_SAMPLES = 2
# Minimum spread (in z / probit units) the samples' percentiles must span for the OLS slope to
# be well-conditioned. Two percentiles ~5 points apart near the middle clear this; tighter
# clusters fall back to the prior instead of amplifying noise into a wild slope.
MIN_Z_SPREAD = 0.15
# Universal coefficient of variation (sigma/mu) for the single-sample prior. Derived once at
# dev time by fitting each tank's (mu, sigma) from a published MoE table and taking the median
# sigma/mu across the roster (see tools/dev/derive_moe_prior.py). Runtime never fetches anything
# -- this is a baked constant. Provenance: median over 760 EU tanks (tomato.gg, 2026-07), where
# the normal model's residual at the 85th percentile averaged ~1.4% (assumption holds well).
UNIVERSAL_CV = 0.8079

# Probability clamp: inv_norm_cdf(0) / (1) are -/+ infinity, so keep p strictly interior.
_P_EPS = 1e-9
# Below this the single-sample prior denominator (1 + CV*z0) collapses (percentile so low the
# normal extrapolation to the marks is meaningless) -- refuse rather than emit nonsense.
_DENOM_EPS = 1e-3
# Upper plausibility bound for the single-sample prior: the fitted mu = d0/(1 + CV*z0) blows up
# as the denominator shrinks toward zero (a low-percentile sample, z0 << 0), so a percentile
# just above the singularity (p0 ~ 0.108) yields mu -- and thus 5-figure mark thresholds -- that
# stay positive and strictly ascending, sailing past the `_targets` sanity gate. `_DENOM_EPS`
# only refuses the exact collapse. This ceiling refuses any prior whose mu exceeds a generous
# multiple of the player's own sample damage: a genuine estimate near the sane band (p0 ~ 0.20)
# sits at mu ~ 3*d0; the blow-up band (p0 in (0.108, 0.14)) is mu > 7.8*d0. Refusing (-> {})
# degrades the widget to no per-mark labels, which is safer than displaying a wrong number.
PRIOR_MAX_MU_MULTIPLE = 6.0


def _clamp_p(p):
    if p < _P_EPS:
        return _P_EPS
    if p > 1.0 - _P_EPS:
        return 1.0 - _P_EPS
    return p


# --- inverse normal CDF (probit) ---------------------------------------------
# Acklam's rational approximation. Max relative error ~1.15e-9 after the optional Halley
# refinement below; even the bare approximation (~1e-4) is far tighter than the normality
# assumption's error, so this is never the limiting factor.
_A = (-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
      1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00)
_B = (-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
      6.680131188771972e+01, -1.328068155288572e+01)
_C = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
      -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00)
_D = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
      3.754408661907416e+00)
_P_LOW = 0.02425
_P_HIGH = 1.0 - _P_LOW


def inv_norm_cdf(p):
    """Inverse standard-normal CDF (probit): the z such that Phi(z) == p. Input clamped to the
    open interval so 0/1 don't blow up to -/+ infinity."""
    p = _clamp_p(float(p))
    if p < _P_LOW:
        q = math.sqrt(-2.0 * math.log(p))
        x = (((((_C[0] * q + _C[1]) * q + _C[2]) * q + _C[3]) * q + _C[4]) * q + _C[5]) / \
            ((((_D[0] * q + _D[1]) * q + _D[2]) * q + _D[3]) * q + 1.0)
    elif p <= _P_HIGH:
        q = p - 0.5
        r = q * q
        x = (((((_A[0] * r + _A[1]) * r + _A[2]) * r + _A[3]) * r + _A[4]) * r + _A[5]) * q / \
            (((((_B[0] * r + _B[1]) * r + _B[2]) * r + _B[3]) * r + _B[4]) * r + 1.0)
    else:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        x = -(((((_C[0] * q + _C[1]) * q + _C[2]) * q + _C[3]) * q + _C[4]) * q + _C[5]) / \
            ((((_D[0] * q + _D[1]) * q + _D[2]) * q + _D[3]) * q + 1.0)
    # One Halley step tightens the approximation to near machine precision. Guarded behind
    # erfc's availability (present in Python 2.7+); the bare value is already adequate.
    try:
        e = 0.5 * math.erfc(-x / math.sqrt(2.0)) - p
        u = e * math.sqrt(2.0 * math.pi) * math.exp(x * x / 2.0)
        x = x - u / (1.0 + x * u / 2.0)
    except (AttributeError, OverflowError, ValueError):
        pass
    return x


def norm_cdf(z):
    """Forward standard-normal CDF: Phi(z), the probability mass at or below z. The inverse
    of inv_norm_cdf. Used by the in-battle overlay to map a combined-damage value to a
    percentile over the fitted (mu, sigma) curve (percent = 100*norm_cdf((d-mu)/sigma)),
    so the projection rides WG's smooth distribution SHAPE instead of straight chords.

    erfc-based (same idiom as the Halley step above); math.erfc exists in Python 2.7+ and 3.x.
    Always finite in (0.0, 1.0) for a finite z."""
    return 0.5 * math.erfc(-float(z) / math.sqrt(2.0))


# --- fitting -----------------------------------------------------------------

def _valid_samples(samples):
    """Keep only usable (damage, percentile-fraction) pairs: damage > 0 and 0 < p < 1."""
    out = []
    for s in samples or ():
        try:
            d = float(s[0])
            p = float(s[1])
        except (TypeError, ValueError, IndexError):
            continue
        if d > 0.0 and 0.0 < p < 1.0:
            out.append((d, p))
    return out


def fit_mu_sigma(samples):
    """OLS fit of damage on z=inv_norm_cdf(p) over the samples. Returns (mu, sigma) or None
    when there are too few samples, too little percentile spread, or a degenerate slope."""
    pts = _valid_samples(samples)
    if len(pts) < MIN_SAMPLES:
        return None
    zs = [inv_norm_cdf(p) for _d, p in pts]
    ds = [d for d, _p in pts]
    if max(zs) - min(zs) < MIN_Z_SPREAD:
        return None
    n = float(len(pts))
    zbar = sum(zs) / n
    dbar = sum(ds) / n
    sxx = sum((z - zbar) ** 2 for z in zs)
    if sxx <= 0.0:
        return None
    sxy = sum((zs[i] - zbar) * (ds[i] - dbar) for i in range(len(pts)))
    sigma = sxy / sxx
    mu = dbar - sigma * zbar
    return (mu, sigma)


def _prior_mu_sigma(pts):
    """Single-sample (or clustered) prior: assume sigma = UNIVERSAL_CV*mu and solve for mu from
    the mean of the available points. Returns (mu, sigma) or None when the population percentile
    is so low the normal extrapolation to the marks collapses."""
    n = float(len(pts))
    d0 = sum(d for d, _p in pts) / n
    p0 = sum(p for _d, p in pts) / n
    z0 = inv_norm_cdf(p0)
    denom = 1.0 + UNIVERSAL_CV * z0
    if denom <= _DENOM_EPS:
        return None
    mu = d0 / denom
    if mu <= 0.0:
        return None
    # Guard the near-singularity blow-up: a low-percentile sample drives denom toward zero and
    # mu (hence every mark threshold) to an absurd multiple of the sample damage. Refuse it.
    if mu > PRIOR_MAX_MU_MULTIPLE * d0:
        return None
    return (mu, UNIVERSAL_CV * mu)


def _targets(mu, sigma):
    """Map a fitted (mu, sigma) to the {1,2,3,100: damage} threshold dict. Returns None unless
    every value is positive and strictly ascending (a sane distribution)."""
    if sigma <= 0.0:
        return None
    out = {}
    for percent, count in zip(MARK_PERCENTS, MARK_COUNTS):
        out[count] = iround_half_away(mu + sigma * inv_norm_cdf(percent / 100.0))
    out[100] = iround_half_away(mu + sigma * inv_norm_cdf(GOALPOST_PERCENTILE / 100.0))
    ordered = [out[1], out[2], out[3], out[100]]
    prev = 0
    for v in ordered:
        if v <= 0 or v <= prev:
            return None
        prev = v
    return out


def thresholds_from_samples(samples):
    """Estimate {1,2,3,100: combined-damage} from the accumulated (damage, percentile-fraction)
    samples for one tank. Uses the OLS fit when the samples span enough percentile range, else
    the single-sample universal prior. Returns {} when nothing usable is available (e.g. a
    never-played tank), so the widget degrades to no per-mark labels."""
    pts = _valid_samples(samples)
    if not pts:
        return {}
    fit = fit_mu_sigma(pts)
    if fit is None:
        fit = _prior_mu_sigma(pts)
    if fit is None:
        return {}
    targets = _targets(fit[0], fit[1])
    return targets or {}
