# Ideas backlog

Short, one-line entries for future features and bug reports. The **wotmod-planner**
skill researches each submission against the codebase and saves an implementer-ready
note under `TASKS/`; delete an entry here once it ships.

## Open

### Add in-battle MoE info (into the damage-log panel)
Big feature — the mod is garage-only today. Now LIVE: res_map-registered Gameface WINDOW over the
HUD, real data, input-steal fixed, real MoEBattle font (extracted from fontlib.swf) loading,
px/rem recalibrated, approximation stripped. **Visual tune DONE** — checker regen'd to 2px cells
(fine dither), backdrop reworked to a fixed two-layer stack (background gradient + clip under the
dots dither), `-webkit-mask` stripped (WG uses unprefixed `mask`), final CSS deployed. Remaining:
live-battle metric sanity check (replay baseline empty = BUG B) + **COMMIT** (whole feature +
garage/tooltip/widget-polish all still UNCOMMITTED). Full current state: memory `in-battle-moe.md`.
→ Styling handoff (broader state): TASKS/in-battle-moe-styling.md
→ Live findings + BUG B (empty replay baseline): TASKS/in-battle-moe-handoff.md
→ Checker dither fix (shipped this session): TASKS/shipped/in-battle-checker-squares.md
→ Mount rework (done): TASKS/in-battle-moe-mount-rework.md · Original design: TASKS/in-battle-moe-panel.md

### Prevent rounding in % values (in-battle + garage)
The MoE percent readouts cap precision at the display layer (both widgets floor to 2 decimals in
their JS `pctText`; the delta floors to 1). The raw floats reach the front-end intact — the cut is
purely cosmetic. Show full precision so battle "feel" is trustworthy; confirm the garage widget
gets the same fix. Keep the deliberate *truncate-don't-round-up* intent (never overstate a mark).
→ Research: TASKS/percent-no-rounding.md

### Refine mod positioning — drag-and-drop + scale/screen/log-aware defaults
Both surfaces are hardcoded viewport anchors today (`MoEBattle.css` `13.8vw/78.8vh`;
`MoECalculator.css` `2.4vw/25.5vh` + a carousel-row nudge). Wanted: (1) drag-and-drop the
in-battle panel with persisted position; (2) auto-default the in-battle position from the
damage-log settings + screen size + interface scale; (3) screen-size + interface-scale
awareness for the garage widget too. Key finding: `vw/vh` already neutralizes *resolution*
(fullscreen window) but NOT *interface scale* (`settingsCore.interfaceScale.get()`), and the
damage-log panel exposes **no** position API (Flash — must calibrate empirically). Splits into
3 slices (scale-correctness → log-aware default → drag+persistence). Drag needs a new reverse
channel (VMs are read-only) + a settings store (ModsSettingsAPI?). Cross-refs the in-battle
styling handoff (anchor, no-hot-reload, prior input-steal fix, reuse the overlay tuner to calibrate).
→ Research: TASKS/mod-positioning.md

### Hover tooltip — full stats breakdown (localized, with icons)
On widget hover, show a tooltip breaking down all MoE stats as rows of icon + localized label
+ value. First feature needing user-facing text → introduces the mod's localization plumbing
(`adapter/i18n.py` bundled dict + `helpers.getClientLanguage`, push a `labels` JSON bundle on
the VM). Mostly re-presents existing VM fields. Reusable how-to now lives in the harness
(wotmod-gameface-widget → Tooltips + Localization; wotmod-architecture → Localization).
→ Research: TASKS/hover-stats-tooltip.md
