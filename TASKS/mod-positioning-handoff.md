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
- Phase 3 persistence = **ModsSettingsAPI** (`izeberg.modssettingsapi_1.7.0.wotmod` is vendored in `installer/vendor/`; zero code refs today).
- Phase 2 trigger = the **"Summarized damage" group only**: when ALL four `DAMAGE_LOG` summary flags are unticked, events shift up → raise the anchor; otherwise position unchanged. `EVENT_POSITIONS` does NOT matter.

## Reusable code (do not reinvent)
- **`C:\Users\Dmytro Vasylkivskyi\wgmod-research-progress`** ("Garage Progress Bar") already ships **Ctrl+drag + ModsSettingsAPI + reset** — port from it for Phase 3:
  `src/res/scripts/client/wgmod_research/bridge/mod_settings.py`, `WGModResearch.js:703-793` (invokeCommand + drag), `view_models.py:171-177` (`_addCommand`), `tests/test_position.py`.

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

## Phase 2 — damage-log-aware default (own session, after Phase 1)
Binary: read the four `DAMAGE_LOG` flags (`TOTAL_DAMAGE='damageLogTotalDamage'`, `BLOCKED_DAMAGE`, `ASSIST_DAMAGE`, `ASSIST_STUN`; confirmed in `settings_constants.py:268-272`) via `core.getSetting(...)` in `battle_adapter` (fail-soft). Pure predicate in `domain/`: all-unticked → raised anchor, else default. Re-apply via `onSettingsChanged` (any of the four in diff). Calibrate the raised anchor in-game (all-four-unticked layout) at 1×/2×. Builds on Phase 1's scale-aware placement.

## Phase 3 — Ctrl+drag + persist (own session, after Phase 2)
Gated on drag probes **P1** (can the `focus=False`, `pointer-events:none` window receive ANY pointer event on a temp `pointer-events:auto` hot layer?), **P2** (`setPointerCapture` across the ~256px surface; screen-fraction vs delta wire contract), **P3** (Python-observable Ctrl), **P5** (MSA symbols). **Build probe-independent plumbing first** (`clamp_frac`/`cmd_xy_frac` + tests, port `mod_settings.py` → fractions, `BattleMoEVM` `setPosition`/`resetPosition` commands + `properties=7`→6 fix, `place_fraction` refactor + seed, `onResetMod` reset) so persistence + reset ship even if free-drag proves infeasible (fallback: MSA X/Y-fraction steppers / arrow-nudge). **Move the WINDOW via Python `move()`, never the DOM element.** Full mechanics in the plan file + the deeper design captured this session.

---

## Dev quickref
- Build+deploy (client CLOSED): `& "C:\Python27\python.exe" build\deploy_wotmod.py "D:/Games/World_of_Tanks_EU" 2.3.0.1`
- Garage JS/CSS hot-reload (client open): `& "<py3>" tools\dev\sync_gameface.py "D:/Games/World_of_Tanks_EU" 2.3.0.1` → switch screens. **Battle overlay: NO hot-reload, full relaunch.**
- Tests: `& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" -m pytest -q`
- REPL: `& "<py3>" tools\dev\repl_client.py "<expr>"` (needs `com.14th_ua.moe_calculator_debug.wotmod`, :2224).
- Decompile (grep symbols): `C:\Users\Dmytro Vasylkivskyi\wot-eu\source\res\scripts\client\`.
