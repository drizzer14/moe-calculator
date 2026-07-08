# Ideas backlog

Short, one-line entries for future features and bug reports. The **wotmod-planner**
skill researches each submission against the codebase and saves an implementer-ready
note under `TASKS/`; delete an entry here once it ships.

## Open

### In-battle overlay — LTR (current) / RTL layout direction
The overlay is built left-to-right (`[icon] [value]`, left-aligned, backdrop fading from the
left, window anchored bottom-left). Add an RTL mode that mirrors it (`[value] [icon]`,
right-aligned, backdrop from the right, and likely a bottom-right anchor). Same wiring as the
single/double-row toggle: a `rtl` VM flag → a `.mb-rtl` CSS class → mirrored overrides (try
`direction: rtl` first, fall back to explicit flex/margin/mask flips). Shares the VM property
slot budget with the row-mode task and couples with positioning (the right-edge anchor).
→ Research: TASKS/in-battle-rtl-layout.md

### Single / double row mode for the in-battle overlay
The in-battle overlay is a fixed two-row vertical stack (row 1 dmg/avg, row 2 %/delta). Add a
single-row mode that lays both metric groups on ONE horizontal line for a shorter footprint.
Mostly CSS: flip `#moe-battle-root` to `flex-direction: row` + kill the column-overlap margin;
drive it off a `compact` flag (mirror the garage's `carouselRows` class-toggle precedent —
BattleMoEVM even has a spare property slot). Couples with positioning (single row is shorter →
re-tune the bottom-flush anchor). Open decision: dev-constant vs a first ModsSettingsAPI toggle.
→ Research: TASKS/in-battle-single-double-row.md

### Garage widget — match the setup-slot box style EXACTLY (2nd pass)
First pass (border-texture swap only) degraded the visuals and delivered nothing. Second pass:
match WG's garage boxes **exactly**, grounded in the client's own Gameface CSS. Key finding —
the shells/consumables/equipment/directives slots are ALL one component
(`lobby/tanksetup/common/SlotParts/Container`): 54rem square, flat `rgba(0,0,0,.45)` fill, `toggle.png`
9-slice frame (`4 fill / 4rem`, stretched, full opacity), **no border-radius**, brighten-on-hover.
The widget mismatches on 5 axes (radius, opacity, repeat-vs-stretch, fill tone, inverted hover)
+ a wide-bar aspect caveat. Crew boxes are IDENTICAL (same box) — only their tooltips differ, so
all five named types map to the one box. ⚠️ CORRECTION: the real hangar bottom-bar boxes are
Scaleform FLASH (`AmmunitionPanel.swf`), NOT the Gameface `Container.css` (that's a different
full-screen view) — decompile the SWF for authoritative values; the CSS is only an approximation.
→ Research: TASKS/garage-box-style-match.md (supersedes TASKS/garage-widget-ammo-border.md)

### Refine mod positioning — Phase 3: drag-and-drop + persist
Phases 1 (interface-scale + resolution correctness, `e4b7d1d`) and 2 (damage-log-aware raised
anchor, `0df7cff`) have **shipped** — both surfaces now scale-correct and the battle overlay
auto-raises when the damage log is present. Remaining slice: **drag-and-drop the in-battle panel
with a persisted position**. Drag needs a new reverse channel (VMs are read-only) + a settings
store (ModsSettingsAPI?). A WIP patch exists: `TASKS/phase3-drag-wip.patch`. Full phased context,
locked decisions, and per-phase verification live in the handoff note.
→ Research: TASKS/mod-positioning-handoff.md
