# Research: Widget mispositioned over a single-row (1-level) carousel

_Submitted: "Position is wrong when carousel is 1-level, see screenshot" · Status: shipped (2026-07-06)_

> Shipped: NOT a detection bug (see CORRECTED DIAGNOSIS below). `getRowCount()` is correct.
> Fixed by CSS `vh` calibration, dialed in live: single-row (`rows=1`) `#moe-root bottom: 25.5vh`
> at 2160p (double `.moe-rows2` stays 28vh, small-double 24vh). NB the single-row base only takes
> effect when `CAROUSEL_TYPE` is truly 'single' (rows=1); with 'double' + a collapsed display the
> row count still reads 2 — a separate limitation, not re-opened here.

## ⚠️ CORRECTED DIAGNOSIS (2026-07-06, verified live via REPL) — READ FIRST
The original root-cause below (a Python detection bug in `getRowCount()`) is **WRONG**.
Live probing of the running client (`account_helpers.settings_core.options`) shows:
- `CAROUSEL_TYPE` options = `('single','double')`; `getRowCount()` = **stored index + 1**
  (single→1, double→2) — a **pure, stable** function of the setting, NOT view-timing-sensitive.
- `DOUBLE_CAROUSEL_TYPE` options = `('adaptive','small')`; `enableSmallCarousel()` = (index==small)
  — also pure/stable.
- With the setting on `'double'`, the garage **actually shows 2 rows** and the log reads a
  **stable `rows=2`** (no 1↔2 flapping this session). So detection faithfully tracks the display.

The old log's `rows=1 ×8` were the `except: return 1, False` **fallback** firing in transient
windows (early/teardown pushes before settings-core was ready), not `getRowCount()` misbehaving.

**Real issue = CSS `vh` calibration** of `#moe-root`'s bottom offsets. The user confirmed
(setting=double, 2 rows) the bar sits **too low / overlapping** at `bottom:28vh` (`.moe-rows2`);
the original "single-row floats too high" is the `20vh` single case being over-lifted. Fix =
recalibrate the three offsets (`:20` single 20vh, `:102` rows2 28vh, `:103` rows2.small 24vh),
verified live. The Python `_carousel_geometry()` needs no change (optional: read the stable
`core.getSetting(...)` values instead of the option objects to shrink the transient-fallback
window). Everything below is the superseded original analysis.

## Summary
With a **single-row** vehicle carousel, the MoE widget floats too high above the carousel
(large gap). Root-caused from the live client log: the widget's carousel-row **detection is
wrong** — it reports the carousel as **2 rows** almost always, even though it's visually a
single row — so the CSS applies the taller-carousel lift (`bottom: 28vh`) instead of the
single-row lift (`20vh`). This is a **Python detection bug**, not a CSS-value calibration
issue.

## Findings — the position mechanism
- `#moe-root` anchors bottom-right with a responsive bottom offset switched by two classes:
  - base (single row): `bottom: 20vh` (`MoECalculator.css:20`)
  - `.moe-rows2` (double row): `bottom: 28vh` (`:102`)
  - `.moe-rows2.moe-small` (short double row): `bottom: 24vh` (`:103`)
- JS sets those classes from the pushed data (`MoECalculator.js:159-160`):
  ```js
  root.classList.toggle("moe-rows2", Number(data.carouselRows) === 2);
  root.classList.toggle("moe-small", !!data.carouselSmall);
  ```
- `carouselRows` / `carouselSmall` come from Python `_carousel_geometry()`
  (`bridge/gameface_bridge.py:243-256`):
  ```py
  rows  = int(core.options.getSetting(sc.GAME.CAROUSEL_TYPE).getRowCount())
  small = bool(core.options.getSetting(sc.GAME.DOUBLE_CAROUSEL_TYPE).enableSmallCarousel())
  return rows, small          # except -> return 1, False
  ```
  `push()` logs the value each time (`gameface_bridge.py:306`, `rows=%d`).

## Root cause (from the live log — `D:/Games/World_of_Tanks_EU/python.log`)
While the carousel is a single row on screen, the pushed value is overwhelmingly `rows=2`:
- **`rows=2` × 277 vs `rows=1` × 8** across this session's pushes.
- A grep for `_carousel_geometry` / `getRowCount` / `CAROUSEL_TYPE` finds **no tracebacks**,
  so the `except: return 1, False` fallback is NOT firing — `getRowCount()` is *succeeding*
  and returning **2** for a single-row carousel.
- Consecutive pushes seconds apart flip between values (e.g. `20:07:01 rows=1` →
  `20:07:02 rows=2`), so the read is also **unstable**, making the widget jump between the
  20vh and 28vh positions; it mostly rests on the wrong `rows=2` → `28vh` (too high).

Conclusion: `sc.GAME.CAROUSEL_TYPE.getRowCount()` does **not** reflect the actual displayed
row count — it reports 2 for this single-row carousel. So `.moe-rows2` is wrongly applied and
the bar gets the double-row lift. (The CSS values themselves may still want a later tune, but
they are not the bug.)

## Suggested approach
Fix the detection so a single-row carousel reads `rows=1`. Because `getRowCount()` returns the
wrong thing here, confirm the correct signal **live via the debug REPL** (see the
`wotmod-debug-repl` harness skill) against the running client, single-row carousel active:
- Inspect what `core.options.getSetting(sc.GAME.CAROUSEL_TYPE)` actually is and what
  `getRowCount()` returns vs. the visible rows. It may report the *maximum*/type default (2),
  not the current display.
- Check the **double-carousel enable** signal instead: in WoT the second row is the
  "double carousel" feature. Reading whether double-carousel is *enabled* (a bool) — rather
  than a row count — likely maps cleanly to 1 vs 2 rows. `DOUBLE_CAROUSEL_TYPE` is already
  read for `small`; verify whether it (or a sibling setting / `isDoubleCarousel`-style flag)
  is the real single-vs-double switch, and derive `rows = 2 if double_enabled else 1`.
- As a more robust alternative, read the **actual carousel view/component geometry** (the
  live carousel's row count or pixel height) rather than a settings preference, so the widget
  tracks what's really on screen even if the setting and display disagree.
- Also address the **instability**: whatever is read should be consistent across the refresh
  bursts (the current value flapping 1↔2 is itself a symptom that the read is context/timing
  sensitive — a stable source removes the position jitter).

Once detection is correct, re-verify the three CSS offsets (20/24/28vh) still look right for
each carousel mode (they were calibrated while detection was feeding the wrong class, so the
single-row 20vh in particular is currently unverified in practice).

## Touch points
- `bridge/gameface_bridge.py` — `_carousel_geometry()` (`:243-256`); possibly
  `_on_settings_changed()` (`:76-88`) if the watched settings change.
- `MoECalculator.js` — the class toggle (`:159-160`) if the wire field changes shape.
- `MoECalculator.css` — offsets (`:20`, `:102`, `:103`) for a follow-up calibration pass.
- Wire contract: `carouselRows`/`carouselSmall` in `view_models.py` (MoEVM properties 7/8) if
  the semantics change (e.g. switching to a boolean).

## Verification
- Live log: with a single-row carousel, `[moe] push … rows=1` consistently (no 1↔2 flapping);
  with double carousel, `rows=2`. Toggle the carousel setting and watch the log + widget move.
- Visually: the bar sits just above the carousel in BOTH single and double modes, no large gap.
- The debug REPL confirms the chosen API returns 1 for single / 2 for double before coding it.

## Open questions
- What is the correct client API for the *displayed* carousel row count? (Confirm via REPL /
  decompiled source — `getRowCount()` is demonstrably not it.)
- Should the wire field become a boolean `doubleCarousel` (cleaner) rather than a row count?
