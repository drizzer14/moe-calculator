# Research: Garage bridge lifecycle — stale `_active`, no teardown

_Submitted: repo-wide bug hunt (2026-07-09) · Status: PARTIALLY SHIPPED (2026-07-09, 76fa5c3)_

> **Shipped:** the `refresh()` view-alive guard (`_host_alive()` early-returns when the lobby
> host is gone, so a mid-battle threshold-fetch / items-cache push no longer hits a dead VM)
> and Rider 1 (garage `_arm` `getattr` aligned to the battle twin's `None` default).
> **Still open:** a real `_active` teardown (no view-destroy hook is wired -- the guard makes
> stale `_active` harmless but doesn't clear it) and **Rider 2** (does OpenWG re-execute
> injected modules per mount, stacking `observer.onUpdate` callbacks?) -- needs a live REPL probe.

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

### Rider 2 — front-end remount observer stacking (UNCONFIRMED)

- `MoECalculator.js:325-329` (approx) registers `observer.onUpdate(render)` +
  `observer.subscribe()` at module top-level inside `engine.whenReady`. Python re-injects
  the assets on every `_onLoading` (mod_moe_calculator.py:31-45). If OpenWG re-executes the
  module per injection, each hangar mount stacks another `onUpdate` callback (leak +
  redundant renders). If it dedupes by URL, no leak. Cannot confirm without `libs/model.js`
  / the injector source.

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

- Is there a clean view-destroy signal to hang teardown on, or must `refresh()` self-guard?
- Rider 2: does OpenWG re-execute injected modules per mount? (Decides leak vs. no-op.)
