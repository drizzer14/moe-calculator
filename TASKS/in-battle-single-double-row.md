# Research: Single / double row mode for the in-battle overlay

_Submitted: "Single/double row mode for in-battle widget." · Status: open_

## Summary

Give the in-battle overlay two layout modes:
- **Double row (current):** a vertical stack of two lines —
  row 1 `[dmg icon] combinedDamage / projAvgDamage`, row 2 `[mark icon] curPercent (±delta)`.
- **Single row (new):** the same two metric groups laid out on ONE horizontal line
  (`[dmg icon] cd/avg   [mark icon] pct (±delta)`), for a shorter vertical footprint.

This is a layout toggle over the *same* data — no new metrics. The main open decision is
**how the mode is chosen** (dev constant vs. in-game setting); see Open questions.

## Findings — how the overlay renders today

Front-end (`MoEBattle.js` / `MoEBattle.css`, a standalone registered Gameface window — NOT the
garage sub-view inject):

- `MoEBattle.js` `ensureRoot()` (lines 71–92) builds `#moe-battle-root` containing **two
  `.mb-row` divs**: row 1 = `.mb-ico`+`.mb-cd`+`.mb-sep`+`.mb-avg`; row 2 =
  `.mb-ico`+`.mb-pct`+`.mb-delta`(`.mb-delta-num`).
- `MoEBattle.css`:
  - `#moe-battle-root` (lines 60–75) is `display: flex; flex-direction: column;` — the stack.
  - `.mb-row` (79–87) is itself `display: flex; flex-direction: row; align-items: center;
    white-space: nowrap;` with `margin-bottom: -11rem;` — a **negative pitch that overlaps the
    two rows' airy padding** (column-only concern).
  - `html, body` (45–54) is a **fixed box** `width: 340rem; height: 130rem;` — "tall enough for
    2 rows (no clip)". Comment: the window surface follows content, leftover transparent space
    still hit-tests, so "keep the box snug."
  - `#moe-battle-root { top: 27rem }` (68) nudges the readout down inside the box so its top
    lands on the tuned anchor; kept "in lockstep" with the overlay tuner.

So flipping to single-row is mostly: `flex-direction: row` on the root + kill the `.mb-row`
negative `margin-bottom` + add horizontal spacing between the two rows. The existing `.mb-row`
markup already lays out horizontally, so the two groups sit side-by-side with **no DOM rebuild**.

## Findings — the precedent to mirror (garage `carouselRows`)

The garage widget already does exactly this shape of thing: a numeric VM field drives a CSS
class the JS toggles each render — `MoECalculator.js:297`:
```js
root.classList.toggle("moe-rows2", Number(data.carouselRows) === 2);
root.classList.toggle("moe-small", !!data.carouselSmall);
```
Mirror that for the battle overlay: a `compact` (or `layoutRows`) field on the VM →
`root.classList.toggle("mb-compact", !!data.compact)` → CSS `.mb-compact` overrides.

## Findings — the data channel (`BattleMoEVM`) has a free slot

`bridge/view_models.py` `BattleMoEVM` (107–142): `__init__` passes **`properties=7`** but
`_initialize` registers only **6** properties (indices 0–5: visible, combinedDamage,
projAvgDamage, curPercent, pctDelta, hasData). **Index 6 is already allocated but unused** — a
new field can be added there WITHOUT bumping the `properties=` count (the hand-maintained-index
caveat in that file's docstring still applies: register at 6, set via `_setBool(6, v)`).

`bridge/battle_bridge.py` `push()` (242–261) writes the model into the VM inside one
`rvm.transaction()`. A `tx.setCompact(...)` call slots in here. The value would come from
`domain/constants.py` (engine-free; e.g. a new `BATTLE_COMPACT_LAYOUT = False`) — the same file
that holds `MARK_PERCENTS`, `EWMA_*`, `BATTLE_ANCHOR_*`.

## Suggested approach

Recommended (data-driven, future-proof, ~mirrors the garage): a VM field fed by a constant.

1. **Domain constant** — `domain/constants.py`: `BATTLE_COMPACT_LAYOUT = False` (single-line
   when True). One obvious toggle point; ready to be sourced from a setting later.
2. **VM field** — `view_models.py` `BattleMoEVM._initialize`: add at the spare index 6
   `self._addBoolProperty("compact", False)` + `def setCompact(self, v): self._setBool(6, v)`.
   (No `properties=` change — slot 6 already exists.)
3. **Push** — `battle_bridge.py` `push()`: inside the transaction,
   `tx.setCompact(BATTLE_COMPACT_LAYOUT)` (import the constant).
4. **JS** — `MoEBattle.js` `render()`: `root.classList.toggle("mb-compact", !!data.compact);`
   (mirror the garage `carouselRows` line). Read is a plain scalar off the root model.
5. **CSS** — `MoEBattle.css`: keep the default (column = double row) as-is; add:
   ```css
   #moe-battle-root.mb-compact { flex-direction: row; align-items: center; }
   #moe-battle-root.mb-compact .mb-row { margin-bottom: 0; }      /* kill column overlap */
   #moe-battle-root.mb-compact .mb-row + .mb-row { margin-left: 16rem; }  /* gap between groups */
   ```
   (`flex gap` is unsupported in this Coherent build — use margins, per the existing comment.)

**Minimal fallback** (if we never want it user-selectable): skip steps 1–3 and hard-code a JS
`const COMPACT = false;` at the top of `MoEBattle.js`, toggling the class off that. Less wiring,
but not drivable from Python/settings. The VM-field route is only marginally more work and keeps
the door open for a real toggle.

**Positioning coupling (must-check):** the overlay window is **bottom-flush anchored**
(`BATTLE_ANCHOR_Y = 0`) and the readout is pinned inside the box via `top: 27rem`, sized for two
rows (`html,body { height: 130rem }`). A single row is ~half as tall, so at the same `top` it
will sit HIGHER above the bottom edge than the double-row's second line did — it may no longer
align with WG's efficiency-panel corner. Expect to tune `top` (and possibly `BATTLE_ANCHOR_Y`)
for the compact case, and consider shrinking the `html,body` height so the leftover transparent
surface stays snug for the Ctrl+click passthrough (the box can be shrunk via a class on
`<html>`/`<body>` set in JS, since they're outside `#moe-battle-root`). **No hot-reload for this
window — changes need a full client relaunch to verify** (see the CSS header + memory
`in-battle-moe.md`). This overlaps **TASKS/mod-positioning.md** (same anchor/scale machinery);
coordinate so the two don't fight over `top`/anchor.

## Touch points

- `src/res/scripts/client/moe_calculator/domain/constants.py` — new `BATTLE_COMPACT_LAYOUT`.
- `src/res/scripts/client/moe_calculator/bridge/view_models.py` — `BattleMoEVM`: `compact`
  property at index 6 + `setCompact`.
- `src/res/scripts/client/moe_calculator/bridge/battle_bridge.py` — `push()`: `tx.setCompact(...)`.
- `src/res/gui/gameface/mods/14th_ua/MoECalculator/MoEBattle.js` — `render()` class toggle
  (+ optional `<body>` box-size class for the snug surface).
- `src/res/gui/gameface/mods/14th_ua/MoECalculator/MoEBattle.css` — `.mb-compact` overrides;
  possibly `top` / `html,body` height for the compact anchor.

## Verification

- Rebuild + deploy (client CLOSED — window resources pin at launch, no hot-reload):
  `& "C:\Python27\python.exe" build\deploy_wotmod.py "D:/Games/World_of_Tanks_EU" 2.3.0.1`,
  then relaunch and enter a battle (or a replay).
- Flip `BATTLE_COMPACT_LAYOUT` True/False (rebuild each time) and confirm: single-row shows both
  metric groups on one line, no clipping (`white-space: nowrap` is already set), the sign colours
  (red/white/green) still apply to the live-damage value and the delta number, and both icons
  render. Double-row must be visually identical to today.
- Confirm the readout still lands on WG's efficiency-panel corner in BOTH modes at 1× AND 2×
  interface scale (the positioning coupling above); re-tune `top`/anchor for compact if it drifts.
- `pytest` — engine-free `test_battle_builder` is unaffected (layout is bridge/VM/JS only, not
  domain); it should stay green. There is no automated coverage of the layout itself — it's an
  in-game eyeball.

## Open questions

- **How is the mode chosen?** (the real product decision)
  - (a) **Dev constant** (`BATTLE_COMPACT_LAYOUT` in `constants.py`, or a bare JS `const`) — ship
    ONE layout, changeable only by a rebuild. Simplest.
  - (b) **In-game setting** — user picks single/double live. The mod has NO settings backend
    wired, so this introduces settings plumbing from scratch (a small mod-local store, shared with
    the drag/position store in TASKS/mod-positioning.md). More work; do it as its own slice.
  - Recommend building (a) now via the VM field so the JS/VM contract is ready, then layering (b)
    on top later by sourcing the constant from a saved setting.
- Should single-row also apply to the **garage** widget, or is this in-battle-only? (Submission
  says "in-battle widget" — assumed in-battle-only.)
- Does single-row want a visual separator between the two groups (e.g. a dim `·`), or just
  whitespace?
