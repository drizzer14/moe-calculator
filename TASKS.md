# Ideas backlog

Short, one-line entries for future features and bug reports. The **wotmod-planner**
skill researches each submission against the codebase and saves an implementer-ready
note under `TASKS/`; delete an entry here once it ships.

## Open

### Refine mod positioning — drag-and-drop + scale/screen/log-aware defaults
Both surfaces are hardcoded viewport anchors today (`MoEBattle.css` `13.8vw/78.8vh`;
`MoECalculator.css` `2.4vw/25.5vh` + a carousel-row nudge). Wanted: (1) drag-and-drop the
in-battle panel with persisted position; (2) auto-default the in-battle position from the
damage-log settings + screen size + interface scale; (3) screen-size + interface-scale
awareness for the garage widget too. Key finding: `vw/vh` already neutralizes *resolution*
(fullscreen window) but NOT *interface scale* (`settingsCore.interfaceScale.get()`), and the
damage-log panel exposes **no** position API (Flash — must calibrate empirically). Splits into
3 slices (scale-correctness → log-aware default → drag+persistence). Drag needs a new reverse
channel (VMs are read-only) + a settings store (ModsSettingsAPI?). Cross-refs the shipped in-battle
styling handoff (anchor, no-hot-reload, prior input-steal fix, reuse the overlay tuner to calibrate).
→ Research: TASKS/mod-positioning.md
