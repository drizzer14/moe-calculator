# Research: In-battle MoE % reads ~1.5% low vs the post-battle actual

_Submitted: "In-battle calculations are incorrect, they're off by ~1.5 percent (lower) than the actual moe percent when viewing it after battle." · Status: open (needs one live/replay probe to confirm which mechanism dominates)_

## Summary

The in-battle overlay's current MoE % lands ~1.5% **below** the value WG shows for the same tank
after the battle (the garage widget's number). The gap is small and consistent — the signature of
a **systematic mapping/curve difference**, not a random read error. The structural cause: the
in-battle % and the "actual" % are computed from **two different percentile sources** that were
never reconciled.

## Findings — the two percentile sources (the crux)

**Garage / "actual" % = WG's own damage rating.** `engine_adapter._read_moe()` reads
`mog.getDamageRating()` straight from the vehicle dossier (`adapter/engine_adapter.py:63-66`) —
WG's real, stored MoE percentile (already ÷100, e.g. `84.7`). The garage widget shows this
verbatim; it's also what the dossier shows post-battle.

**In-battle % = the mod's OWN interpolation.** `build_battle_model()` computes
`cur_percent = _interp_percent(proj, stops)` (`domain/battle_builder.py:102`), i.e. it maps the
projected combined-damage `proj` through a **piecewise-linear** curve built from the external
threshold table (`_threshold_stops`, `battle_builder.py:32-55`):
`(0,0) (D1,65) (D2,85) (D3,95) (D100,100)`.

These are **different functions of damage**: WG's `damageRating` distribution vs the mod's linear
interpolation over the tomato.gg/`moe_data` thresholds (a *different population* sample). Even fed
the identical avg damage they disagree by a percent or two through the mid-range — exactly the
observed ~1.5%.

### Contributing mechanisms (all push the in-battle number DOWN)

1. **Two mismatched curves (dominant, structural).** interp-over-external-table vs
   `getDamageRating()`. The delta `pct_delta = cur_percent - pre_percentile`
   (`battle_builder.py:103`) is itself contaminated: `cur_percent` is interp-based but
   `pre_percentile` is WG-rating-based, so the baseline and the live value are on different scales.

2. **The `cd=0` fold at battle start.** `ewma_project(pre_avg, cd)` =
   `round(pre_avg + k*(cd - pre_avg))` (`battle_builder.py:84-88`). With `cd=0` early in a battle,
   `proj ≈ pre_avg*(1-k) = pre_avg*0.980` — the projected avg starts ~2% **below** career avg. On
   the mid-percentile slope (~20 percentile points across the D1→D2 damage span) a ~2% avg drop is
   ≈ **1–1.5 percentile points low** — matching the report. As real damage accrues `proj` climbs,
   but if the display is read before `cd` overtakes `pre_avg` (or in a below-avg battle) it stays low.

3. **EWMA `k` is a guess.** `EWMA_K = 2/(100+1) ≈ 0.0198` is explicitly
   "community-reverse-engineered, NOT WG-confirmed" (`domain/constants.py:23-28`). If WG's real
   moving-average step is larger, an above-average battle under-projects → low.

4. **Combined-damage approximation** (secondary; direction ambiguous). `combined_damage` uses
   `max(assist, stun)` not the sum, live `assist` merges spot+track, and `team_damage` is hard-wired
   to 0 (`battle_adapter.py:78-92`, `battle_builder.py:22-29`, `battle_adapter.py:208`). Documented
   caveat; can over- OR under-count, so probably not the source of a *consistent low* bias, but rule
   it out with the probe.

## Root cause

Not a single arithmetic bug — a **basis mismatch**: the live overlay estimates the percentile from
a linear interpolation of an external threshold table + a guessed EWMA, while "actual" is WG's own
`getDamageRating()`. The two are ~1.5% apart in the operating region, and mechanism #2 (the cd=0
start-fold) plausibly accounts for most of that on its own.

## Suggested approach

**First, isolate AVG-error vs MAPPING-error with one probe** (don't guess which dominates):
- In a replay, log at battle START and END: the mod's `proj` and `cur_percent`, alongside WG's
  real `movingAvgDamage` and `getDamageRating()` from the dossier for the same tank (the garage
  reads both — `engine_adapter.py:66-68`). Compare:
  - if `proj` tracks WG's `movingAvgDamage` but `cur_percent` ≠ `getDamageRating()` → **mapping**
    error (stops vs WG curve) — fix the percentile function / anchor (below).
  - if `proj` itself lags WG's `movingAvgDamage` → **EWMA/k or the cd=0 fold** — fix the projection.

**Most promising fix — anchor the live % to WG's real baseline and add only the battle's increment**
(cancels the constant offset regardless of which curve is "right"):
```
cur_percent = pre_percentile + (interp(proj) - interp(pre_avg))
```
At battle start `proj≈pre_avg` → `cur_percent≈pre_percentile` = WG's actual (no offset); as the
battle improves `proj`, the interp *increment* is added. This reuses the same threshold curve for
the delta only, where its absolute bias cancels. (`pre_percentile`/`pre_avg` already flow through
the snapshot — `battle_adapter.py:190-209`.) `pct_delta` then becomes `interp(proj)-interp(pre_avg)`.

**Also fix the cd=0 start-fold**: don't fold a zero/partial battle until there's real activity, or
seed `proj = pre_avg` until `cd > 0`, so the readout opens exactly at the career value.

**Optionally revisit `k`** only if the probe shows `proj` lagging WG's `movingAvgDamage` — try
fitting `k` from a few replays rather than assuming `N=100`.

## Touch points
- `src/res/scripts/client/moe_calculator/domain/battle_builder.py` — `build_battle_model` (91-113),
  `ewma_project` (84-88), `_interp_percent`/`damage_to_percent` (58-81). The fix lives here (pure,
  unit-testable — add cases to `tests/test_battle_builder.py`).
- `src/res/scripts/client/moe_calculator/domain/constants.py:27-28` — `EWMA_N`/`EWMA_K` (only if #3).
- `src/res/scripts/client/moe_calculator/adapter/battle_adapter.py` — `_read_efficiency` (78-92) and
  the snapshot (177-217) if the combined-damage components (#4) turn out to matter.
- Reference (do NOT change): `adapter/engine_adapter.py:63-68` — WG's `getDamageRating()` +
  `movingAvgDamage`, the "actual" the overlay should reconcile to.

## Verification
- Unit: with `snapshot.pre_percentile=84.7`, `pre_avg=proj` (no battle yet) → `cur_percent==84.7`
  (anchored, was interp(pre_avg)≈83.x); a known good battle raises it by the interp increment.
- Replay probe (above) at start + end; confirm the overlay's end-of-battle % now matches the garage
  dossier % for that tank within rounding.
- No hot-reload for the battle WINDOW — rebuild + relaunch with the client CLOSED
  (`build/deploy_wotmod.py`); see `TASKS/shipped/in-battle-moe-styling.md`.
- `pytest` (currently ~50 tests) stays green.

## Open questions
- Is the ~1.5% roughly **constant** across tanks/percentile ranges (→ pure mapping offset, anchor
  fix nails it), or does it **grow with how far the battle moved the avg** (→ EWMA/k)? The probe
  answers this and decides how much of the fix is needed.
- Does the user compare the overlay against the **garage widget** number or WG's **native**
  post-battle results screen? (Both trace to `getDamageRating()`, so the fix is the same, but worth
  confirming the exact reference.)

## Cross-references
- `domain/constants.py:23-28` — the EWMA_K "NOT WG-confirmed" caveat.
- `TASKS/shipped/in-battle-moe-panel.md` — the original four-readout design + the combined-damage
  approximation notes. `TASKS/shipped/in-battle-moe-handoff.md` — live findings incl. latent
  BUG B (empty-replay baseline), which can masquerade as a wrong percent if the baseline is missing.
- `[[in-battle-moe]]`, `[[wulf-setnumber-int-cast]]` (a *separate*, already-fixed rounding cause).
