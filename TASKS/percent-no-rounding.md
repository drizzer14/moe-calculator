# Research: Prevent rounding in % values (in-battle + garage widget)

_Submitted: "a clean session must prevent any rounding in % values & check whether such rounding
persists in the garage widget as well." · Status: open_

## Summary

The user wants the MoE **percent** readouts shown at full precision — no rounding/truncation
of the `%` value — so they can trust what they feel while playing battles. Confirm the same
fix covers the **garage widget**, not just the in-battle overlay. This is display-layer only:
the underlying floats reach the front-end at full precision; the widgets deliberately cut them.

## Findings — where % precision is capped today

**Wire path (no rounding here):** both bridges push the **raw float**; all `%` formatting is
in the JS.
- Garage: `bridge/gameface_bridge.py:330` — `tx.setCurPercent(model.cur_percentile)`.
- Battle: `bridge/battle_bridge.py:185` — `tx.setCurPercent(model.cur_percent)`.
- Source floats carry full precision: `cur_percentile` = `getDamageRating()` float
  (`adapter/engine_adapter.py:62`); `cur_percent` = `_interp_percent(...)` float
  (`domain/battle_builder.py:102`). No `round()` on the percent upstream. (The `int(round(...))`
  at `battle_builder.py:88` is `_ewma` for combined-damage/avg — **not** the percent.)

**In-battle overlay — `MoEBattle.js`:**
- `pctText` (lines ~46–51): `return (Math.floor(p * 100) / 100).toFixed(2) + "%";`
  → floors to **2 decimals** (e.g. 84.739 → "84.73%"). Used at line ~115 for `.mb-pct`.
- `deltaText` (lines ~54–59): `(Math.floor(Math.abs(p) * 10) / 10).toFixed(1)`
  → floors to **1 decimal** (e.g. "(+0.4%)").

**Garage widget — `MoECalculator.js` (rounding DOES persist here):**
- `pctText` (lines ~44–51): identical 2-decimal floor. Used for the current-% label
  (line ~307 `.moe-cur-pct`) and the tooltip footer (line ~271 `.moe-tt-foot-pct`).
- Tick-label cells (line ~254): `Math.round(tk.percent || 0) + "%"` — integer round, **but**
  `tk.percent` are the fixed axis positions 65/85/95 (already integers), so this is harmless;
  line ~264 hard-codes "100%". Not part of the "live %" the user is judging.

**Python `adapter/format.py`** — `percent()` / `signed_percent()` DO round (`int(round(p))`
when `decimals<=0`, else `"%.1f"`). But they appear **off the percent display path** (bridges
push floats; JS formats). `gameface_bridge.py:24` imports `format as fmt` — confirm what it's
actually used for (likely `thousands()` for damage, not the %). If unused for %, leave them; if
used, align them too.

## Suggested approach

1. Decide the target precision (see Open questions) — likely "more decimals" or "raw", applied
   consistently to `pctText` in **both** JS files (they're byte-identical copies of the helper).
2. Edit `pctText` in `MoEBattle.js` and `MoECalculator.js` together (keep them identical), and
   `deltaText` in `MoEBattle.js` to match the chosen policy.
3. Garage widget hot-reloads JS/CSS; the in-battle **window pins resources at client launch**,
   so it needs a rebuild + **relaunch** to verify (`deploy_wotmod.py … --clean-overlay`).
4. If `format.percent`/`signed_percent` turn out to be on a display path, update them too and fix
   any assertions in `tests/test_adapter.py` that pin the old rounding.

## Touch points

- `src/res/gui/gameface/mods/14th_ua/MoECalculator/MoEBattle.js` — `pctText`, `deltaText`.
- `src/res/gui/gameface/mods/14th_ua/MoECalculator/MoECalculator.js` — `pctText` (+ tick line ~254 if desired).
- `src/res/scripts/client/moe_calculator/adapter/format.py` — `percent`/`signed_percent` (only if on a display path).
- `tests/test_adapter.py` — format assertions, if Python side changes.

## Verification

- `python -m pytest -q` (Python 3) — confirm format tests still pass / update them.
- Garage: hot-reload JS/CSS, hover the bar → tooltip footer + current-% label show full precision.
- In-battle: `deploy_wotmod.py "D:/Games/World_of_Tanks_EU" 2.3.0.1 --clean-overlay`, relaunch,
  drop into a replay/battle; compare the shown % against the raw float (REPL: read
  `model.cur_percent` or the `LOG_NOTE` at `battle_bridge.py:178` which already prints `pct=%.1f`).
- The user will play battles to judge feel — leave the precision easy to re-tune.

## Open questions

- **What does "no rounding" mean concretely?** Truly raw float (many digits) reads badly; more
  likely: show more decimals, or stop *flooring* while keeping a fixed dp. Needs a user call.
- **The floor was deliberate** — `MoECalculator.js:47` comments that truncation "never overstates
  progress toward a mark threshold (84.999 → 84.99%, not 85%)." Any change must preserve that
  intent (don't round *up* past a mark). Truncating at MORE decimals satisfies both; rounding does not.
- Confirm whether `format.percent`/`signed_percent` are actually used for any displayed % (grep
  suggests not — only the `fmt` import in `gameface_bridge.py`).
