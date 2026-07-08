# Research: In-battle overlay steals Ctrl+click / Ctrl+hover (cursor mode)

_Submitted: "Ctrl+mouse click is stolen" + "Ctrl+hover too" · Status: shipped_

> **2026-07-07 — Fix 3 ruled out, Fix 1 applied (untested, user opted in):**
> - **Fix 3 is DEAD:** grepped all of `frameworks/wulf` + `gui/impl` in the decompile —
>   no `setInputTransparent`/`hitTest`/`inputEnabled`/`setSize` lever exists; window
>   size/position is entirely C++ (`WindowSettings` exposes none). Confirmed the note's inference.
> - **Fix 1 applied:** dropped `WINDOW_FULLSCREEN` (`bridge/battle_view.py` → `WindowFlags.WINDOW`
>   only, layer WINDOW); the surface now sizes to a fixed rem box (`MoEBattle.css` `html,body`
>   340×88rem, root repositioned to the box top-left); `_onReady` `move(_ANCHOR_X,_ANCHOR_Y,
>   LEFT,BOTTOM)` places it bottom-left. Stale `layer=OVERLAY` log fixed.
> - **Why confident it's viable:** WG precedent `gui/impl/lobby/offers/offer_banner_window.py`
>   — a decoratorless non-fullscreen `WindowFlags.WINDOW` that `load()`s then `center()`s, i.e.
>   content-sized + movable. Same pattern.
> - **Still LIVE-UNKNOWN (must relaunch to check):** (a) the Coherent surface adopts the body's
>   declared rem/px size (vs. defaulting fullscreen/0); (b) rem basis in windowed mode; (c) the
>   bottom-left anchor is a first guess — expect one calibration pass (`_ANCHOR_X/_Y` +/or the
>   CSS box). If the surface does NOT content-size, fall back to Fix 2 (Flash placeId sub-view).
>
> **2026-07-07 LIVE FINDINGS (via REPL, WoT running):**
> - Fix 1 WORKS: Ctrl-steal is GONE (user-confirmed minimap pings under the old overlay rect).
> - Surface does NOT content-size — it's a **fixed 256×256 in a LOGICAL 1920×1080 GUI space**
>   (physical 3840×2160 = 2×). `windowSize` is READ-ONLY (no resize lever). `move()` coords are
>   in that logical space, NOT physical px.
> - `_onReady` reworked to **self-calibrate**: `move(FAR,FAR)` → read clamp `(max_x,max_y)` →
>   `space = max + size` → place top-left at `(_ANCHOR_VW*space_w, _ANCHOR_VH*space_h)`, clamped.
>   Resolution/scale-independent. Deployed position = **(264,824) logical = 13.75vw / 76.30vh**.
> - REMAINING CALIBRATION: readout sits ~1.5 rows too HIGH (target ≈ 78.8vh, the old anchor). The
>   256-tall box is clamped flush to the bottom (top can't exceed y=824), so the down-nudge must
>   be an **in-box CSS offset** `#moe-battle-root { top: ~1.5 row-pitches }`, NOT a `move()` change.
>   Pending: user tuning the exact offset in the overlay tuner.

## Summary

Holding **Ctrl** in battle reveals the mouse cursor (forced GUI mode) so the player can click
the minimap, target markers, and radial commands. While the cursor is up, the mod's in-battle
overlay **captures the click AND hover** — the minimap ping / marker interaction doesn't
register under the overlay's rectangle. A prior *keyboard* input-steal was already fixed by
moving the window `OVERLAY`→`WINDOW`; the *mouse* path is still captured. The overlay's CSS is
`pointer-events:none` throughout, so the surprise is that clicks/hover are still eaten.

## Root cause

The overlay is a **separate, top-level, full-screen Coherent/Gameface window** (its own
document, registered via `res_map/MoEBattleView.json`), composited at `WindowLayer.WINDOW` (=7),
directly over the Scaleform battle HUD (`SF_BATTLE`) which lives at `WindowLayer.VIEW` (=4)
(`gui/Scaleform/battle_entry.py:111-112`). When Ctrl reveals the cursor
(`gui/Scaleform/managers/battle_input.py:85-88` → `setForcedGuiControlMode` →
`AvatarInputHandler/__init__.py:379-398` `attachCursor(SF_BATTLE)`), the pointer event is routed
to the **topmost window whose rectangle covers the cursor** — the mod's full-screen window,
which sits above the minimap/markers.

**`pointer-events:none` does not translate to window-level, cross-surface hit-test
transparency.** It reliably passes events through only *within a single shared Gameface
document* — which is exactly why the garage widget (injected into the hangar's own document via
OpenWG `gf_mod_inject`) never steals hangar input. The battle overlay is NOT in the HUD's
document; it's its own full-screen surface stacked above `SF_BATTLE`, so the CSS only stops
*its own* DOM elements from being event targets — it does not make the window **rectangle**
transparent to the engine's hit-test. Focus/keyboard was decoupled by the layer move; mouse
routing is geometric + per-window, so it's still captured (both click and hover, hence
"Ctrl+hover too").

**No Python-level input-transparency lever exists.** `WindowFlags`
(`frameworks/wulf/gui_constants.py:59-79`) has only type/state/modality bits — no
"input-transparent"/"click-through"/"hit-test-off". `WindowSettings` /
`PyObjectWindow(Settings)` expose no mouse/hitTest attribute; grepping `frameworks/wulf` for
`hitTest|inputTransparent|mouseTransparent|passThrough` returns nothing. The actual pass-through
decision lives in the **C++ `_wulf`/Coherent layer** — so the "hit-tests the rectangle, not
per-element `pointer-events`" claim is a strong inference from the Python decompile that needs
**one live confirmation** (see probes).

Corroboration: WG ships **no** full-screen, info-only, click-through Gameface WINDOW over the
battle HUD. Every `WINDOW | WINDOW_FULLSCREEN` window in the client is input-capturing (reward
screens, dialogs, `PrebattleHintsWindow` — which explicitly *enters* GUI control mode,
`prebattle_hints_view.py:70-76`). WG's always-on battle HUD Gameface pieces (`DeathCamHudView`,
`PostmortemPanelView`, `BattleNotifierView`) are **not windows** — they're `ViewFlags.VIEW`
sub-views added as children of the battle MainView through a Flash-composited placeId
(`gui/Scaleform/framework/entities/inject_component_adaptor.py:88-97`,
`mainView.addChild(placeId, view, True)` + `as_setPlaceIdS`). Living inside the battle app's
composite/input model is what keeps them click-safe.

## Current window setup (the thing to change)
- `bridge/battle_view.py:86-89` — `WindowImpl(WindowFlags.WINDOW | WindowFlags.WINDOW_FULLSCREEN,
  content=content, layer=WindowLayer.WINDOW)`. The **`WINDOW_FULLSCREEN`** bit (=1024) makes the
  surface cover the whole screen.
- `battle_view.py:91-93` — `show(focus=False)` (already declines focus; never enters GUI control
  mode — good, that's why keyboard is clean).
- `battle_view.py:47-56` — `ViewSettings(..., ViewFlags.VIEW, BattleMoEVM())` (plain VIEW flag).
- `MoEBattle.css:47,58` — `pointer-events:none` on `html,body` and `#moe-battle-root`.
- `res_map/MoEBattleView.json` — standalone `impl: gameface` Layout (its **own** document, not a
  child of the HUD).
- Stale log nit: `battle_view.py:119` still prints `layer=OVERLAY` though it opens at `WINDOW`.

## Suggested approach (fixes, ranked — run in this order)

**Fix 3 first (cheap 5-min reconnaissance): probe for a C++ input-transparency setter.**
Nothing in the Python exposes one, but the live `PyObjectWindow`/`PyObjectView` proxy might.
Via the debug REPL, `dir()` the open window's proxy + the view proxy for anything like
`setInputTransparent` / `setMouseTransparent` / `setHitTestEnabled` / `setInputEnabled` / a
Coherent view flag. If one exists → one-line fix, makes Fix 1/2 unnecessary. If not → discard.

**Fix 1 (primary if Fix 3 is empty): make the window non-full-screen, sized to the readout rect.**
Drop `WINDOW_FULLSCREEN` (keep `WindowFlags.WINDOW`, layer 7) at `battle_view.py:88`, and give the
window a small rect over the damage-panel corner (bottom-left) via `WindowImpl.move(...)` / the
`WindowsArea` (`gui/impl/pub/window_impl.py:42-56`). If the engine hit-tests window rectangles
(the hypothesis), only that small corner still swallows clicks; the minimap (bottom-right) and
the rest of the screen become click-through because no mod window covers those pixels.
- **Two unknowns to confirm live:** (a) a non-fullscreen Gameface window actually sizes to a set
  rect rather than defaulting the surface to full screen — note the CSS `html,body{width/height:
  100%}` resolves against the *surface*, so the surface size must come from the window; (b)
  uncovered pixels truly pass through.
- Interacts with the drag/positioning feature (`TASKS/mod-positioning.md`): a sized window is
  also a prerequisite for a bounded drag target — worth coordinating so the two don't fight.

**Fix 2 (fallback, heaviest, most correct): host the readout as a battle-MainView sub-view via a
Flash InjectComponent placeId** — WG's own always-on-HUD pattern
(`inject_component_adaptor.py:88-97`). Inside a Scaleform-composited placeId surface, input
follows the battle app's hit-testing where HUD elements are already click-safe.
- **Honesty:** real new work (a Flash `.swf` shell / placeId plumbing). Prior research
  (`TASKS/in-battle-moe-mount-rework.md`, `in-battle-moe-handoff.md`) already concluded the
  battle HUD has *no shared full-screen Gameface document*, which is why the standalone window
  was chosen. This trades the click bug for significant complexity — only if Fix 1 fails.

## Touch points
- `bridge/battle_view.py:86-89` (drop `WINDOW_FULLSCREEN` + add geometry) — Fix 1.
- `bridge/battle_view.py:91-93` (`show(focus=False)` — keep).
- `bridge/battle_view.py:119` (fix the stale `OVERLAY` log string while here).
- `MoEBattle.css:47,58` (`pointer-events:none` — keep; not the actual lever).
- For Fix 2 only: a new Flash shell + placeId plumbing mirroring `inject_component_adaptor.py`.

## Verification
- **No hot-reload for this window — every attempt needs a full client relaunch.**
- REPL probe (Fix 3): in a live battle, `w = <the open MoEBattleWindow>`; inspect
  `dir(w.proxy)` / the view proxy for an input/hit-test setter; try toggling it and Ctrl+click
  the minimap.
- Repro / accept test: in a battle (or replay), hold **Ctrl**, then click the **minimap** under
  where the overlay sits and confirm the ping registers; hover a target marker under the overlay
  and confirm the tooltip appears; confirm the readout area itself no longer blocks either.
- Fix 1 validation: open the window without `WINDOW_FULLSCREEN`, `move()`/size it to the corner,
  Ctrl+click minimap (should register) and Ctrl+click over the readout (only that eaten, or
  nothing if the surface is truly small).

## Open questions
- **Does the engine hit-test the window rectangle vs. per-element `pointer-events`?** The one
  C++-level inference underpinning Fix 1 — confirm via the repro above before committing.
- Does a non-fullscreen Gameface window size to its rect, or does the surface still default to
  full screen (making Fix 1 moot)? Confirm live.
- Is there any `PyObjectWindow`/view input-transparency setter (Fix 3)? Introspect live.

## Cross-references
- `TASKS/in-battle-moe-styling.md` — prior OVERLAY→WINDOW keyboard-steal fix + no-hot-reload.
- `TASKS/in-battle-moe-mount-rework.md` / `in-battle-moe-handoff.md` — why a standalone window
  (not a HUD-injected view) was chosen; directly relevant to Fix 2's cost.
- `TASKS/mod-positioning.md` — a sized (non-fullscreen) window overlaps with the drag target;
  coordinate Fix 1 with the positioning work.
