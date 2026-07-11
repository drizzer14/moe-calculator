# Research: MoE estimator single-sample prior emits absurd thresholds near its singularity

_Submitted: repo-wide bug hunt (2026-07-11) · Status: open_

## Summary

The offline threshold estimator's single-sample prior can silently produce grossly inflated
mark thresholds (~10k–40k combined damage for 1 mark, vs. a realistic ~1000–2000) for a
low-percentile tank. The values are wrong but *ordered*, so the only sanity gate
(`_targets`, "positive & strictly ascending") lets them through and the widget displays them.

## Root cause

`domain/moe_estimate.py:138-152` `_prior_mu_sigma`:

```python
z0 = inv_norm_cdf(p0)
denom = 1.0 + UNIVERSAL_CV * z0          # UNIVERSAL_CV = 0.8079
if denom <= _DENOM_EPS:                  # _DENOM_EPS = 1e-3
    return None
mu = d0 / denom
```

The guard only refuses the *exact* collapse (`denom <= 1e-3`). `denom` hits zero at
`z0 = -1/0.8079 ≈ -1.238`, i.e. `p0 = Phi(-1.238) ≈ 0.108`. For a percentile just **above**
that boundary `denom` is a tiny positive number, so `mu = d0/denom` blows up. `_targets`
(`moe_estimate.py:155-170`) then scales `mu, sigma=CV*mu` out to the 65/85/95/99 percentiles;
because everything scales from the same inflated `mu` the outputs stay positive and ascending,
so the `if v <= 0 or v <= prev: return None` check passes.

Worked example — one sample `(d0=400, p=0.12)`:
- `z0 ≈ -1.175`, `denom ≈ 0.051`, `mu ≈ 7890`, `sigma ≈ 6374`
- `out[1] = mu + sigma·z(0.65) ≈ 10344`, `out[3] ≈ 18375`

At `p=0.11` `out[1]` exceeds 40000; by `p ≈ 0.20` the math is back to sane (`out[1] ≈ 1600`).
The blow-up band is roughly `p0 ∈ (0.108, 0.14)` — narrow, but a genuinely reachable
percentile for a weak player on a weak tank.

## Reachability

The estimator is the **error-fallback** path: `adapter/engine_adapter.get_estimated`
(engine_adapter.py ~:71 builds the `(damage, percentile/100.0)` fraction contract) calls
`thresholds_from_samples` when the WG-API fetch has no data for the tank
(`moe_wgapi.needs_estimate` True). Single-sample means a tank with one usable
`(movingAvgDamage, damageRating)` point — a freshly-played tank, or one with only one sample.
Combined with a low `damageRating`, the estimate is served whenever the WG API path fails
(see the companion note on the no-retry trap, [[wgapi-fetch-retry-robustness]], which makes
the fallback fire for a whole session on one transient error — widening this bug's blast radius).

## Suggested approach

Add an upper plausibility bound before accepting the prior's output — either:
- clamp/refuse when `mu` (or `out[1]`) exceeds a sane ceiling (e.g. a few × `d0`), or
- raise `_DENOM_EPS` well above `1e-3` so the whole low-`p0` danger band falls back to `None`
  (→ `{}` → bar shows bare ticks, no wrong labels), or
- add a magnitude check to `_targets` (reject when any threshold is an implausible multiple of
  the input damage).

Refusing (returning `None`/`{}`) is safer than displaying a wrong number: the widget already
degrades gracefully to no-per-mark-labels.

## Touch points

- `domain/moe_estimate.py:138-152` (`_prior_mu_sigma`), `:155-170` (`_targets` gate)
- `domain/constants.py` (`GOALPOST_PERCENTILE`, `MARK_PERCENTS`)

## Verification

- Unit test the untested mid-low band: `thresholds_from_samples([(400, 0.12)])`,
  `[(x, 0.11)]`, `[(x, 0.13)]` — assert the result is `{}` (or bounded), not 5-figure. The
  existing suite only probes `p=0.02` (refused) and `p=0.80` (fine); the dangerous band has
  **no coverage**.
- In-client: hard to force (needs WG-API failure + a single-sample low-percentile tank);
  the unit test is the real gate.

## Open questions

- What ceiling is "plausible"? Needs a value judgement — a multiple of the sample damage
  (e.g. `out[3] <= 6·d0`) is simple and defensible, but confirm against the derive-prior data
  (`tools/dev/derive_moe_prior.py`) if it still exists.
