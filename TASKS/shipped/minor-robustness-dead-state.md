# Research: Minor robustness & dead-state batch

_Submitted: repo-wide bug hunt (2026-07-11) · Status: open_

## Summary

Low-severity latent-robustness items and one write-only dead-state field, found during the
repo-wide hunt. None fires today; grouped because each is too small for its own note but worth
not losing. Land opportunistically.

## Findings

### 1. `_clamp` passes NaN straight through
`domain/builder.py:15` and `domain/battle_builder.py:18`:
```python
lo if value < lo else hi if value > hi else value
```
For `value = NaN` both comparisons are False, so NaN returns unclamped → `fill`/`cur_percent`
propagate NaN to the widget instead of being clamped into `[0,100]`. Requires an upstream NaN
`cur_percentile`/`pre_percentile` (bad dossier read), which the adapter is unlikely to produce.
**Severity:** latent. **Confidence:** low. **Fix:** add an `value != value` (NaN) guard, or
structure the clamp as `max(lo, min(hi, value))` with a NaN check.

### 2. `positioning.efficiency_panel_wide` `zip(flags, values)` silently truncates on length mismatch
`domain/positioning.py:41` (and `:27`). If a fail-soft adapter read returns a shorter `values`
tuple than `flags`, `zip` truncates and a 5-digit total in a dropped column is never seen, so
the right-shift never fires → overlay can collide with WG's widened panel.
`damage_log_summary_hidden` is fixed-arity, so it's unaffected. The adapter returns fixed
4-tuples today. **Severity:** latent (cosmetic overlap). **Confidence:** low. **Fix:** assert/pad
to equal length, or `itertools.izip_longest` (py2) with an explicit fill.

### 3. `fetch_list.add_with_eviction` can evict a more-recently-played member than the incoming tank
`domain/fetch_list.py:70`. The new id is appended unconditionally and eviction ranks only the
*current* members, so when the list is full, adding a stale tank can drop a fresher one. In
practice "add" fires on selection/buy/battle (so the incoming tank is effectively current), so
this is a design assumption more than a clear defect. **Severity:** latent/by-design.
**Confidence:** low. **Fix (if desired):** rank the incoming id alongside members and evict the
globally-least-recent, or document the "incoming is always current" assumption.

### 4. `_temp` set is write-only dead state
`adapter/moe_wgapi.py:95,338,351,378`. `_temp` is added to in `on_vehicle_selected`, discarded
in `on_vehicle_sold`/`_promote`, but **never read** to gate anything. The header's
"selected-but-not-yet-committed TEMP set → playing a battle promotes it" semantics are
unimplemented — `on_battle_played`/`_promote` promote any int_cd regardless of `_temp`
membership. No functional effect (selection fetching is handled by `get_thresholds`), but the
state and its documented purpose are inert. **Severity:** cosmetic (dead code). **Confidence:**
high. **Fix:** either implement the intended gate (only promote tanks that were in `_temp`) or
delete `_temp` and correct the module docstring.

## Suggested approach

Drive-by fixes; can land as a single "minor robustness" commit or be cherry-picked. #1/#2 are
one-line guards; #4 is a decision (implement vs delete) then a small edit; #3 is a design call.

## Touch points

- `domain/builder.py:15` · `domain/battle_builder.py:18` · `domain/positioning.py:27,41`
- `domain/fetch_list.py:70` · `adapter/moe_wgapi.py:95,338,351,378`

## Verification

- #1: unit-test `_clamp(float('nan'), 0, 100)` → expect a clamped/finite result.
- #2: unit-test `efficiency_panel_wide` with a short `values` tuple → expect no silent miss.
- #4: unit-test that a battle in a never-selected tank does/doesn't promote, per the chosen
  semantics.

## Open questions

- #3/#4 need a design decision (are the "incoming is current" / `_temp`-gating assumptions
  intended?), not just a mechanical fix.
