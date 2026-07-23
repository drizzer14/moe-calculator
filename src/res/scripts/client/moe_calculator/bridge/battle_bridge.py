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

from moe_calculator._compat import LOG_CURRENT_EXCEPTION, LOG_DEBUG
from moe_calculator.adapter import battle_adapter
from moe_calculator.adapter import battle_input
from moe_calculator.adapter import moe_wgapi
from moe_calculator.domain.battle_builder import build_battle_model, battle_bar_visible
from moe_calculator.domain.constants import EFFICIENCY_WIDE_THRESHOLD
from moe_calculator.domain.positioning import efficiency_panel_wide
from moe_calculator.bridge import battle_view
from moe_calculator.bridge import mod_settings

# Set while a coalesced refresh is queued, so a burst of onTotalEfficiencyUpdated fires
# collapses to a single deferred refresh().
_refresh_pending = False

# Whether we've registered our one-time listener on the async MoE-table loader (so the
# overlay re-pushes and reveals once the per-tank thresholds finish loading).
_data_listener_armed = False

# Whether we've promoted the played tank into the permanent fetch list this battle. Reset on
# each battle mount; set once we can read the player's OWN vehicle (see push). Recording here
# -- off the persistent PlayerEvents lifecycle, where the played vehicle is known -- is far more
# reliable than the garage-side onResultPosted, whose subscription is torn down with the hangar
# during the battle and re-armed only after the result has already posted.
_battle_recorded = False

# The full-stats scoreboard views currently open, keyed by their g_eventBus eventType. While
# any is open the overlay hides (it would otherwise clutter the full-screen scoreboard). All
# four are dispatched on g_eventBus at EVENT_BUS_SCOPE.BATTLE with ctx['isDown'] (True open /
# False close) -- this mirrors WG's own damage_log_panel gating (see battle.shared.page).
# Deliberately EXCLUDED: Ctrl free-look (SHOW_CURSOR), F1 help and the ESC menu all keep the
# readout visible.
_open_overlays = set()

# Whether the g_eventBus scoreboard listeners are armed. Unlike the arena controllers (rebuilt
# every battle), g_eventBus is a persistent singleton whose BATTLE-scope listeners survive
# arena teardown -- so we arm ONCE and never re-add (a second add would only warn + no-op).
_overlay_listeners_armed = False

# Last-applied "efficiency panel is 5-digit wide" state (see domain.efficiency_panel_wide).
# The overlay opens at damage 0 (condition False), so the right-shift can only engage LATER,
# when a total crosses the threshold mid-battle. We re-place the window when this flips (not on
# every efficiency tick -- window.move is comparatively costly). None = not yet evaluated this
# battle; reset on each mount.
_last_wide = None


# True between avatar-ready and avatar-non-player, i.e. while we're in a battle. Tracked even
# when the overlay is disabled so a live enable (apply_settings) knows to open the window now.
_in_battle = False


# Whether Alt is currently held, as reported by the event-driven battle_input hook. Drives the
# "Show on Alt Key" mode: while the In-Battle Widget master is on AND that mode is on, the
# overlay's visible flag follows this. Whether the mode CARES is decided in battle_bar_visible.
_alt_held = False


# --- engine event subscriptions ---------------------------------------------
# Handlers are module-level (stable identity) so the membership-checked _arm is idempotent.

def _on_mount_refresh(*args, **kwargs):
    # Avatar ready -> we're in a battle: open the overlay window, (re)arm the efficiency
    # listener, kick the thresholds loader, and push the initial model. Reset the played-tank
    # record so this battle promotes its vehicle exactly once (see push).
    global _battle_recorded, _last_wide, _in_battle
    try:
        _in_battle = True
        _battle_recorded = False
        # Re-evaluate the 5-digit shift from scratch this battle (totals reset to 0).
        _last_wide = None
        # Clear any scoreboard flag left over from a prior battle / relogin / replay teardown,
        # so a stale key can never keep the fresh battle's overlay hidden.
        _open_overlays.clear()
        if not mod_settings.battle_enabled():
            # The In-Battle Widget master is off -> the overlay is never shown, so don't open
            # the window this battle (the "Show on Alt Key" child is inert while the master is
            # off). A live enable opens it mid-battle (see apply_settings); _in_battle stays
            # True so that path fires.
            return
        battle_view.open_window()
        install_all_listeners()
        moe_wgapi.start()  # idempotent; the garage path may already have kicked it
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


def _on_summary_feedback(*args, **kwargs):
    # feedback.onPlayerSummaryFeedbackReceived(event): the server pushed a fresh battle-events
    # summary -- the source of the track/spot assist split (counted-assistance row). Coalesce a
    # push so the row updates promptly. (push() re-reads the cached summary either way; this just
    # makes it timely rather than waiting for the next efficiency tick.)
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
    global _in_battle
    try:
        _in_battle = False
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
        LOG_DEBUG("[moe-battle] table ready -> refresh")
        refresh()
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _on_scoreboard_toggled(event):
    # A full-stats scoreboard view (Tab / personal missions / reserves / event stats) opened
    # or closed -> track which are down and re-push so the overlay hides while any is open and
    # reveals when the last closes. Read fail-soft: a missing/odd ctx can only DROP the key
    # (reveal the overlay), never wedge it hidden.
    try:
        ctx = getattr(event, "ctx", None) or {}
        key = getattr(event, "eventType", None)
        if ctx.get("isDown"):
            _open_overlays.add(key)
        else:
            _open_overlays.discard(key)
        _schedule_refresh()
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _set_alt_held(down):
    # battle_input's transition callback: Alt was pressed / released. Store it and re-push so
    # the overlay reveals/hides live under the "Battle Widget on Alt Key" peek mode. refresh()
    # is cheap and no-ops when no window is open (always-on off + peek off), so it's safe to
    # fire on every Alt transition regardless of which mode is active.
    global _alt_held
    try:
        _alt_held = bool(down)
        refresh()
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _player_events_holder():
    from PlayerEvents import g_playerEvents
    return g_playerEvents


def _efficiency_holder():
    return battle_adapter._efficiency_ctrl()  # None until the controller exists -> skipped


def _feedback_holder():
    # sessionProvider.shared.feedback -- the BattleFeedbackAdaptor whose battle-events summary
    # carries the track/spot assist split. None until the arena spins it up -> _arm retries.
    return battle_adapter._feedback_ctrl()


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
    # Server battle-events summary -> the track/spot assist split (counted-assistance row).
    ("summary feedback", _feedback_holder, "onPlayerSummaryFeedbackReceived",
     _on_summary_feedback),
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
            LOG_DEBUG("[moe-battle] %s listener (re)armed" % label)
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
            moe_wgapi.add_ready_listener(_on_moe_data_ready)
            _data_listener_armed = True
        except Exception:
            LOG_CURRENT_EXCEPTION()
    _arm_overlay_listeners()
    # Event-driven Alt-key hook for the "Battle Widget on Alt Key" peek mode. Installed once
    # (idempotent + self-healing: AvatarInputHandler may not be importable until a battle
    # exists, so a failed attempt retries on the next mount).
    battle_input.install_alt_key_listener(_set_alt_held)


def _arm_overlay_listeners():
    """Subscribe the scoreboard hide/reveal handler to the full-stats g_eventBus events, ONCE.
    These sit on the persistent g_eventBus (not the per-battle arena controllers), so re-arming
    each mount is unnecessary and would only warn. Fail-soft: an unavailable event bus just
    leaves the overlay always-visible (its prior behaviour)."""
    global _overlay_listeners_armed
    if _overlay_listeners_armed:
        return
    try:
        from gui.shared import g_eventBus, EVENT_BUS_SCOPE
        from gui.shared.events import GameEvent
        events = (GameEvent.FULL_STATS, GameEvent.FULL_STATS_QUEST_PROGRESS,
                  GameEvent.FULL_STATS_PERSONAL_RESERVES, GameEvent.EVENT_STATS)
        for ev in events:
            g_eventBus.addListener(ev, _on_scoreboard_toggled, scope=EVENT_BUS_SCOPE.BATTLE)
        _overlay_listeners_armed = True
        LOG_DEBUG("[moe-battle] scoreboard hide listeners armed")
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
    _maybe_replace_for_width()


def _maybe_replace_for_width():
    """Re-place the overlay when the "efficiency panel is 5-digit wide" state flips (a total
    crossed the threshold), so the right-shift engages/disengages live. Coalesced onto the
    efficiency refresh; a no-op when the state is unchanged (avoids a window.move every tick).
    Fail-soft: a bad read leaves the position untouched."""
    global _last_wide
    try:
        wide = efficiency_panel_wide(battle_adapter.read_damage_log_summary_flags(),
                                     battle_adapter.read_efficiency_totals(),
                                     EFFICIENCY_WIDE_THRESHOLD)
        if wide != _last_wide:
            _last_wide = wide
            battle_view.apply_position()
    except Exception:
        LOG_CURRENT_EXCEPTION()


# --- fetch-list promotion ----------------------------------------------------

def _record_played_tank(snap):
    """Promote the tank this battle is being fought in from the fetch list's temp set to the
    permanent list -- once per battle, as soon as we can read the player's OWN vehicle. Skips
    while spectating (a dead player observing a teammate: getControllingVehicleID would be the
    ally's tank, not ours). Guarded -- a promotion failure must never break the overlay push."""
    global _battle_recorded
    if _battle_recorded:
        return
    try:
        if snap.has_vehicle and not snap.is_spectating and snap.vehicle_int_cd:
            moe_wgapi.on_battle_played(snap.vehicle_int_cd)
            _battle_recorded = True
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
        _record_played_tank(snap)
        model = build_battle_model(snap)
        overlay_open = bool(_open_overlays)
        visible = battle_bar_visible(snap.in_battle, snap.has_vehicle, snap.is_spectating,
                                     overlay_open=overlay_open,
                                     enabled=mod_settings.battle_enabled(),
                                     alt_mode=mod_settings.battle_alt_key_enabled(),
                                     alt_held=_alt_held)
        assist_visible = mod_settings.counted_assistance_enabled()
        LOG_DEBUG("[moe-battle] push visible=%s spectating=%s scoreboard=%s alt=%s cd=%d pct=%.1f delta=%.2f data=%s baseline=%s assist=%d/%s(on=%s)" % (
            visible, snap.is_spectating, overlay_open, _alt_held, model.combined_damage,
            model.cur_percent, model.pct_delta, model.has_data, model.has_baseline,
            model.counted_assist, model.assist_kind, assist_visible))
        with rvm.transaction() as tx:
            tx.setVisible(visible)
            tx.setCombinedDamage(model.combined_damage)
            tx.setProjAvgDamage(model.proj_avg_damage)
            tx.setCurPercent(model.cur_percent)
            tx.setPctDelta(model.pct_delta)
            tx.setHasData(model.has_data)
            tx.setHasBaseline(model.has_baseline)
            tx.setCountedAssist(model.counted_assist)
            tx.setAssistKind(model.assist_kind)
            tx.setAssistVisible(assist_visible)
    except Exception:
        LOG_CURRENT_EXCEPTION()


def apply_settings():
    """Apply the battle-overlay settings live (the mod_settings change callback).

    The window must exist whenever the "In-Battle Widget" master is on (the "Show on Alt Key"
    child is inert while the master is off, so it never opens the window on its own). Master off
    -> close it if open. Master on while in a battle -> open it now (arm + kick data + push) so
    the toggle takes effect without waiting for the next battle. (Under the Alt-key mode the
    window opens but stays hidden until Alt is held -- push/battle_bar_visible decides visible.)"""
    try:
        if not mod_settings.battle_enabled():
            if battle_view.active_view() is not None:
                battle_view.close_window()
            return
        if _in_battle and battle_view.active_view() is None:
            battle_view.open_window()
            install_all_listeners()
            moe_wgapi.start()
            refresh()
        else:
            # Window already open (or not in battle) -> just re-push so a live mode switch
            # (e.g. Alt-key mode toggled) re-evaluates the visible flag immediately.
            refresh()
    except Exception:
        LOG_CURRENT_EXCEPTION()
