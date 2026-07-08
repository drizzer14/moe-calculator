# Research: Hide in-battle widget while spectating another player

_Submitted: "hide the widget when other player is selected in spectator mode" · Status: SHIPPED (unit-tested; pending live confirm)_

> **DONE 2026-07-07:** implemented exactly as the Suggested approach below.
> - `adapter/battle_adapter.py`: new fail-soft `_is_spectating()` (own `getPlayerVehicleID()`
>   vs observed `vehicleState.getControllingVehicleID()`, WG's `hit_direction_ctrl` test),
>   set on the snapshot in `build_battle_snapshot()`.
> - `domain/battle_types.py`: `is_spectating` field on `BattleSnapshot`.
> - `domain/battle_builder.py`: `battle_bar_visible(in_battle, has_vehicle, is_spectating=False)`
>   → `and not is_spectating`.
> - `bridge/battle_bridge.py`: `_vehicle_state_holder()` + two re-armed listeners
>   (`onVehicleControlling`, `onPostMortemSwitched` → `_on_observed_vehicle_changed`),
>   visibility call updated.
> - `tests/test_battle_builder.py`: spectating cases. 50 tests pass.
> Live confirm still needed (replay: die → hides while spectating allies; no hot-reload).

## Summary

After the local player dies and spectates teammates (postmortem free-look), the overlay keeps
showing — but the readout becomes **meaningless**: the tank *identity* (int_cd, thresholds)
follows the spectated vehicle while the damage *stats* stay the local player's. Hide the
overlay whenever a **different** player's vehicle is being observed. This is really a latent
correctness bug, not just a cosmetic hide (see Findings §A).

## Findings

### A. Why the current readout is wrong while spectating (the real bug)
- **Vehicle identity follows the observed vehicle.**
  `battle_adapter._player_vehicle_descr()` (`adapter/battle_adapter.py:63-82`) reads the id from
  `vehicleState.getControllingVehicleID()` (line 72) — the *observed/controlled* vehicle — then
  looks it up in `BigWorld.player().arena.vehicles[vid]` (73-79). Its docstring even says it's
  "the observed/controlled vehicle so it also works while spectating in a replay." So int_cd,
  nation, and the per-tank threshold table switch to whoever you're watching.
- **Damage stats do NOT reset on spectate — they stay yours.**
  `_read_efficiency()` (`battle_adapter.py:46-60`) calls
  `sessionProvider.shared.personalEfficiencyCtrl.getTotalEfficiency(...)`
  (`_efficiency_ctrl()`, 38-43). That controller only clears for a **dedicated observer role**,
  not postmortem spectating: `personal_efficiency_ctrl.py:361-364` clears the log only
  `if self.__arenaDP.isPlayerObserver()` and never touches `__totalEfficiency`.
- **Net:** while spectating, the overlay shows *your* accumulated damage measured against the
  *spectated tank's* thresholds → a nonsense percent/delta. That's exactly what to hide.

### B. Current visibility gate (where to add the condition)
- Pure gate: `battle_bar_visible(in_battle, has_vehicle)` — `domain/battle_builder.py:116-119`
  (only checks readable vehicle + active BATTLE period). Extend this (keep it pure/tested).
- Snapshot type `BattleSnapshot` — `domain/battle_types.py:11-46`; populated by
  `battle_adapter.build_battle_snapshot()` — `battle_adapter.py:117-146`.
- Bridge computes visibility + pushes at `battle_bridge.py:177`.
- The mod has **no notion of observed-vs-own today.**

### C. Game API — detect "observing someone else" ✅
- **Own vehicle id:** `avatar_getter.getPlayerVehicleID()`
  (`gui/battle_control/avatar_getter.py:69-72`, `getattr(avatar,'playerVehicleID',0)`) or
  `BigWorld.player().playerVehicleID`.
- **Observed vehicle id:** `sessionProvider.shared.vehicleState.getControllingVehicleID()`
  (`gui/battle_control/controllers/vehicle_state_ctrl.py:252-253`; the controller's id is
  `BATTLE_CTRL_ID.OBSERVED_VEHICLE_STATE`). WG itself treats this as the observed vehicle
  (`Avatar.py:1382,1588,1787,1799`).
- **The exact test WG uses for "looking at someone else":**
  `hit_direction_ctrl/ctrl.py:147` →
  `if arenaDP.getPlayerVehicleID() != vehicleState.getControllingVehicleID(): self._hideAllHits()`
  — adopt this comparison verbatim.
- **Do NOT use `Avatar.isObserver()`** (`Avatar.py:1863-1866`) — it's true only for the
  dedicated observer/spectator *role* (training rooms), **not** normal postmortem spectating.
- **Change events to re-evaluate on:** `vehicleState.onVehicleControlling(vehicle)`
  (declared `vehicle_state_ctrl.py:200`, fired 338 & 363 on setup/switch) — the canonical
  "observed vehicle changed" signal; and `vehicleState.onPostMortemSwitched(...)`
  (declared :201, fired :311) — fires the instant you die into postmortem. Efficiency events
  may not fire while spectating, so these are needed to refresh visibility.

## Suggested approach
1. **Adapter:** add a fail-soft reader (own vs observed) and set `is_spectating` on
   `BattleSnapshot`:
   `own = getPlayerVehicleID(); observed = vehicleState.getControllingVehicleID();
   is_spectating = bool(own) and bool(observed) and own != observed`.
   Populate in `build_battle_snapshot()` (`battle_adapter.py:117-146`). (`_player_vehicle_descr`
   already uses the observed id, so identity/thresholds stay consistent with what's on screen —
   you only suppress display.)
2. **Domain:** extend `battle_bar_visible` (`battle_builder.py:116`) →
   `return has_vehicle and in_battle and not is_spectating`. Keep pure; update the call at
   `battle_bridge.py:177` and add cases to `tests/test_battle_builder.py`.
3. **Bridge listeners:** register two more on `sessionProvider.shared.vehicleState` in
   `_LISTENERS` (`battle_bridge.py:93-98`), reusing the idempotent `_arm` re-subscribe
   (rebuilt each arena, so re-arming on `onAvatarReady` is correct):
   - `onVehicleControlling` → refresh
   - `onPostMortemSwitched` → refresh
   (Any existing refresh handler works, e.g. `_on_arena_period_changed`.)

## Touch points
- `adapter/battle_adapter.py` — new own-vs-observed reader + `build_battle_snapshot` (117-146).
- `domain/battle_types.py:11-46` — add `is_spectating` to `BattleSnapshot`.
- `domain/battle_builder.py:116-119` — extend `battle_bar_visible`.
- `bridge/battle_bridge.py:93-98` (listeners), `:177` (visibility call), + a
  `vehicleState` holder getter.
- `tests/test_battle_builder.py` — visibility cases (spectating → hidden).

## Verification
- Unit: `battle_bar_visible(..., is_spectating=True)` → False; alive → True.
- In-game (no hot-reload — full relaunch; see `in-battle-moe-styling.md`): in a battle/replay,
  confirm the overlay shows while alive, then **hides** the moment you die and the camera moves
  to a teammate, and stays hidden as you cycle spectated allies. (A replay is the easy repro.)
- REPL probe (run alive, then after dying and cycling allies):
  ```python
  import BigWorld
  from helpers import dependency
  from skeletons.gui.battle_session import IBattleSessionProvider
  sp = dependency.instance(IBattleSessionProvider); p = BigWorld.player()
  vs = sp.shared.vehicleState
  print("own=%r observed=%r isObserver=%r eff=%r" % (
      p.playerVehicleID, vs.getControllingVehicleID(), p.isObserver(),
      sp.shared.personalEfficiencyCtrl.getTotalEfficiency(1)))
  ```
  Expect alive: `own == observed`. Spectating a teammate: `own != observed`, `isObserver` still
  False, `eff` unchanged (still your damage) — the mismatch that justifies hiding.

## Open questions
- Timing: does `getControllingVehicleID()` momentarily return 0/`UNKNOWN_VEHICLE_ID` mid-switch,
  and does it cleanly equal `playerVehicleID` at battle start before any death? Both *should*
  hold (`setPlayerVehicle` sets it to your own id at spawn) — confirm live via the probe. The
  `bool(own) and bool(observed)` guard already makes a transient 0 fail-safe (stays visible, not
  wrongly hidden — acceptable).
- Should we also hide during the brief death→postmortem transition, or only once a *different*
  vehicle is controlled? The id-comparison handles both naturally.

## Cross-references
- `TASKS/in-battle-moe-handoff.md` — live findings + BUG B (empty replay baseline).
- `TASKS/in-battle-moe-styling.md` — no-hot-reload constraint, prior input-steal history.
