# MoE hover tooltip — handoff (WG ammo-tooltip restyle + 2x2 layout; NOW DISABLED behind a flag)

Session handoff for the **garage hover tooltip** (feature: `TASKS/hover-stats-tooltip.md`).
Built full-stack in earlier sessions. **This session** (a) reskinned it to match WG's
**ammunition / module ("blocks") tooltip** exactly, (b) reworked the content layout
(bigger title + 2x2 requirement grid + opposite-corner footer), then (c) **DISABLED the
whole tooltip behind a flag** at the user's request ("I'll come back to it later"). All
**UNCOMMITTED**. The new layout was **NOT eyeballed live** (disabled before confirming).

Env: WoT = `D:/Games/World_of_Tanks_EU`, **EU 2.3.0.1**. Py2.7 = `C:\Python27\python.exe`
(packaging); Py3.13 = `%LOCALAPPDATA%\Programs\Python\Python313\python.exe` (tests).
Front-end hot-reload: `python tools/dev/sync_gameface.py "D:/Games/World_of_Tanks_EU" 2.3.0.1`
then in-game toggle Tech Tree ↔ Garage (client may stay running; res_mods outranks the .wotmod).

## STATE RIGHT NOW — tooltip is OFF
`MoECalculator.js` has `const TOOLTIP_ENABLED = false;` (just above `ensureTooltip`).
`renderTooltip()` bails on the first line when false, so the host node is never built and no
hover listeners bind (`ensureTooltip` is reached ONLY through `renderTooltip`). The widget
bar renders normally; hovering does nothing. **To resume: flip the flag to `true`, sync,
toggle screen.** All the layout/skin code below is intact.

## WG ammo/module tooltip skin — ported verbatim (do NOT re-probe; values captured here)
Source: the client's own Gameface CSS, `mono/hangar/tooltips/tooltips.css` (`.Index_decorator`)
+ `mono/tooltips/tooltips/tooltips.css` (`.Index_title`/`.Index_body`/`.Index_separator`).
Extract pkg entries with Python `zipfile` (the harness `unzip`-wildcard trap does not apply).
- **Bubble frame:** `border-image: url(tooltip_bg.png) 4 fill / 4rem round;`
  `background-color: rgb(25,25,25);` `box-shadow: 0 0 32px rgba(15,15,15,.8);`
  `border: 4rem solid transparent;` content `padding: 14rem 20rem 18rem;`
  (This REPLACED the old components.dds `24 fill/24rem` skin + 3-layer `--hangar-highlight-shadow`.)
- **Texture** `tooltip_bg.png` = WG's `gui/maps/icons/tooltip/background_with_border.png`
  (gui-part2.pkg, 364×139): solid fill **rgb(25,25,25)**, 1px light rim **rgb(53,51,49)**,
  softly-rounded corners baked into a 4px border region. Bundled beside the CSS (border-image
  ignores `img://`/data: but paints a relative sibling — same trick as `card_border.png`).
- **Divider** `tooltip_divider.png` = WG's `gui/maps/icons/tooltip/divider.png` (gui-part1.pkg,
  624×18, faint centred dotted rule). `.moe-tt-sep`: `height:9rem; margin:4rem 0 8rem;
  background:url(tooltip_divider.png) center/contain no-repeat;`
- **Design tokens** (from `mono/lib/lib.css` + `global.css`): `--color-general-primary #ede6d9`
  (237,230,217), `secondary #b2afab` (178,175,171), `tertiary #8e867d` (142,134,125).
  Font `PFDINMax`, `letter-spacing: 0.02em`.

## Layout rework THIS session (the DOM the JS now builds)
`.moe-tt-title` → **20rem / weight 600 / #ede6d9 / opacity 0.9** (WG daily-mission/blocks title
tier; the daily_quest_tooltip.css itself only carries 18rem — its title comes from a shared
header, so we used the canonical `.Index_title` 20rem token). Then a **2x2 grid**
(`.moe-tt-grid` → two `.moe-tt-grid-row`, each two `.moe-tt-cell`) of the **four requirements**:
cells 0–2 = the three marks (65/85/95%) with the flat mark glyph `mark_1/2/3` + percentile over
required combined damage; cell 3 = the **100% goalpost** (glyph-less, `endDamageRequired`).
Reached marks brighten + get a green `✓` (`.moe-tt-cell-reached`). Divider, then a **footer**
(`.moe-tt-foot`, `justify-content:space-between`): current combined-damage LEFT (with the
widget's `DMG_ICON` at `background-size:260%`), current **%** RIGHT — opposite corners.
**Only localized text = the title** (off the model's `LABELS` bundle); everything else is
language-neutral numbers/percent + reused widget glyphs. No new i18n keys needed.

## Files touched this session (all in `src/`, uncommitted)
- `MoECalculator.css` — `#moe-tooltip` reskin (see above) + full content-style rewrite
  (title / grid / cells / footer). Removed the old `.moe-tt-row/-label/-val/-ico/-tick*` rules.
- `MoECalculator.js` — `TOOLTIP_ENABLED` flag; `ensureTooltip()` builds the new grid+footer DOM;
  `renderTooltip()` rewritten to fill 4 cells + footer (and bail when disabled).
- `tooltip_bg.png` — REPLACED content with WG's `background_with_border.png` (was the 233×212
  components.dds crop).
- `tooltip_divider.png` — NEW (WG's tooltip/divider.png).
- `tools/dev/sync_gameface.py` — ASSETS now lists `tooltip_divider.png` (user also added an
  `ASSET_DIRS = ("fonts",)` copy pass — unrelated, for the battle overlay; leave it).

Prior-session parts of this same uncommitted feature (unchanged): `adapter/i18n.py` (labels +
`_wg_text` hardening), `tests/test_i18n.py`, `bridge/view_models.py` (`labels` prop),
`bridge/gameface_bridge.py` (`_labels_json()` + push).

## Deploy state
CSS/JS + `tooltip_bg.png` + `tooltip_divider.png` **hot-reloaded** to `res_mods/2.3.0.1/…`.
Tooltip is disabled, so nothing shows in-client. The **Python label fix is still on the OLD
deployed build** — irrelevant while the tooltip is off; it must be rebuilt+deployed before the
title reads "Marks of Excellence" once re-enabled (`C:\Python27\python.exe build\deploy_wotmod.py
"D:/Games/World_of_Tanks_EU" 2.3.0.1`, client CLOSED). 43 tests pass; JS parses (`node --check`).

## NEXT (when the user returns to the tooltip)
1. Flip `TOOLTIP_ENABLED = true`, `sync_gameface.py … 2.3.0.1`, toggle screen.
2. **Eyeball the new layout live** (never confirmed): 20rem title, the 2x2 grid, opposite-corner
   footer, at the width-matched tooltip width. Likely tune knobs: grid cell font sizes (14/13rem)
   if the damage numbers crowd at our width; the 100% cell is glyph-less (text aligns to the
   reserved icon column) — give it a subtle marker if the empty slot reads odd. Fast CSS loop.
3. Rebuild+deploy Python for the label fix, relaunch, verify title = "Marks of Excellence".
4. (Gated on confirming the look) update the `wotmod-gameface-widget` skill with the "match WG's
   native ammo/module tooltip" recipe — the `background_with_border`/`divider` texture locations,
   the `4 fill/4rem round` + `0 0 32px` values, the design tokens, the sibling-PNG border-image
   trick. Ask before editing the skill.
5. **Commit** when asked. Tooltip-scoped files: `adapter/i18n.py`, `tests/test_i18n.py`,
   `bridge/view_models.py`, `bridge/gameface_bridge.py`, `MoECalculator.js`, `MoECalculator.css`,
   `tooltip_bg.png`, `tooltip_divider.png`, `tools/dev/sync_gameface.py`. (Tree also holds
   unrelated widget-polish + in-battle-panel work — scope the commit; see
   `TASKS/widget-polish-handoff.md`, `TASKS/in-battle-moe-panel.md`.)
