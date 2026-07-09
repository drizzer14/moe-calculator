# Research: Refine mod positioning (drag-and-drop + scale/screen/log-aware defaults)

_Submitted: "Refine mod positioning in battle: drag-n-drop, automatic default positioning depending on Log settings, screen size and interface scale. Last two apply to the garage widget as well." · Status: open_

## Summary

Three related positioning improvements:

1. **(battle) Drag-and-drop** — let the player grab the in-battle MoE panel and move it,
   with the chosen position persisted across battles.
2. **(battle) Smarter default position** — auto-place the panel based on the player's
   **damage-log settings**, **screen size**, and **interface scale** instead of one
   hardcoded anchor.
3. **(garage + battle) Screen-size + interface-scale awareness** — the "screen size" and
   "interface scale" parts apply to the **garage widget** too, so both surfaces stay put
   correctly across resolutions and UI-scale changes.

Both surfaces are hardcoded, viewport-relative anchors today with essentially no
dynamic positioning (the garage has only a carousel-row `bottom` nudge). This note maps
what's there and what runtime data actually exists — with one significant correction to
the premise (see Findings §D).

## Findings

### A. In-battle overlay — current positioning (100% static CSS)
- `#moe-battle-root` is built once in `MoEBattle.js` `ensureRoot()` (~lines 69-90) and
  appended to `document.body`. `render()` (~92-121) only toggles `display` + sets
  text/colour — **no resize listener, no pointer/drag handler, never touches position.**
- The sole positioning rule: **`MoEBattle.css:53-63` → `#moe-battle-root { position:fixed;
  left:13.8vw; top:78.8vh; z-index:9000; pointer-events:none; }`** — a hand-tuned constant
  (calibrated against WG's efficiency panel in the overlay tuner). This `13.8vw / 78.8vh`
  pair is the single value any dynamic-default or drag logic must override.
- The window itself is a **fullscreen** Wulf window: `battle_view.py:87-89`
  (`WindowFlags.WINDOW | WINDOW_FULLSCREEN, layer=WindowLayer.WINDOW`). No anchor/geometry
  rect — placement is entirely delegated to the CSS. `res_map/MoEBattleView.json` has no
  geometry either.
- Python push (`battle_bridge.py::push`, ~170-189) writes only data fields
  (`visible, combinedDamage, projAvgDamage, curPercent, pctDelta, hasData`) onto
  `BattleMoEVM`. **No position/geometry/screen fields.** `BattleMoEVM` (`view_models.py:105-139`)
  is a flat, read-only, 6-prop VM with no position fields.

### B. Garage widget — current positioning (static + carousel nudge only)
- `#moe-root` anchor: **`MoECalculator.css:13-56` → `position:fixed; right:2.4vw;
  bottom:25.5vh; width:315rem; pointer-events:auto;`** (live-calibrated at the 1080/2160p
  baseline).
- The **only** dynamic positioning today is carousel-row-count driven, on the `bottom`
  axis only: `MoECalculator.js` `render()` (~296-298) toggles classes `moe-rows2` /
  `moe-small`, and `MoECalculator.css:89-90` maps them to `bottom:28vh` / `bottom:24vh`.
  Fed by `gameface_bridge._carousel_geometry()` (~262-275) reading `sc.GAME.CAROUSEL_TYPE`
  / `DOUBLE_CAROUSEL_TYPE` from `ISettingsCore.options`; pushed via `setCarouselRows` /
  `setCarouselSmall` (`push`, ~334-335); re-pushed by `_on_settings_changed` (~95-107).
- **No screen resolution and no interface scale is read anywhere** in the mod (Python or
  JS). `MoEVM` (`view_models.py:45-102`) has `carouselRows`/`carouselSmall` but no
  screen/scale/x/y fields.
- `#moe-root` is already `pointer-events:auto` — the natural drag surface if garage drag is
  ever wanted (not requested here, but noted).

### C. Runtime data source — screen size ✅
- **`BigWorld.screenSize()` → `(width, height)` in device px** (e.g. `(3840, 2160)`).
  In-client precedent: `hangar_header.py:95`, `interfacescalemanager.py:62`.
- Resolution-change event: the global set **`gui.g_guiResetters`** (`gui/__init__.py:15`).
  Add a zero-arg callable; invoked on device recreate / resolution change
  (`gui/shared/personality.py:354`). Precedent: `hangar_header.py:118`
  `g_guiResetters.add(...)`. **Must `g_guiResetters.discard(fn)` on teardown.**
- Avoid `gui/shared/utils/graphics.py::getResolution()` — it clamps down to 1280×768
  (`min(width, MIN_SCREEN_WIDTH)`, line 139). Use `BigWorld.screenSize()`.
- **Key nuance:** because the overlay window is fullscreen, **`vw/vh` in CSS already
  neutralizes resolution** — raw pixels are only needed for scale math or px-exact offsets,
  not for basic placement.

### D. Runtime data source — interface scale ✅ (premise correction: no `g_guiScaleManager`)
- There is **no `g_guiScaleManager`** in this client (zero grep hits). Interface scale lives
  on **`settingsCore.interfaceScale`** (an `InterfaceScaleManager`).
- **Current multiplier: `settingsCore.interfaceScale.get()`** → float `1.0 / 2.0 / 4.0 …`
  (`interfacescalemanager.py:36-37`). Raw index via `.getIndex()`; `value = 2**(index-1)`,
  index 0 = "auto".
- Change events: `InterfaceScaleManager.onScaleChanged(scaleValue)` /
  `.onScaleExactlyChanged(scaleValue)` (`interfacescalemanager.py:14-15,55-58`) — subscribe
  to re-position mid-session.
- Or via the settings diff (same pattern the mod already uses): key
  **`GRAPHICS.INTERFACE_SCALE = 'interfaceScale'`** (`settings_constants.py:36`); react in
  `onSettingsChanged(diff)` with `GRAPHICS.INTERFACE_SCALE in diff` — exactly analogous to
  `gameface_bridge.py:99-100`. (`getSetting` returns the *index*; prefer
  `interfaceScale.get()` for the multiplier.)
- **Why it matters:** WG's HUD grows with interface scale, so the damage-panel corner
  **moves in vw/vh terms** as scale changes. `vw/vh` neutralizes *resolution* but **not
  interface scale** — this is the main thing the current hardcoded anchor gets wrong.

### E. Runtime data source — damage-log settings ⚠️ (position is NOT queryable)
- **Firm negative:** WG offers **no user setting or API for the damage-log panel's on-screen
  X/Y.** The panel (`.../battle/shared/damage_log_panel.py`, `class DamageLogPanel`) is a
  **Flash/Scaleform** component; its pixel corner is baked into the SWF layout, not exposed
  to Python. (This matches `TASKS/in-battle-moe-panel.md §1` — the panel can't be injected
  into either.) So "position depending on Log settings" cannot mean "read the panel's
  position"; it must mean **react to the log's content/footprint settings + calibrate the
  corner empirically**, then offset by interface scale.
- Damage-log **content/visibility** settings *are* readable via the same `ISettingsCore`
  the mod already uses — `settings_constants.py:268 class DAMAGE_LOG`:
  - `SHOW_DETAILS='damageLogShowDetails'` — `SHOW_ALWAYS / SHOW_BY_ALT_PRESS / HIDE`.
  - **`EVENT_POSITIONS='damageLogEventsPosition'`** — `ALL_BOTTOM` vs `NEGATIVE_AT_TOP`.
    **This is the one setting that changes the panel's vertical footprint** (received-damage
    rows at top vs. all-at-bottom), so it's the one worth reacting to if you want to avoid
    overlapping a taller/differently-shaped log.
  - `TOTAL_DAMAGE / BLOCKED_DAMAGE / ASSIST_DAMAGE / ASSIST_STUN` — which summary totals show
    (affects the summary block's height); `SHOW_EVENT_TYPES` — ALL/ONLY_NEG/ONLY_POS.
  - Read: `core.getSetting(DAMAGE_LOG.EVENT_POSITIONS)` etc.; react via `onSettingsChanged`.

## Suggested approach (a starting direction, not a spec)

Recommend splitting into **three shippable slices** so each can land independently:

**Slice 1 — interface-scale + resolution correctness (battle + garage).** Highest value,
lowest risk; fixes the actual "moves when scale changes" bug.
- Read `interfaceScale.get()` (and, if needed, `BigWorld.screenSize()`) in the adapters.
- Push a `uiScale` (float) onto both `MoEVM` and `BattleMoEVM` (`view_models.py`).
- In JS `render()`, set a `--ui-scale` custom property (or adjust root font-size) and
  express the anchor/offsets in terms of it. Mirror the existing carousel-class pattern.
- Re-push on scale change: add `settingsCore.interfaceScale.onScaleChanged` (battle: armed
  in `battle_bridge._LISTENERS`/`_arm`, ~93-115; garage: extend `_on_settings_changed`
  with `GRAPHICS.INTERFACE_SCALE in diff`). For resolution, optionally
  `g_guiResetters.add(...)` (discard on teardown).

**Slice 2 — damage-log-aware default (battle).** Read `DAMAGE_LOG.EVENT_POSITIONS` (± the
summary-total flags), pick between a small set of **empirically calibrated** default anchors
(one per log footprint), push the chosen anchor onto `BattleMoEVM`, apply in JS. Requires an
in-game calibration pass at 1× and 2× scale (see Verification / probe #4).

**Slice 3 — drag-and-drop (battle).** The biggest lift:
- Enable pointer capture on a drag handle (the panel is `pointer-events:none` today —
  `MoEBattle.css:58`); add `pointerdown/move/up` in `MoEBattle.js`, write inline `left/top`
  px (overriding the CSS anchor).
- **Persistence needs a new reverse channel** — `BattleMoEVM` is read-only today. Add an
  `invokeCommand`-style command (single MAP arg `{value:…}`, per wotmod-gameface-widget) to
  send the dropped x/y back to Python, and a **store** to persist it (a small JSON
  under the mod). On next battle, seed the default from the stored position (falling back to
  the Slice-2 computed default when unset). A "reset to default" affordance is worth
  including.
- Decide interaction: is the panel draggable only while some overlay/edit mode is on, or
  always? Always-draggable + `pointer-events:auto` risks stealing HUD input (the mod already
  fought an input-steal bug — see `in-battle-moe-styling.md`), so an explicit edit/unlock
  mode is safer.

## Touch points
- **Battle JS/CSS:** `MoEBattle.js` (`ensureRoot` ~69-90, `render` ~92-121, mount ~123-127),
  `MoEBattle.css:53-63` (the anchor) + `:58` (pointer-events).
- **Battle Python:** `bridge/battle_view.py:87-89` (fullscreen window), `bridge/battle_bridge.py`
  (`push` ~170-189, `_LISTENERS`/`_arm` ~93-115), `adapter/battle_adapter.py` (reads none
  today — add scale/log reads here), `bridge/view_models.py:105-139` (`BattleMoEVM` — add
  fields + any command).
- **Garage JS/CSS:** `MoECalculator.js` `render()` ~296-298, `MoECalculator.css:13-56` (anchor)
  + `:89-90` (carousel overrides pattern to mirror).
- **Garage Python:** `bridge/gameface_bridge.py` (`_carousel_geometry` ~262-275, `push`
  ~315-360, `_on_settings_changed` ~95-107, `_settings_holder` ~147-149),
  `bridge/view_models.py:45-102` (`MoEVM` — add `uiScale`).
- **Constants:** `domain/constants.py` has no geometry today — add anchor/scale constants
  here if the defaults become a table.

## Verification
- Unit: extend `tests/test_battle_builder.py` / adapter tests if any scale/log→anchor mapping
  becomes pure domain logic (keep the math engine-free and testable).
- In-game (this window has **no hot-reload** — full relaunch per change; see
  `in-battle-moe-styling.md`): verify placement at 1× and 2× interface scale, at 2+
  resolutions, and with `EVENT_POSITIONS = ALL_BOTTOM` vs `NEGATIVE_AT_TOP`. For drag: move +
  relaunch, confirm the position persisted; confirm HUD/menu input is NOT stolen.
- REPL probes (via wotmod-debug-repl, in a replay/training room):
  1. `console.log(window.innerWidth, window.innerHeight, window.devicePixelRatio)` in the
     overlay vs `BigWorld.screenSize()` — **decides whether Gameface already gives scaled CSS
     px, i.e. whether you must push scale from Python at all.**
  2. `import BigWorld; print(BigWorld.screenSize())` at scale 1× vs 2× — confirm units.
  3. `from helpers import dependency; from skeletons.account_helpers.settings_core import
     ISettingsCore; sc=dependency.instance(ISettingsCore); print(sc.interfaceScale.get(),
     sc.interfaceScale.getIndex())` — confirm value shape.
  4. Calibrate WG's damage-panel corner (in vw/vh) at scale 1× and 2× using the overlay tuner
     / `getComputedStyle` — the only way to get the panel position; feeds `anchor(scale)`.

## Open questions
- **Do we even need to push scale from Python?** Probe #1 settles it — if Gameface reports
  already-scaled CSS px, `vw/vh` may suffice and the whole scale-push can be dropped. Confirm
  before building Slice 1.
- **Drag persistence store:** a small mod-local JSON (decided — MSA was removed as an unused
  dependency). New plumbing either way, since the mod has no settings backend today.
- **Drag interaction model:** always-draggable vs. an explicit unlock/edit mode (input-steal
  risk favors the latter).
- **Scope of "screen size" for the garage:** is there an actual observed mispositioning at
  non-baseline resolutions, or is `vw/vh` already fine there? (The garage is a normal injected
  view, not a fullscreen window — behavior may differ from the battle overlay.) Confirm the
  real symptom before building.
- Should the battle default track the summary-total flags too, or only `EVENT_POSITIONS`?

## Cross-references
- `TASKS/in-battle-moe-styling.md` — the overlay's current anchor, the no-hot-reload
  constraint, the overlay tuner (reuse it for the scale calibration in probe #4), and the
  prior input-steal fix (relevant to drag).
- `TASKS/in-battle-moe-panel.md` — confirms the damage/efficiency panels are Flash and not
  injectable (why the log position isn't queryable).
- `TASKS/in-battle-moe-handoff.md` — live findings + BUG B.
