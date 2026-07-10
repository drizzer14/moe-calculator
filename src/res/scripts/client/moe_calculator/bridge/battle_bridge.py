# -*- coding: utf-8 -*-
"""Bridge: drive the in-battle MoE overlay -- open/close its window, arm the engine
listeners, and push the recomputed model into the window view's ViewModel.

The overlay is a standalone OpenWG-registered Gameface WINDOW opened over the battle HUD
(see bridge/battle_view.py for WHY a window and not a garage-style sub-view inject). This
module owns the lifecycle: on battle start (avatar ready) it opens the window and arms the
efficiency listener; on battle end (avatar becomes non-player) it destroys the window. A
burst of onTotalEfficiencyUpdated collapses to one deferred push.

    All symbols VERIFIED (decompile + live replay, 2.3.0.1): the PlayerEvents arena hooks
    and personalEfficiencyCtrl.onTotalEfficiencyUpdated. Re-arm every battle: the arena
    teardown rebuilds the controllers/event lists each match.
"""
import BigWorld

from moe_calculator._compat import LOG_CURRENT_EXCEPTION, LOG_NOTE
from moe_calculator.adapter import battle_adapter
from moe_calculator.adapter import moe_data
from moe_calculator.domain.battle_builder import build_battle_model, battle_bar_visible
from moe_calculator.bridge import battle_view

# Set while a coalesced refresh is queued, so a burst of onTotalEfficiencyUpdated fires
# collapses to a single deferred refresh().
_refresh_pending = False

# Whether we've registered our one-time listener on the async MoE-table loader (so the
# overlay re-pushes and reveals once the per-tank thresholds finish loading).
_data_listener_armed = False


# --- engine event subscriptions ---------------------------------------------
# Handlers are module-level (stable identity) so the membership-checked _arm is idempotent.

def _on_mount_refresh(*args, **kwargs):
    # Avatar ready -> we're in a battle: open the overlay window, (re)arm the efficiency
    # listener, kick the thresholds loader, and push the initial model.
    try:
        battle_view.open_window()
        install_all_listeners()
        moe_data.start()  # idempotent; the garage path may already have kicked it
        refresh()
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _on_arena_period_changed(*args, **kwargs):
    # Arena period changed (PREBATTLE -> BATTLE ...) -> re-push so the overlay reveals/hides.
    try:
        refresh()
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _on_efficiency_updated(*args, **kwargs):
    # personalEfficiencyCtrl.onTotalEfficiencyUpdated(totals): live cumulative stats changed.
    # Coalesce onto the next tick so a burst collapses to one push.
    try:
        _schedule_refresh()
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _on_observed_vehicle_changed(*args, **kwargs):
    # vehicleState.onVehicleControlling / onPostMortemSwitched: the observed vehicle changed
    # (died into postmortem, or cycled to another spectated ally). Re-push so the overlay
    # hides while spectating someone else and reveals again if control returns to us.
    # Efficiency events may not fire while spectating, so this is the signal we need.
    try:
        refresh()
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _on_teardown(*args, **kwargs):
    # Avatar became non-player (battle exit) -> tear down the overlay window; the next
    # battle mount re-opens it. The event lists are rebuilt by the arena teardown regardless.
    try:
        battle_view.close_window()
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _on_scale_changed(*args, **kwargs):
    # Interface scale changed mid-battle (settingsCore.interfaceScale.onScaleChanged) -> the
    # logical GUI space resized, so re-place the overlay to keep it tracking WG's efficiency
    # panel (the fixed logical anchor is scale-invariant, but the window must be re-applied
    # because the movable extent changed).
    try:
        battle_view.apply_position()
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _on_settings_changed(diff):
    # settingsCore.onSettingsChanged(diff): the "Summarized damage" DAMAGE_LOG group drives
    # our anchor (all four unticked -> summary block collapses -> events shift up -> raised
    # anchor). Re-place only when one of those four flags changed. Fail-open (re-place anyway
    # if the constants can't be resolved) -- a spurious re-place is harmless (idempotent).
    try:
        from account_helpers.settings_core.settings_constants import DAMAGE_LOG
        flags = (DAMAGE_LOG.TOTAL_DAMAGE, DAMAGE_LOG.BLOCKED_DAMAGE,
                 DAMAGE_LOG.ASSIST_DAMAGE, DAMAGE_LOG.ASSIST_STUN)
        if diff is None or any(f in diff for f in flags):
            battle_view.apply_position()
    except Exception:
        LOG_CURRENT_EXCEPTION()
        try:
            battle_view.apply_position()
        except Exception:
            LOG_CURRENT_EXCEPTION()


def _on_moe_data_ready():
    # The MoE-data source signalled ready (a WG-API fetch round completed on the main-thread poll).
    # Re-push so the overlay (hidden while hasData is false) reveals with numbers.
    try:
        LOG_NOTE("[moe-battle] table ready -> refresh")
        refresh()
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _player_events_holder():
    from PlayerEvents import g_playerEvents
    return g_playerEvents


def _efficiency_holder():
    return battle_adapter._efficiency_ctrl()  # None until the controller exists -> skipped


def _vehicle_state_holder():
    # sessionProvider.shared.vehicleState -- the OBSERVED_VEHICLE_STATE controller. None until
    # the arena spins it up -> _arm skips and retries next mount.
    sp = battle_adapter._session_provider()
    return sp.shared.vehicleState if (sp and sp.shared) else None


def _interface_scale_holder():
    # settingsCore.interfaceScale -- exposes onScaleChanged (Event.Event). None if the core is
    # unavailable -> _arm skips. Unlike the arena controllers this persists across battles, so
    # re-arming is idempotent (the membership check keeps it a single subscription).
    sc = battle_adapter._settings_core()
    return sc.interfaceScale if sc is not None else None


def _settings_core_holder():
    # settingsCore itself -- exposes onSettingsChanged (fired with a {name: value} diff). Used
    # to re-place the overlay when the "Summarized damage" DAMAGE_LOG group toggles. Persists
    # across battles like interfaceScale, so re-arming is idempotent (membership-checked).
    return battle_adapter._settings_core()


# (label, holder-getter, event-attribute, handler)
_LISTENERS = (
    ("avatar ready", _player_events_holder, "onAvatarReady", _on_mount_refresh),
    ("avatar teardown", _player_events_holder, "onAvatarBecomeNonPlayer", _on_teardown),
    ("arena period", _player_events_holder, "onArenaPeriodChange", _on_arena_period_changed),
    ("efficiency", _efficiency_holder, "onTotalEfficiencyUpdated", _on_efficiency_updated),
    # Observed-vehicle changes drive the spectate hide/reveal (postmortem free-look).
    ("observed vehicle", _vehicle_state_holder, "onVehicleControlling",
     _on_observed_vehicle_changed),
    ("postmortem", _vehicle_state_holder, "onPostMortemSwitched",
     _on_observed_vehicle_changed),
    # Interface-scale changes re-place the overlay so it keeps tracking WG's efficiency panel.
    ("interface scale", _interface_scale_holder, "onScaleChanged", _on_scale_changed),
    # "Summarized damage" DAMAGE_LOG group toggles re-place the overlay (raised vs default).
    ("settings", _settings_core_holder, "onSettingsChanged", _on_settings_changed),
)


def _arm(label, get_holder, attr, handler):
    """Subscribe `handler` to holder.<attr> iff not already present, storing the augmented
    Event back onto the attribute (WoT's += does not reliably mutate in place). Self-healing
    + idempotent; a not-yet-ready holder just skips (retried next mount)."""
    try:
        holder = get_holder()
        if holder is None:
            return
        event = getattr(holder, attr, None)
        if event is not None and handler not in event:
            event += handler
            setattr(holder, attr, event)
            LOG_NOTE("[moe-battle] %s listener (re)armed" % label)
    except Exception:
        LOG_CURRENT_EXCEPTION()


def install_all_listeners():
    """(Re)arm every battle listener + the one-time MoE-data ready hook. Safe to call on
    every battle mount -- the arena teardown drops the delegates and rebuilds the
    controllers, and this restores them."""
    global _data_listener_armed
    for entry in _LISTENERS:
        _arm(*entry)
    if not _data_listener_armed:
        try:
            moe_data.add_ready_listener(_on_moe_data_ready)
            _data_listener_armed = True
        except Exception:
            LOG_CURRENT_EXCEPTION()


def _schedule_refresh():
    """Coalesce a refresh onto the next tick (main thread -> transaction is safe)."""
    global _refresh_pending
    if _refresh_pending:
        return
    _refresh_pending = True
    try:
        BigWorld.callback(0.0, _do_scheduled_refresh)
    except Exception:
        _refresh_pending = False
        LOG_CURRENT_EXCEPTION()
        try:
            refresh()
        except Exception:
            LOG_CURRENT_EXCEPTION()


def _do_scheduled_refresh():
    global _refresh_pending
    _refresh_pending = False
    try:
        refresh()
    except Exception:
        LOG_CURRENT_EXCEPTION()


# --- push --------------------------------------------------------------------

def refresh():
    """Re-push the current battle model into the open overlay window's ViewModel."""
    view = battle_view.active_view()
    if view is None:
        return False
    push(view.viewModel)
    return True


def push(rvm):
    """Recompute the in-battle MoE model and write it into rvm."""
    if rvm is None:
        return
    try:
        snap = battle_adapter.build_battle_snapshot()
        model = build_battle_model(snap)
        visible = battle_bar_visible(snap.in_battle, snap.has_vehicle, snap.is_spectating)
        LOG_NOTE("[moe-battle] push visible=%s spectating=%s cd=%d pct=%.1f delta=%.2f data=%s baseline=%s" % (
            visible, snap.is_spectating, model.combined_damage, model.cur_percent,
            model.pct_delta, model.has_data, model.has_baseline))
        with rvm.transaction() as tx:
            tx.setVisible(visible)
            tx.setCombinedDamage(model.combined_damage)
            tx.setProjAvgDamage(model.proj_avg_damage)
            tx.setCurPercent(model.cur_percent)
            tx.setPctDelta(model.pct_delta)
            tx.setHasData(model.has_data)
            tx.setHasBaseline(model.has_baseline)
    except Exception:
        LOG_CURRENT_EXCEPTION()
