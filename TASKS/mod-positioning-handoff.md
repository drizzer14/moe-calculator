# Handoff: mod-positioning (phased) — Phases 0-1 DONE, Phases 2-3 pending

**Workflow:** one **clean session per phase**. Read this note + the approved plan, do the
phase, deploy, get in-game "lgtm", commit, then append a "Phase N done" section here and
`/clear` before the next phase.

- **Approved plan:** `C:\Users\Dmytro Vasylkivskyi\.claude\plans\work-on-positioning-task-validated-spring.md` (full context, all three phases, verification).
- **Research:** `TASKS/mod-positioning.md` (stale on the battle side — see below).
- **Memory:** `[[positioning-scale-findings]]`, `[[in-battle-moe]]`.

## Locked decisions (from user)
- Deliver **all three slices, phased, sign-off between each**.
- Phase 3 drag = **Ctrl+drag, always available** (no separate edit mode).
- Phase 3 persistence = **a small mod-local JSON** under the mod (ModsSettingsAPI was removed as an unused dependency — no settings backend is wired today).
- Phase 2 trigger = the **"Summarized damage" group only**: when ALL four `DAMAGE_LOG` summary flags are unticked, events shift up → raise the anchor; otherwise position unchanged. `EVENT_POSITIONS` does NOT matter.

## Reusable code (do not reinvent)
- **`C:\Users\Dmytro Vasylkivskyi\wgmod-research-progress`** ("Garage Progress Bar") already ships **Ctrl+drag + reset** — port the drag/reverse-channel from it for Phase 3 (but persist to a mod-local JSON, not MSA):
  `WGModResearch.js:703-793` (invokeCommand + drag), `view_models.py:171-177` (`_addCommand`), `tests/test_position.py`. (Its `bridge/mod_settings.py` is MSA-specific — use it only as a shape reference for the store, not a direct port.)

---

## Phase 0 — DONE (probes, no code shipped)

Probe: `tools/dev/probe_scale.py`, run via `tools/dev/repl_client.py` (REPL on :2224). Results @ 4K/3840×2160:

| | replay 2× | replay 1× | garage 2× | garage 1× |
|---|---|---|---|---|
| logical space (`move()` space) | 1920×1080 | 3840×2160 | n/a | n/a |
| `interfaceScale.get()` | 2.0 | 1.0 | 2.0 | 1.0 |
| drift vs WG panel (eyeball) | aligned* | **both axes** | aligned* | **drifted** |

\* 2× is where the current anchors were tuned.

**Conclusions:**
1. **Logical GUI space = physical px ÷ interfaceScale.** `move()` works in this space; surface fixed 256×256.
2. **Read `settingsCore.interfaceScale.get()`** (float), NOT `.getIndex()` (returned 0.0/"Auto" in garage while `.get()`=2.0).
3. **Both surfaces drift** with scale because their anchors are in **scale-invariant** units (battle = fraction of logical space `_ANCHOR_VW/_VH=0.138/0.788` in `battle_view.py:84-85`; garage = `vw/vh` in `MoECalculator.css:13-56`), while WG's panels are in **scale-tracking** units.
4. WG efficiency/damage panels are **Flash** — no runtime position API; calibrate empirically.

**Battle side is STALE in `mod-positioning.md`:** overlay is no longer fullscreen; it's a content-sized Wulf WINDOW positioned from Python in `battle_view.py::MoEBattleWindow._onReady()` (far-sentinel calibrate → `move()` at the fraction anchor). The `13.8vw/78.8vh` CSS anchor is gone.

---

## Phase 1 — interface-scale correctness — DONE (verified in-game 1x+2x, committed)

**What shipped (both surfaces track interface scale + resolution now):**
- **Battle** — the fraction anchor `_ANCHOR_VW/_VH` is GONE. New pure `domain/positioning.py::anchor_top_left()` (unit-tested `tests/test_positioning.py`) + `domain/constants.py::BATTLE_ANCHOR_X=264 / BATTLE_ANCHOR_Y=0` place the window at a FIXED logical-px offset from the bottom-left (X=264 from left, bottom-flush). `battle_view._place()` (far-sentinel calibrate → anchor) + new `apply_position()`; `battle_bridge` arms `settingsCore.interfaceScale.onScaleChanged` (via new `battle_adapter._settings_core()`) to re-place mid-battle. `MoEBattle.css` UNCHANGED (bottom-flush + the existing `top:27rem` already aligned at both scales). Hypothesis confirmed live at 1x (REPL nudge `move(264,1904)` → "perfectly aligned"); 2x is byte-identical to the old shipped-aligned placement.
- **Garage** — `MoECalculator.css` anchor converted vw/vh → rem (pure CSS; the engine reflows rem live on scale change, so NO Python push needed). S1 probe (temporary on-screen debug in the JS, since removed) established: hangar CSS px == PHYSICAL px (viewport stays 3840x2160 at every scale); **1rem == interfaceScale px** (1px@1x, 2px@2x) == WG's logical unit. So `right: 46rem` (was 2.4vw); vertical needed a **rem + fixed-140px** hybrid via `calc()` (Coherent honors mixed-unit calc + reflows it live) because the carousel sits above scale-INVARIANT bottom chrome: `.moe-rows2 = calc(232rem+140px)` (verified live 1x+2x on double-row), single-row `calc(205.5rem+140px)` + `.moe-small calc(189rem+140px)` DERIVED from the same model (2x preserved exactly, NOT eyeballed — spot-check if those carousel modes are used).

**Follow-ups:** the deployed `.wotmod` still carries the OLD garage CSS (the fix rode a `res_mods` hot-reload overlay); rebuild+deploy for a clean packaged state before release. Verify at a 2nd resolution when convenient.

---

## Phase 1 — interface-scale correctness (original plan, for reference)

**Hypothesis to fix the drift (verify FIRST, before writing battle code — no hot-reload there):**
re-express each anchor in a **scale-tracking unit** so it follows WG's panels:
- **Battle:** anchor to a **fixed logical-px offset from the bottom-left edge** instead of a fraction of the space. X analysis: 2×-correct ≈ 264 logical from left; the fraction wrongly doubles it to ~529 at 1× (≈265 physical px too far right = the observed drift). A fixed logical offset predicts ~264 at both scales.
- **Garage:** anchor in **rem** (engine scales rem with interface scale) instead of `vw/vh`.

If the hypothesis holds, **no per-scale calibration table is needed** — just a unit change + re-apply on scale change. If it does NOT fully hold, fall back to an empirically-calibrated `anchor(scale)` lookup table (calibrate 1× and 2×, interpolate).

**Step 1 — LIVE VERIFY (client in a paused replay, scale 1×):** nudge the battle window to a fixed logical offset from bottom-left and ask if it now aligns with WG's efficiency panel:
```
py -3 tools/dev/repl_client.py "from moe_calculator.bridge import battle_view as bv; from frameworks.wulf import PositionAnchor as PA; w=bv._active[0]; w.move(264, 0, xAnchor=PA.LEFT, yAnchor=PA.BOTTOM); echo(str(w.position)+' '+str(w.size))"
```
(Note the readout also carries a CSS `top:27rem` in-box nudge tuned for 2×-flush — the Y may need a companion tweak. Iterate X/Y live until aligned at 1×, then re-check 2×.)

**Step 2 — implement:**
- *Battle* (`bridge/battle_view.py`): replace the `_ANCHOR_VW/_VH` fraction math in `_onReady` (`:117-137`) with the verified fixed-logical-offset placement; keep fail-soft. Re-apply on scale change: add `settingsCore.interfaceScale.onScaleChanged` to `battle_bridge._LISTENERS`/`_arm` (`:111-153`) calling a new `battle_view.apply_position()`. Reconcile the CSS `top:27rem` nudge (`MoEBattle.css:60-75`) with the new anchor.
- *Garage* (`MoECalculator.css:13-56`, `MoECalculator.js`, `bridge/gameface_bridge.py`): convert the `vw/vh` anchor to rem (or push `uiScale` from a new fail-soft `_ui_scale()` mirroring `_carousel_geometry` `:262-275` and set `--ui-scale` in `render()`); react to `GRAPHICS.INTERFACE_SCALE in diff` in `_on_settings_changed` (`:95-107`). Garage JS/CSS **has** hot-reload (`tools/dev/sync_gameface.py`) — iterate there cheaply.
- Keep any scale→offset math **pure + unit-tested** (Python 3.13 pytest).

**Verify:** placement aligned at 1× AND 2× on both surfaces; ideally a 2nd resolution. `commit-after-lgtm`.

---

## Phase 2 — damage-log-aware default anchor — DONE (verified in-game, committed)

**What shipped:** when the "Summarized damage" group is fully unticked (all four `DAMAGE_LOG`
summary flags off) WG collapses the summary block and the damage-log events shift up, so the
overlay moves to a **separate RAISED anchor**; any one flag ticked → the signed-off default.
- Pure predicate `domain/positioning.py::damage_log_summary_hidden(total, blocked, assist, assist_stun)`
  (bool-coerced so getSetting's 0/1/None read right; unit-tested).
- `domain/constants.py`: default `BATTLE_ANCHOR_X=264 / BATTLE_ANCHOR_Y=0` **UNCHANGED**; new
  **`BATTLE_ANCHOR_X_RAISED=215 / BATTLE_ANCHOR_Y_RAISED=33`** — its OWN X+Y (per user decision:
  *raised-only X*, default preserved). Calibrated LIVE via the box-drag tuner artifact
  (real-readout graft: real MoEBattle font + `.mb-*` CSS + dither backdrop over a 2× 4K shot).
- Fail-soft reader `battle_adapter.read_damage_log_summary_flags()` (`core.getSetting` ×4; a bad
  read defaults that flag to *ticked* → predicate → DEFAULT anchor, so we never wrongly raise).
- `battle_view._place` picks raised-vs-default **X and Y** from the predicate; re-applied on
  interface-scale change (Phase 1) AND on `settingsCore.onSettingsChanged` when any of the four
  flags toggles (new `settings`/`onSettingsChanged` listener + `_settings_core_holder` in
  `battle_bridge`, membership-idempotent).
- 62 tests pass; Python 2.7 byte-compile clean. Verified in-game (unticked → raised 215/33;
  re-tick any one → default 264/bottom-flush). `commit-after-lgtm` satisfied.

**Follow-up:** the deployed `.wotmod` still carries the OLD garage CSS via the `res_mods`
hot-reload overlay-shadow (Phase 1 note) — a clean rebuild before release still applies. **Phase 3
(Ctrl+drag + mod-local JSON persist) is next** and un-started.

## Phase 2 — damage-log-aware default (own session, after Phase 1)
Binary: read the four `DAMAGE_LOG` flags (`TOTAL_DAMAGE='damageLogTotalDamage'`, `BLOCKED_DAMAGE`, `ASSIST_DAMAGE`, `ASSIST_STUN`; confirmed in `settings_constants.py:268-272`) via `core.getSetting(...)` in `battle_adapter` (fail-soft). Pure predicate in `domain/`: all-unticked → raised anchor, else default. Re-apply via `onSettingsChanged` (any of the four in diff). Calibrate the raised anchor in-game (all-four-unticked layout) at 1×/2×. Builds on Phase 1's scale-aware placement.

## Phase 3 — HANDOFF TO A CLEAN SESSION (working tree REVERTED to HEAD; WIP saved as a patch)

Per the user (2026-07-08): **the positioning/persistence work was discarded back to HEAD**
(overlay behaves exactly as at commit `0df7cff` again). The clean session should **focus
ONLY on making the Ctrl+drag work** — start from the *learnings* below, not the reverted code.

### What we PROVED this session (all live, do NOT re-litigate)
- **JS-side drag is a DEAD END** (two independent reasons): plain JS `console.log` is NOT
  routed to `python.log` (only JS *errors* + engine `[Gameface]` msgs are), and the
  input-transparent overlay WINDOW (`show(focus=False)`, `pointer-events:none`) gives its DOM
  no usable pointer path — the guaranteed-visible Python handler never fired on a drag. So
  **drive the drag ENTIRELY from Python.**
- **All Python-driven drag primitives VERIFIED via the REPL (:2224):**
  - `BigWorld.isKeyDown(Keys.KEY_LCONTROL / KEY_RCONTROL / KEY_LEFTMOUSE)` — reads Ctrl + LMB,
    including held together (sampled `ctrl+lmb_any=True` over 5 s while the user held them).
  - `GUI.mcursor().position` — cursor in **CLIP space**: x∈[-1,1] L→R, y∈[-1,1] **BOTTOM→top**
    (flip y for screen). Updates live; cursor is visible only while Ctrl is held (WG behaviour).
  - `GUI.screenResolution()`=(3840,2160) ÷ `interfaceScale.get()`=2.0 → logical 1920×1080;
    `logical − 256 surface == far-sentinel extent 1664×824` EXACTLY (compute logical size
    directly; do NOT far-sentinel mid-drag — it would fling the window).
  - `window.move()/position/size` work; surface fixed **256×256** (`size` read-only).
  - **GOTCHA:** `BigWorld.callback` scheduled from the **REPL socket thread** ("Python7") does
    NOT run on the main loop (heartbeat never fired) — but from the MOD (main thread) it does…
    **but only for ~2 s, then the chain silently dies — see SESSION 2 below.**
    REPL multi-line needs `execfile(r'…')` (`--file` sends per-line → SyntaxError on loops).
- **The overlay RENDERS FINE** — confirmed by REPL-moving the live window to screen centre
  (`w.move(760,400,…)`): the readout appeared. So rendering/model/front-end are all good.

### SESSION 2 (2026-07-08) — ROOT CAUSE FOUND: the poll STALLS after ~2 s (NOT a mapping/Ctrl bug)

The handoff's "the poll loop DOES run in the mod" was a **false inference** — it was based only
on the `drag poll armed` log (which just proves `arm()` ran), never on an actual tick count.
This session instrumented an **unconditional** alive-heartbeat at the TOP of `_poll_once`
(before the Ctrl-gated early-return) + edge logging, deployed, and captured live:

- The poll **does** start ticking (logged `alive tick=33,34,37,66`, `win=True`) — so
  `BigWorld.callback`, the gen guard, and `_active_window()` are all fine at first.
- Then **every subsystem's** logging stops at the SAME instant (`18:00:03.592`, tick 66) —
  that's a **python.log buffer-flush boundary, not a crash**; mid-battle the file tail is
  STALE (don't trust it — use the REPL, below).
- **Decisive REPL probe (no flush dependency):** read `battle_drag._state['dbg_tick']` twice
  1 s apart → **`delta_over_1s = 0`** while `armed=True, gen=1`, `dbg_tick` frozen at **74**.
  If the 33 Hz loop were alive `dbg_tick` would be in the tens of thousands. So the
  self-rescheduling `BigWorld.callback` chain **fires ~74 times (~2 s) then silently stops** —
  **no exception** (the reschedule is guarded + would `LOG_CURRENT_EXCEPTION`), **no disarm/
  teardown** (no `overlay window destroyed`), gen unchanged. The timer chain just stops.

**Consequences for next session:**
- ctrl detection and the `_over`/mapping math are **UNTESTED, not disproven** — the poll died
  before the user's real Ctrl-hold+drag, so the `lctrl=False` lines are just the pre-gesture
  window, NOT evidence Ctrl is unreadable. Re-evaluate them only once the poll survives.
- **The bug to fix FIRST is the stalling poll**, not the gesture.

**Reusable diagnostic technique (do this instead of tailing python.log mid-battle):** have the
poll write what it sees into module state (`_state['dbg_tick']` etc.), then read it live over
the REPL — bypasses the log-flush buffering entirely and measures the tick rate directly.

### Clean-session plan (drag only) — REVISED for the stall

1. Restore the WIP: `git apply TASKS/phase3-drag-wip.patch` (now INCLUDES the alive-heartbeat
   instrumentation + `_state` dbg fields — brings back `battle_drag.py`, `mod_settings.py`, the
   `battle_bridge`/`battle_view`/`view_models`/`wulf_args` wiring, tests).
2. **Fix the stalling `BigWorld.callback` chain FIRST.** Hypotheses to test (cheap, via the REPL
   `dbg_tick`-delta probe — no relaunch needed to confirm a fix once deployed):
   - The scheduled `lambda: _tick(gen)` closure may be **GC'd** after arm returns (the engine
     may hold only a weak ref) → hold a strong module-level ref to the callback, or schedule a
     **bound method / module-level function with args** instead of a fresh lambda each tick.
   - The engine may cancel app-scheduled `BigWorld.callback`s across a battle-load phase (the
     `[Gameface] … Size calculation timeout` + a `place` both landed at ~tick 66) → re-arm from
     a **durable periodic signal** or an **input-event hook** instead of self-rescheduling.
   - **Preferred redesign:** drop the poll entirely and drive the drag from WoT's **input event
     system** (event-driven, no self-reschedule, no 33 Hz burn) — investigate `InputHandler`
     (`avatar_input_lobby` / `gui.app_loader`) key+mouse handlers, or an `onMouseMove`/key
     handler on the battle app. Grep the decompile (Dev quickref) for the mount point.
3. Once the loop survives a whole battle (verify: `dbg_tick` climbs into the thousands via REPL),
   THEN validate the gesture (ctrl → `over` → `move`), fix any mapping, then wire persistence
   (`mod_settings.py` per-mille fractions are ready) + reset, then `commit-after-lgtm`.

`battle_drag.py` design: gesture logic (fresh Ctrl+LMB whose cursor is inside the window rect →
`window.move` to cursor − grab-offset → release persists the fraction) is fine; **only the
scheduling mechanism is broken.** Full code + instrumentation in the patch.

## Phase 3 — Ctrl+drag + persist (own session, after Phase 2) — ORIGINAL PLAN (pre-pivot; JS parts are now known-dead)
Gated on drag probes **P1** (can the `focus=False`, `pointer-events:none` window receive ANY pointer event on a temp `pointer-events:auto` hot layer?), **P2** (`setPointerCapture` across the ~256px surface; screen-fraction vs delta wire contract), **P3** (Python-observable Ctrl), **P5** (MSA symbols). **Build probe-independent plumbing first** (`clamp_frac`/`cmd_xy_frac` + tests, port `mod_settings.py` → fractions, `BattleMoEVM` `setPosition`/`resetPosition` commands + `properties=7`→6 fix, `place_fraction` refactor + seed, `onResetMod` reset) so persistence + reset ship even if free-drag proves infeasible (fallback: MSA X/Y-fraction steppers / arrow-nudge). **Move the WINDOW via Python `move()`, never the DOM element.** Full mechanics in the plan file + the deeper design captured this session.

---

## Dev quickref
- Build+deploy (client CLOSED): `& "C:\Python27\python.exe" build\deploy_wotmod.py "D:/Games/World_of_Tanks_EU" 2.3.0.1`
- Garage JS/CSS hot-reload (client open): `& "<py3>" tools\dev\sync_gameface.py "D:/Games/World_of_Tanks_EU" 2.3.0.1` → switch screens. **Battle overlay: NO hot-reload, full relaunch.**
- Tests: `& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" -m pytest -q`
- REPL: `& "<py3>" tools\dev\repl_client.py "<expr>"` (needs `com.14th_ua.moe_calculator_debug.wotmod`, :2224).
- Decompile (grep symbols): `C:\Users\Dmytro Vasylkivskyi\wot-eu\source\res\scripts\client\`.
