# -*- coding: utf-8 -*-
"""Empirical EWMA-coefficient estimator for the in-battle projection. Pure/engine-free (2/3).

The overlay projects the post-battle moving average with proj = prevAvg + k*(cd - prevAvg).
The default k = 2/(N+1), N=100 (domain/constants.EWMA_K) is a community guess for WG's real
averaging window; in-client it reads systematically too SMALL -- a blowout battle undershoots
the garage value while a near-average battle matches. But WG's real moving average
(movingAvgDamage) is readable in the garage dossier, so each battle yields ONE observation of
WG's true single step:

    k_real = (avg_after - avg_before) / (cd - avg_before)

where avg_before/avg_after are the pre-/post-battle movingAvgDamage and cd is the combined
damage the overlay computed. This module turns a stream of such (avg_before, cd, avg_after)
samples into a robust running k: reject bad samples, take the clamped MEDIAN once enough
accumulate, fall back to the caller's default until then. Because k_real is derived from OUR
cd, a per-account median also absorbs how THIS player's cd is biased (max-assist
approximation, team_damage=0 live) -- something a single baked constant could not.

Arithmetic only (no `statistics` module -- not guaranteed in the 2.7 client). The adapter owns
capture + persistence (adapter/calib_cache); this stays a pure function of numbers so it
unit-tests on Python 3 with the client closed.
"""

# Plausible band for k. WG describes the Marks rating as a moving average over "~50-100
# battles"; k = 2/(N+1) maps N=40 -> 0.0488 and N=400 -> 0.00499, so [K_MIN, K_MAX] brackets a
# generous window range. A sample or median outside it is an artefact, not a real coefficient.
K_MIN = 0.005
K_MAX = 0.05

# The battle's combined damage must differ from the pre-battle average by at least this much for
# the sample to be usable. movingAvgDamage is an INTEGER dossier record, so avg_before/avg_after
# each carry +-0.5 quantization; with a denominator of 300 the induced error in k is
# < 0.5/300 ~= 0.0017, and the median over many samples drives it lower. A near-average battle
# (tiny denominator) would blow the quotient up -- reject it.
MIN_DENOM = 300.0

# Below this many accepted samples we do NOT trust the estimate and return the caller's default
# k -- so the shipped behavior is identical to today until real evidence accrues.
MIN_SAMPLES = 8

# Ring-buffer cap on retained samples (the adapter enforces it; shared here as the constant).
SAMPLE_CAP = 200


def _is_finite(x):
    """True for a real finite float. NaN != NaN, and +-inf equals the inf literals -- both are
    rejected. Dependency-free (2/3-identical, no math.isnan/isinf)."""
    return x == x and x != float("inf") and x != float("-inf")


def observed_k(avg_before, cd, avg_after):
    """One battle's realized EWMA coefficient k = (avg_after - avg_before)/(cd - avg_before),
    or None when the sample is unusable. Rejects:
      - non-numeric / NaN / inf inputs;
      - a denominator |cd - avg_before| < MIN_DENOM (quantization blow-up near the average);
      - a numerator that moved OPPOSITE to the denominator, or not at all (avg fell on an
        above-average battle / rose on a below-average one / did not move -- a stale or
        cross-battle-contaminated read; a genuine EWMA step always moves TOWARD cd);
      - a result outside [K_MIN, K_MAX] (outlier, e.g. a first-ever battle where the moving
        average is just the single sample, k ~= 1)."""
    try:
        b = float(avg_before)
        c = float(cd)
        a = float(avg_after)
    except (TypeError, ValueError):
        return None
    if not (_is_finite(b) and _is_finite(c) and _is_finite(a)):
        return None
    denom = c - b
    if abs(denom) < MIN_DENOM:
        return None
    numer = a - b
    if numer == 0.0 or (numer > 0.0) != (denom > 0.0):
        return None
    k = numer / denom
    if k < K_MIN or k > K_MAX:
        return None
    return k


def clamp_k(k):
    """Clamp k to [K_MIN, K_MAX]; None for non-numeric / NaN / inf (so junk from disk drops)."""
    try:
        v = float(k)
    except (TypeError, ValueError):
        return None
    if not _is_finite(v):
        return None
    return K_MIN if v < K_MIN else K_MAX if v > K_MAX else v


def _median(values):
    """Median of a non-empty list of floats (mean of the two middles for an even count).
    Arithmetic only -- the `statistics` module isn't guaranteed in the 2.7 client."""
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return 0.5 * (s[mid - 1] + s[mid])


def aggregate_k(k_samples, default):
    """Robust running estimate: the caller's `default` until at least MIN_SAMPLES usable samples
    exist, else the clamped MEDIAN of the samples. Non-numeric entries are dropped defensively.
    Pure -- `k_samples` is a plain list of floats the adapter maintains."""
    vals = []
    for k in (k_samples or ()):
        v = clamp_k(k)
        if v is not None:
            vals.append(v)
    if len(vals) < MIN_SAMPLES:
        return default
    return clamp_k(_median(vals))
