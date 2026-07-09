# Research: In-battle overlay — LTR (current) / RTL layout direction

_Submitted: "In-battle widget layout - ltr (current), rtl (to do)." · Status: open_

## Summary

The in-battle overlay is built left-to-right: each row is `[icon] [value…]`, the stack is
left-aligned, its soft backdrop fades in from the LEFT edge, and the window is anchored to the
screen's bottom-LEFT (tracking WG's efficiency panel there). Add an **RTL mode** that mirrors
this: `[…value] [icon]`, right-aligned, backdrop fading from the RIGHT, and (likely) anchored to
the bottom-RIGHT. LTR stays the default.

Same shape of feature as the single/double-row toggle (TASKS/in-battle-single-double-row.md):
a flag on the VM → a CSS class the JS toggles → CSS overrides. The two are independent axes
(rows × direction) and should share the same wiring; **coordinate the VM property slot** (see
Findings). The window-side mirroring couples with TASKS/mod-positioning.md.

## Findings — what is LTR-specific today

`MoEBattle.css`:
- `#moe-battle-root` (60–75): `left: 0; display: flex; flex-direction: column;` — implicitly
  left-aligned (items stretch/start at the left).
- `.mb-row` (79–87): `flex-direction: row` → `[icon][value]…` order; `padding: 8rem 32rem`.
- `.mb-ico` (137–148): `margin-right: 4rem` (icon→value gap, physical LEFT-side).
- `.mb-sep, .mb-value.mb-avg, .mb-delta` (151–155): `margin-left: 4.5rem` (physical spacing).
- Backdrop is **left-biased**:
  - `.mb-row::before` dither `mask: radial-gradient(223% 120% at 29% 50%, #000 0%, transparent 22%)`
    (110) — blob centered LEFT of middle.
  - `.mb-row::after` gradient underlay `mask: linear-gradient(90deg, transparent 13%, #000 22%)`
    (127) — soft-clips the LEFT edge (fades in from left).

`bridge/battle_view.py` `_place()` + `domain/constants.py`:
- Window anchored bottom-LEFT: `BATTLE_ANCHOR_X = 264` measured **from the LEFT edge**;
  `move(x, y, xAnchor=PositionAnchor.LEFT, yAnchor=PositionAnchor.TOP)` after self-calibrating the
  movable extent (`domain.positioning.anchor_top_left`). Y is from the bottom.

`MoEBattle.js` `ensureRoot()` (71–92): DOM order is icon-first in both rows.

## Findings — the VM channel (coordinate with the row-mode task)

`bridge/view_models.py` `BattleMoEVM`: `properties=7`, only 6 registered (0–5) → **one spare
slot (index 6)**. The single/double-row task plans to take slot 6 for a `compact` flag. **RTL
would then need slot 7 → bump `properties=7` to `8`** and register `rtl` at index 7. If both
features are built together, add both properties in one change and bump the count once. (The
hand-maintained-index caveat in that file's docstring applies: register in order, set via the
matching `_setBool(i, v)`.)

## Suggested approach

Front-end mirror driven by a `rtl` flag, plus a right-side window anchor. Pure CSS for the
content; a small Python change for the anchor.

1. **VM + push** (mirror the garage `carouselRows`/`carouselSmall` pattern, and the row-mode
   task): `BattleMoEVM` add `rtl` bool (index 7, bump `properties`→8) + `setRtl`; `battle_bridge`
   `push()` writes `tx.setRtl(BATTLE_RTL_LAYOUT)`; new `domain/constants.py` `BATTLE_RTL_LAYOUT`.
2. **JS** `render()`: `root.classList.toggle("mb-rtl", !!data.rtl);` (next to the `mb-compact`
   toggle). No DOM reorder needed — do it in CSS.
3. **CSS** `.mb-rtl` overrides (keep LTR as the untouched default):
   ```css
   #moe-battle-root.mb-rtl              { align-items: flex-end; }      /* right-align the stack */
   #moe-battle-root.mb-rtl .mb-row      { flex-direction: row-reverse; }/* [value…][icon] */
   #moe-battle-root.mb-rtl .mb-ico      { margin-right: 0; margin-left: 4rem; }
   #moe-battle-root.mb-rtl .mb-sep,
   #moe-battle-root.mb-rtl .mb-value.mb-avg,
   #moe-battle-root.mb-rtl .mb-delta    { margin-left: 0; margin-right: 4.5rem; }
   /* mirror the backdrop to fade in from the RIGHT */
   #moe-battle-root.mb-rtl .mb-row::before { mask: radial-gradient(223% 120% at 71% 50%, #000 0%, transparent 22%); }
   #moe-battle-root.mb-rtl .mb-row::after  { mask: linear-gradient(90deg, #000 78%, transparent 87%); }
   ```
   - `flex gap` is unsupported here (existing comment) → margins, hence the explicit L/R flips.
   - `.mb-delta` holds static parens `(<num>)`; `row-reverse` keeps them intact (they're one
     inline span), so no parens-mirroring issue.
   - **Shortcut to TEST, not assume:** `#moe-battle-root.mb-rtl { direction: rtl; }` may auto-flip
     flex main-axis, text-align, and logical margins in one line — BUT Coherent/Gameface support
     for `direction: rtl` is unverified and several CSS features silently drop in this engine (see
     wotmod-gameface-widget quirks). Try it in the tuner; if it doesn't fully mirror, fall back to
     the explicit overrides above (which are known-good primitives).
4. **Window anchor (positioning)** — for a true right-side overlay, place from the RIGHT edge:
   either `move(..., xAnchor=PositionAnchor.RIGHT)` with an X measured from the right, or reuse
   the self-calibrated movable extent and place at `max_x - BATTLE_ANCHOR_X` (a right-measured
   offset). This is the piece that overlaps **TASKS/mod-positioning.md** — do it there or in
   lockstep so the two don't fight over the anchor. **Open:** does RTL also reposition to the
   right, or only mirror the content in place on the left? (See Open questions — decide first.)

## Touch points

- `src/res/scripts/client/moe_calculator/domain/constants.py` — `BATTLE_RTL_LAYOUT` (+ a
  right-anchor constant if RTL moves to the right edge).
- `src/res/scripts/client/moe_calculator/bridge/view_models.py` — `BattleMoEVM`: `rtl` property
  (index 7, `properties`→8) + `setRtl`. **Coordinate with the row-mode task's slot 6.**
- `src/res/scripts/client/moe_calculator/bridge/battle_bridge.py` — `push()`: `tx.setRtl(...)`.
- `src/res/gui/gameface/mods/14th_ua/MoECalculator/MoEBattle.js` — `render()` class toggle.
- `src/res/gui/gameface/mods/14th_ua/MoECalculator/MoEBattle.css` — `.mb-rtl` overrides.
- `src/res/scripts/client/moe_calculator/bridge/battle_view.py` + `domain/positioning.py` — the
  right-edge anchor, IF RTL repositions (couples with mod-positioning).

## Verification

- Preview the mirrored content in the **overlay tuner** (`tools/dev/gen_overlay_tuner.ps1` →
  `TASKS/refs/in-battle-overlay-tuner.html`) — no hot-reload for this window, so iterate there
  first. Check the `direction: rtl` shortcut vs the explicit overrides.
- Rebuild + **relaunch** (client CLOSED):
  `& "C:\Python27\python.exe" build\deploy_wotmod.py "D:/Games/World_of_Tanks_EU" 2.3.0.1`.
- Flip `BATTLE_RTL_LAYOUT` and confirm in battle/replay: row order mirrored (`value…icon`), stack
  right-aligned, backdrop fades from the right, spacing correct, sign colours/glow still apply,
  and — if repositioned — the panel sits at the intended right-side corner at 1× AND 2× scale.
  LTR must be byte-for-byte unchanged.
- `pytest` unaffected (layout is bridge/VM/JS/CSS; the engine-free domain is untouched — unless
  a right-anchor helper is added to `domain/positioning.py`, in which case add a unit test there).

## Open questions

- **Does RTL also move the panel to the bottom-RIGHT, or only mirror the content in place?** This
  is the key call — it decides whether the Python/positioning change is in scope or whether RTL is
  purely a CSS content-mirror on the same left anchor. (Mirroring in place on the left looks odd;
  a right-side panel is the usual intent — confirm.)
- **How is the mode chosen?** Same fork as the row-mode task: dev constant now vs an in-game
  settings toggle later. Recommend the VM-flag + constant now; layer settings later.
- Combine with the single/double-row task into ONE layout change (shared VM slot allocation and
  one relaunch), or keep them as separate slices? They touch the same files.

## Cross-references

- `TASKS/in-battle-single-double-row.md` — sibling layout toggle; SHARES the VM-flag/CSS-class
  wiring and the VM property-slot budget (that task takes slot 6, this one slot 7).
- `TASKS/mod-positioning.md` — the anchor/scale machinery; owns the right-edge reposition.
- `TASKS/shipped/in-battle-moe-styling.md` — the overlay tuner + no-hot-reload constraint.
