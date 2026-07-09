# Research: Garage bridge lifecycle — stale `_active`, no teardown

_Submitted: repo-wide bug hunt (2026-07-09) · Status: **RESOLVED / CLOSED** (2026-07-09) — refresh guard + `_active` teardown shipped (76fa5c3, c4e60df); Rider 2 resolved statically (no leak, no code change)_

> **Shipped (76fa5c3):** the `refresh()` view-alive guard (`_host_alive()` early-returns when
> the lobby host is gone, so a mid-battle threshold-fetch / items-cache push no longer hits a
> dead VM) and Rider 1 (garage `_arm` `getattr` aligned to the battle twin's `None` default).
> **Shipped (c4e60df, committed 2026-07-09, with the collision-aware feature — [[collision-aware-injection]]):**
> the real `_active` teardown. `bridge.detach()` now clears `_active` + the placement
> commitment (`_placed_name`/`_placed_vm`) + the cached candidate VMs, and `refresh()` calls it
> on the host-gone branch (the lobby-state signal suggested below), so a return to the garage
> re-evaluates placement fresh instead of clinging to torn-down ViewModels. In-client verified
> (no `[moe]` push/exception spam during battle).
> **Rider 2 — RESOLVED (2026-07-09, static analysis of the OpenWG 1.1.6 injector; no code change):**
> OpenWG does NOT stack `observer.onUpdate` callbacks across garage remounts. Three independent
> mechanisms guarantee it (see the updated Rider 2 section below). No guard needed.

## Summary

The hangar bridge caches the mounted widget as a module global `_active` on attach and
never clears it. Session-persistent listeners (the MoE-table ready hook, the items-cache
sync hook) can therefore fire after the hangar sub-view is destroyed — most visibly when
the background threshold fetch completes **mid-battle** — pushing into a dead ViewModel.
It's fail-soft (wrapped in try/except) but does wasted work and spams handled exceptions
into `python.log`. Two adjacent robustness items ride along.

## Findings

- `bridge/gameface_bridge.py:52` — `_active = None`; set at `:296`
  (`_active = (host_vm, rvm)` in `attach()`); **never reassigned to `None` anywhere** in
  the file. There is no detach/teardown hook at all.
- `refresh()` (gameface_bridge.py:306-312) pushes into `_active[1]` whenever called.
- The MoE-data ready hook `_on_moe_data_ready` (gameface_bridge.py:119-126) calls
  `refresh()`; it is registered once via `moe_data.add_ready_listener` and lives on the
  session-persistent `moe_data` module. The fetch is kicked in the garage
  (`attach()` → `moe_data.start()`, gameface_bridge.py:299) and completes seconds later,
  potentially after the player has entered battle and the hangar VM is gone.
- `IItemsCache.onSyncCompleted` (`_on_sync_completed`, gameface_bridge.py:110-116) is
  likewise on a session-persistent object.

### Rider 1 — `_arm` getattr divergence

- `gameface_bridge.py:175` — `event = getattr(holder, attr)` (**no default**).
- `battle_bridge.py:181` — `event = getattr(holder, attr, None)` (defaults to `None`,
  then skips).
- If a WG event attribute is ever renamed across a client patch, the garage version raises
  `AttributeError` → caught + logged on **every** hangar mount, and that listener silently
  never arms. The battle twin degrades quietly. Align the garage version to the battle one.

### Rider 2 — front-end remount observer stacking (RESOLVED: no leak)

- `MoECalculator.js:324-326` registers `observer.onUpdate(render)` + `observer.subscribe()`
  at module top-level inside `engine.whenReady`. Python re-injects the assets on every
  `_onLoading` (mod_moe_calculator.py). The concern was that per-mount re-injection stacks a
  new `onUpdate` callback each time (leak + redundant renders).
- **Resolved by reading the OpenWG 1.1.6 injector + libs (extracted from
  `net.openwg.gameface_1.1.6.wotmod`).** No stacking is possible — three independent guards:
  1. **Injector dedups by resId.** `res/gui/gameface/js/index.js` keeps an `injectedResIds`
     `Set`; `injectModAssets` early-returns when the sub-view's resId is already present, so a
     given sub-view's assets are appended to the DOM **exactly once** regardless of how many
     times Python re-writes the `ModInjectModel`.
  2. **ES-module URL dedup.** We register on the `modules` channel
     (`gameface_bridge.py:333` → injector `assetTypes` `{type:"module", tag:"script",
     type:"module"}`), i.e. `<script type="module" src="coui://…/MoECalculator.js">`. Even if
     a same-URL module tag were appended again (a new resId within a still-living view),
     Gameface evaluates a module graph **once per (realm, URL)** — the top-level
     `observer.onUpdate(render)` does not re-run. (A classic `scripts`-channel tag WOULD
     re-execute; we do not use that channel.)
  3. **View-realm teardown.** The dominant real path — battle exit tears down and rebuilds the
     whole hangar Gameface view — creates a fresh JS realm (new `window`, fresh
     `injectedResIds`, fresh module instances). Old-realm `onUpdate` callbacks die with the old
     view and cannot accumulate into the new one.
- **Verdict:** no callback leak, no redundant-render growth, **no guard needed**. This was the
  last open piece of this note; the bug entry closes.

## Root cause

`attach()` has no symmetric detach. The bridge assumes the hangar widget lives for the
session, but battle entry tears down and rebuilds the hangar space, so `_active` outlives
its ViewModel while session-scoped listeners keep calling `refresh()`.

## Suggested approach

- Add a teardown path that clears `_active = None` when the hangar sub-view is destroyed.
  There is no destroy hook wired today — investigate the view lifecycle (the `_onLoading`
  monkey-patch in mod_moe_calculator.py is the mount side; find/instrument the unload side,
  or gate `refresh()` on "is the hangar view still current?" using the same lobby-state
  signal `_on_lobby_state_changed` already listens to).
- Cheapest partial fix: have `refresh()` verify the host view is still alive before pushing
  (guard the push, not just wrap it), turning silent exception spam into an early return.
- Fold in Rider 1 (one-line `getattr` default) while in this file.
- Resolve Rider 2 with a REPL probe (below) before deciding whether a guard is needed.

## Touch points

- `bridge/gameface_bridge.py` — `_active`, `attach`, `refresh`, `_on_moe_data_ready`,
  `_on_sync_completed`, `_arm`
- `gui/mods/mod_moe_calculator.py:29-46` — the `_onLoading` patch (mount side; teardown
  counterpart TBD)
- `src/res/gui/gameface/mods/14th_ua/MoECalculator/MoECalculator.js` (Rider 2 only)

## Verification

- In-client: select a tank in garage, immediately enter battle before the fetch finishes
  (or throttle it), confirm no `[moe]` push/exception lines land in `python.log` during the
  battle. Fixed = the ready hook early-returns.
- Rider 2 REPL probe: mount the hangar, leave and re-enter the garage a few times, then via
  the debug REPL inspect the observer's listener count (or add a temporary counter in
  `render`) to see whether callbacks accumulate.
- Existing 40+ unit tests are Python-domain only and won't cover this; manual/in-client.

## Open questions

- ~~Is there a clean view-destroy signal to hang teardown on, or must `refresh()` self-guard?~~
  RESOLVED: `refresh()` self-guards via `_host_alive()` and `detach()` on the host-gone branch.
- ~~Rider 2: does OpenWG re-execute injected modules per mount?~~ RESOLVED: no — injector
  dedups by resId, module execution is URL-deduped, and a torn-down view is a fresh realm.
