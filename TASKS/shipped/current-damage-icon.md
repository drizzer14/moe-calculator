# Research: Damage icon on the current-damage readout

_Submitted: "Add damage icon to current damage" · Status: shipped (2026-07-06)_

> Shipped: icon added, then moved to the RIGHT of the number and enlarged per user. The user
> picked `personal_missions_30/quest_type/64x64/icon_battle_condition_damage.png` (not the
> recommended dossier glyph below). A follow-up size tweak is tracked in
> `TASKS/damage-icon-size.md` (the chosen art's glyph fills only ~¼ of its canvas).

## Summary
Put a small damage glyph next to the current average combined-damage number (the top-left
readout), so it reads as "⚔ 3,015" rather than a bare number.

## Findings — where the number lives now
Round 4/5 split the readout: `.moe-cur` now holds **only** the damage number, and the
current-% moved out to the bar's 100%-end label.
- Markup (`MoECalculator.js:81-86`): `.moe-head > .moe-cur > .moe-cur-dmg`. The damage text is
  set in `render()` via `thousands(dmg)` on `.moe-cur-dmg`.
- `.moe-head` is `display:flex` anchored top-left (`MoECalculator.css:112-116`); `.moe-cur` is
  the text container (`font-size:16rem; font-weight:400`, `:130-134`); `.moe-cur-dmg` is white
  (`:135`).
- The widget already renders `img://` game-art as `background-image` (the mark glyphs —
  `FLAT_MARK`, `markIcon()` — and per `wotmod-gameface-widget`, `img://` paints in
  `background-image` and `mask-image`). So a client damage icon can be referenced directly, no
  bundling.

## Candidate icon assets (found in `gui-part{1..4}.pkg`)
The number is `movingAvgDamage` (average combined damage), so the dossier average-damage glyph
is the natural semantic match:
- **`img://gui/maps/icons/library/dossier/avgDamage40x32.png`** — recommended (avg-damage stat
  icon, 40×32 ≈ 1.25:1, sized for inline text).
- Alternates to eyeball in-game: `library/efficiency/48x48/damage.png`,
  `eventBoards/tableIcons/damage.png`, `buttons/tab_sort_button/damage.png`,
  `achievements/summary/kpi/small/damage.png`.
(There are also `sibling` dossier glyphs — `avgAttackDmg40x32`, `avgDefenceDmg40x32`,
`dmgRatio40x32` — if a more specific icon is wanted.)

## Suggested approach
- **DOM:** add `<span class="moe-cur-icon"></span>` before `.moe-cur-dmg` in `ensureRoot()`
  (`MoECalculator.js:84`). Static, so it belongs in the one-time markup, not `render()`.
- **CSS:** new `.moe-cur-icon` — an inline glyph sized to the 16rem text:
  ```css
  #moe-root .moe-cur-icon {
      display: inline-block;
      width: 18rem; height: 15rem;          /* ~text height, 40x32 aspect */
      margin-right: 5rem;
      vertical-align: -2rem;                /* nudge onto the text baseline */
      background: url(img://gui/maps/icons/library/dossier/avgDamage40x32.png) no-repeat center / contain;
  }
  ```
  (`.moe-head` is flex; if baseline alignment is fussy, set `.moe-head { align-items:center }`
  or align the icon via flex instead of `vertical-align`.)
- **Tint (only if needed):** if the chosen icon's built-in colour clashes with the cream text,
  tint it to `#ede6d9` with the mask technique WG-matching already uses elsewhere — swap
  `background: url(...)` for `background-color:#ede6d9; mask-image:url(img://…); mask-repeat:no-repeat;
  mask-size:contain;` (Coherent honours `mask-image`; see the visual-polish memory / handoff).
- Keep the icon `pointer-events:none` inheritance (it's inside the hover-capturing box; it
  doesn't extend past it, so no special handling needed).

## Touch points
- `MoECalculator.js` — `ensureRoot()` markup (`:81-86`).
- `MoECalculator.css` — new `.moe-cur-icon`; maybe `.moe-head align-items` (`:112`).

## Verification
- Live in-client: icon sits left of the damage number, vertically centred on the text, crisp
  at this UI scale over a bright hangar; colour reads with the cream number (tint if not).
- Confirm the chosen `img://` path actually resolves (a wrong path renders blank — try the
  recommended one first; the widget's existing mark glyphs prove `img://` works here).

## Open questions
- Which icon — the recommended `avgDamage40x32`, or a different damage glyph (eyeball a few)?
- Icon left of the number (assumed) — or somewhere else?
- Keep the icon its native colour, or tint it to match the cream text?
