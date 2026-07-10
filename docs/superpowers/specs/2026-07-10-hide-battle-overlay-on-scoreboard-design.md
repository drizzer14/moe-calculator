# Hide the in-battle MoE overlay while the scoreboard is open

## Problem

The live in-battle MoE readout (a small corner window over the battle HUD) stays
painted when WG's full-screen scoreboard is up, cluttering it. It should hide
whenever the player opens the scoreboard family of overlays, and reappear when
they close it.

## Scope

Hide the overlay while any of WG's **full-stats scoreboard** views is open:

- `GameEvent.FULL_STATS` — the Tab scoreboard
- `GameEvent.FULL_STATS_QUEST_PROGRESS` — the personal-missions / quest-progress tab
- `GameEvent.FULL_STATS_PERSONAL_RESERVES` — the personal-reserves tab
- `GameEvent.EVENT_STATS` — the event-mode scoreboard (special game modes)

**Out of scope (overlay stays visible):**

- **Ctrl free-look** — raising the cursor to click the HUD while still driving.
  It fires `SHOW_CURSOR`, not a `FULL_STATS` toggle, so it is naturally excluded.
- **F1 help** (`INGAME_HELP` / `INGAME_DETAILS_HELP`) and the **ESC in-game menu**
  (`INGAME_MENU`). These are Scaleform view-loads with no matching boolean close
  event; deliberately dropped to keep the signal clean.

## Why these signals

All four events are dispatched on `g_eventBus` at `EVENT_BUS_SCOPE.BATTLE`, each
carrying `ctx['isDown']` (`True` on open, `False` on close). This is exactly the
mechanism WG's own `gui.Scaleform.daapi.view.battle.shared.damage_log_panel`
(`__handleShowFullStats`) and `battle.shared.page` use to gate themselves. Our
overlay already tracks that damage-log panel's position, so mirroring its
visibility behaviour is the faithful, low-risk choice — no view-load/close
tracking, no polling.

Verified against the `~/wot-eu` 2.3.0.1 decompile:

- `gui/battle_control/event_dispatcher.py` — `toggleFullStats(isDown)`,
  `toggleFullStatsQuestProgress(isDown)`, `toggleFullStatsPersonalReserves(isDown)`,
  `toggleEventStats(isDown)` each `handleEvent(GameEvent(..., _makeKeyCtx(isDown=isDown)), scope=BATTLE)`.
- `gui/shared/events.py` — the four `GameEvent` constants exist.
- `gui/shared/__init__.py` — `g_eventBus = EventBus()`; exports `EVENT_BUS_SCOPE`.

## Design

All new logic lives in `bridge/battle_bridge.py` (the existing owner of the
overlay lifecycle and push), plus one pure-function change in
`domain/battle_builder.py`.

### 1. Domain (pure, unit-tested)

Extend `battle_builder.battle_bar_visible` with a new trailing keyword:

```python
def battle_bar_visible(in_battle, has_vehicle, is_spectating=False, overlay_open=False):
    return (bool(has_vehicle) and bool(in_battle)
            and not bool(is_spectating) and not bool(overlay_open))
```

The default keeps every existing caller unchanged. The overlay flag is a hard
override: an open scoreboard hides the readout regardless of the other inputs.

### 2. Bridge state

In `bridge/battle_bridge.py`:

- A module-level `set` of the currently-*down* scoreboard event keys
  (`_open_overlays`). Deriving `overlay_open = bool(_open_overlays)` this way
  tolerates overlapping toggles (e.g. one scoreboard tab closing as another
  opens) without a brittle single boolean.
- One handler per event that reads `event.ctx.get('isDown')`, adds/removes its
  key, then calls the existing `_schedule_refresh()` to coalesce onto the next
  tick.

### 3. Arming (once, idempotent)

`g_eventBus` is a persistent singleton — BATTLE-scope listeners are **not** torn
down by arena teardown. So these four listeners are armed **once**, guarded by a
module flag (mirroring the existing `_data_listener_armed`), inside
`install_all_listeners()`. Re-adding on every battle mount would stack duplicate
subscriptions.

`_on_mount_refresh()` clears `_open_overlays` on each battle start (alongside the
existing `_battle_recorded` reset) so a stale flag from a prior battle / relogin
/ replay teardown can never leave the overlay hidden.

### 4. Push

`push()` folds the flag into the visibility decision:

```python
visible = battle_bar_visible(snap.in_battle, snap.has_vehicle,
                             snap.is_spectating, overlay_open=bool(_open_overlays))
```

No change to the VM contract or the transaction — `setVisible(visible)` already
exists. The existing debug `LOG_NOTE` gains the overlay flag for traceability.

### 5. Front-end

No change. `MoEBattle.js` already hides `#moe-battle-root` when `visible` is
false (the truthy `visible && hasData` guard).

## Error handling

Each new handler is wrapped in the module's existing `try/except
LOG_CURRENT_EXCEPTION()` pattern; a handler fault must never break battle input
or the overlay. A missing/oddly-shaped `ctx` is read fail-soft
(`event.ctx.get('isDown')` treated as falsy → key removed), so a malformed event
can only ever *reveal* the overlay, never wedge it hidden.

## Testing

Domain unit tests in `tests/test_battle_builder.py` (Python 3.13) for
`battle_bar_visible`:

- `overlay_open=True` → `False`, even when `in_battle` and `has_vehicle` are True
  and `is_spectating` is False.
- `overlay_open=False` (default) → unchanged from current behaviour (regression
  guard on the existing cases).
- `overlay_open` does not flip an already-hidden case to visible (e.g.
  `has_vehicle=False, overlay_open=False` stays `False`).

The bridge wiring is engine-coupled (imports `BigWorld`, `g_eventBus`) and stays
outside the unit suite, consistent with the existing battle-bridge code.

## Deployment

Python-only change. Build with Python 2.7.18 and deploy
(`build/deploy_wotmod.py`), then **full client relaunch** — the in-battle window
has no hot-reload. In-client verification: open a battle, press Tab (and the
personal-missions / reserves keys) — overlay hides on press, returns on release;
hold Ctrl free-look — overlay stays visible.

## Files touched

- `src/res/scripts/client/moe_calculator/domain/battle_builder.py` — new
  `overlay_open` param.
- `src/res/scripts/client/moe_calculator/bridge/battle_bridge.py` — open-set,
  four handlers, arm-once guard, mount reset, push fold-in.
- `tests/test_battle_builder.py` — new `battle_bar_visible` cases.
