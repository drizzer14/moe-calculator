# -*- coding: utf-8 -*-
"""Bridge: attach our Gameface widget to a hangar sub-view and push the MoE model.

OpenWG's JS injector scans hangar SUB-views for a `ModInjectModel` and loads the listed
assets into the hangar document. So we inject onto a sub-view's ViewModel
(HangarVehicleParamsPresenter) and hang our own data model on it (property `moeData`),
which the widget JS reads via ModelObserver("MoECalculator").

This is the seam between the engine and the pure domain: it READS via the adapter,
builds the model via the domain, and MARSHALS it into Wulf ViewModels. See the
wotmod-architecture harness skill for the listener re-arm rationale and the Wulf event
`setattr`-back gotcha.
"""
import json

import BigWorld
from CurrentVehicle import g_currentVehicle
from helpers import dependency
from skeletons.gui.shared import IItemsCache

from moe_calculator._compat import LOG_CURRENT_EXCEPTION, LOG_NOTE
from moe_calculator.adapter import engine_adapter
from moe_calculator.adapter import moe_data
from moe_calculator.adapter import format as fmt
from moe_calculator.adapter import i18n
from moe_calculator.domain.builder import build_model, bar_visible
from moe_calculator.bridge.view_models import MoEVM, MarkTickVM
import openwg_gameface

WIDGET_NAME = "MoECalculator"
DATA_PROP = "moeData"
COUI = "coui://gui/gameface/mods/14th_ua/MoECalculator"

# The tooltip labels, resolved to the client language once and JSON-encoded for the VM's
# `labels` string prop. Cached module-side: the language doesn't change mid-session, so
# every push re-uses the same bundle instead of re-encoding it.
_labels_json_cache = None


def _labels_json():
    global _labels_json_cache
    if _labels_json_cache is None:
        try:
            _labels_json_cache = json.dumps(i18n.labels())
        except Exception:
            LOG_CURRENT_EXCEPTION()
            _labels_json_cache = "{}"
    return _labels_json_cache

# (host_vm, rvm) for the currently-mounted widget. Importable so the entry point and
# the dev REPL can drive refreshes without poking module-private state.
_active = None

# Set while a coalesced refresh is already queued for the next tick, so a burst of
# onSyncCompleted fires collapses to a single deferred refresh().
_refresh_pending = False

# Whether we've registered our one-time listener on the async MoE-table loader (so the
# bar re-pushes and reveals the damage labels once the fetch completes).
_data_listener_armed = False


# --- engine event subscriptions -------------------------------------------------
# WoT's Events store STRONG refs to their delegates, but the battle entry/exit teardown
# rebuilds the hangar space -- repopulating the event lists with WG's own presenters
# while dropping ours. So install_all_listeners() re-arms on every hangar mount,
# membership-checked. Handlers are module-level functions (stable identity). We subscribe
# via getattr/+=/setattr: WoT's Event augmented-add does not reliably mutate in place, so
# the result MUST be stored back onto the attribute or the subscription is silently lost.

def _on_vehicle_changed(*args, **kwargs):
    try:
        refresh()
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _on_interactor_updated(*args, **kwargs):
    # A tank-setup / ammo overlay opened or closed -> re-push so the bar hides/shows.
    try:
        refresh()
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _on_lobby_state_changed(*args, **kwargs):
    # The visible lobby view changed (garage <-> other views) -> re-push so the bar hides
    # off the plain garage and shows again on return.
    try:
        refresh()
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _on_settings_changed(diff):
    # settingsCore.onSettingsChanged(diff): re-push only when the carousel row-count or
    # double-carousel size changed (they drive the bar's bottom offset). Fail-open.
    try:
        from account_helpers.settings_core import settings_constants as sc
        if diff is None or sc.GAME.CAROUSEL_TYPE in diff or sc.GAME.DOUBLE_CAROUSEL_TYPE in diff:
            refresh()
    except Exception:
        LOG_CURRENT_EXCEPTION()
        try:
            refresh()
        except Exception:
            LOG_CURRENT_EXCEPTION()


def _on_sync_completed(*args, **kwargs):
    # IItemsCache.onSyncCompleted(updateReason, invalidItems). Coalesce onto the next tick
    # so a burst collapses to one push and CurrentVehicle has rebuilt its item.
    try:
        _schedule_refresh()
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _on_moe_data_ready():
    # The external thresholds table finished loading (fired on the main thread by
    # moe_data's poll). Re-push so the per-mark damage labels appear.
    try:
        LOG_NOTE("[moe] table ready -> refresh")
        refresh()
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _vehicle_holder():
    return g_currentVehicle


def _loadout_holder():
    from skeletons.gui.game_control import ILoadoutController
    return dependency.instance(ILoadoutController)


def _lobby_holder():
    from gui.Scaleform.lobby_entry import getLobbyStateMachine
    return getLobbyStateMachine()  # None until the lobby state machine exists


def _stats_holder():
    return dependency.instance(IItemsCache)


def _settings_holder():
    from skeletons.account_helpers.settings_core import ISettingsCore
    return dependency.instance(ISettingsCore)


# (label, holder-getter, event-attribute, handler) -- what the bar listens to.
#   vehicle  : vehicle-selection changes
#   loadout  : tank-setup (ammo) overlay open/close -> hide/show the bar
#   lobby    : garage <-> other lobby views -> hide off the plain garage
#   stats    : items-cache syncs (marks/rating updated after a battle sync)
#   settings : carousel row-count / size changes -> re-push the bottom offset
_LISTENERS = (
    ("vehicle", _vehicle_holder, "onChanged", _on_vehicle_changed),
    ("loadout", _loadout_holder, "onInteractorUpdated", _on_interactor_updated),
    ("lobby state", _lobby_holder, "onVisibleRouteChanged", _on_lobby_state_changed),
    ("stats", _stats_holder, "onSyncCompleted", _on_sync_completed),
    ("settings", _settings_holder, "onSettingsChanged", _on_settings_changed),
)


def _arm(label, get_holder, attr, handler):
    """Subscribe `handler` to holder.<attr> iff not already present, storing the
    augmented Event back onto the attribute. Self-healing + idempotent; guarded so a
    not-yet-ready holder just skips (retried next mount)."""
    try:
        holder = get_holder()
        if holder is None:
            return
        # Default to None (matches battle_bridge._arm): if a WG event attribute is renamed
        # across a client patch, this degrades quietly (listener skips + retries) instead of
        # raising AttributeError -> logged -- on every hangar mount.
        event = getattr(holder, attr, None)
        if event is not None and handler not in event:
            event += handler
            setattr(holder, attr, event)
            LOG_NOTE("[moe] %s listener (re)armed" % label)
    except Exception:
        LOG_CURRENT_EXCEPTION()


def install_all_listeners():
    """(Re)arm every engine listener + the one-time MoE-data ready hook. Safe to call on
    every hangar mount -- the battle exit teardown drops the hangar-scoped delegates and
    this restores them."""
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
    """Coalesce a refresh onto the next tick. BigWorld.callback runs on the main thread,
    so the push transaction is safe -- never use a timer thread here."""
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


# --- garage-visibility signals (engine reads) --------------------------------

def _overlay_closed():
    """True unless a tank-setup / ammo overlay is open. The vehicle-params sub-view we
    inject into stays mounted to show stat changes while those overlays are open, so the
    bar must be hidden then. A live loadout interactor is that 'overlay open' signal.
    Guarded -> True (fail open: show the bar) when the controller is unreadable."""
    try:
        from skeletons.gui.game_control import ILoadoutController
        return dependency.instance(ILoadoutController).interactor is None
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return True


def _in_garage():
    """True only when the plain garage view is the visible lobby state. The vehicle-
    params sub-view stays mounted on other lobby views (playlists, etc.), so the bar must
    be hidden there. The plain garage is the DefaultHangarState, whose id ends in
    'hangar/{root}' (verified in the sibling mod). Guarded -> False (FAIL CLOSED: show
    ONLY in the confirmed garage) when the state machine is missing/unreadable."""
    try:
        from gui.Scaleform.lobby_entry import getLobbyStateMachine
        machine = getLobbyStateMachine()
        if machine is None:
            return False
        state = machine.visibleState
        if state is None:
            return False
        state_id = state.getStateID() or ""
        return state_id.endswith("hangar/{root}")
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return False


def _carousel_geometry():
    """(rows, small): carousel row count (1 single / 2 double) and, for a double row,
    whether the small (shorter) tile size is active. Drives the widget's bottom offset so
    it clears the carousel. Guarded -> (1, False): a single-row default is the safest
    (smallest) clearance assumption."""
    try:
        from account_helpers.settings_core import settings_constants as sc
        core = dependency.instance(_settings_core_iface())
        rows = int(core.options.getSetting(sc.GAME.CAROUSEL_TYPE).getRowCount())
        small = bool(core.options.getSetting(sc.GAME.DOUBLE_CAROUSEL_TYPE).enableSmallCarousel())
        return rows, small
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return 1, False


def _settings_core_iface():
    from skeletons.account_helpers.settings_core import ISettingsCore
    return ISettingsCore


def _host_alive():
    """True while the lobby (the hangar document that hosts our widget) exists. False in
    battle, where the hangar space -- and the `_active` ViewModel with it -- has been torn
    down. `_active` is never cleared (there is no view-destroy hook wired), so a
    session-persistent listener (the MoE-table ready hook, an items-cache sync) can fire
    AFTER battle entry; gating refresh() on this turns a push into a dead VM (fail-soft but
    wasteful + log spam) into an early return. Guarded -> False (skip) when the state machine
    is unreadable, matching _in_garage's fail-closed stance (the bar would be hidden anyway)."""
    try:
        from gui.Scaleform.lobby_entry import getLobbyStateMachine
        return getLobbyStateMachine() is not None
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return False


# --- mount + push ------------------------------------------------------------

def attach(host_vm):
    """Load assets into the hangar doc + expose our data model on the sub-view.
    Returns the MoEVM instance to push into, or None on failure."""
    global _active
    try:
        openwg_gameface.gf_mod_inject(
            host_vm, WIDGET_NAME,
            styles=[COUI + "/MoECalculator.css"],
            modules=[COUI + "/MoECalculator.js"])
        rvm = MoEVM()
        host_vm._addViewModelProperty(DATA_PROP, rvm)
        _active = (host_vm, rvm)
        # Kick the one-time external-thresholds fetch (idempotent); the ready hook
        # (armed in install_all_listeners) re-pushes when it completes.
        moe_data.start()
        return rvm
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return None


def refresh():
    """Re-push the current vehicle's model into the mounted widget. No-op when no widget is
    mounted, or when the hangar host is gone (a background fetch / items-cache sync that
    completes mid-battle must not push into the torn-down `_active` VM)."""
    if _active is None:
        LOG_NOTE("[moe] refresh: no active widget")
        return False
    if not _host_alive():
        LOG_NOTE("[moe] refresh: hangar host gone -> skip (stale listener fired off-lobby)")
        return False
    push(_active[1], host_vm=_active[0])
    return True


def push(rvm, host_vm=None):
    """Recompute the MoE model for the selected vehicle and write it into rvm."""
    if rvm is None:
        return
    try:
        snap = engine_adapter.build_snapshot()
        model = build_model(snap)
        rows, small = _carousel_geometry()
        visible = bar_visible(_overlay_closed(), _in_garage(), snap.has_vehicle)
        LOG_NOTE("[moe] push visible=%s marks=%d pct=%.1f rows=%d data=%s" % (
            visible, model.marks, model.cur_percentile, rows, model.has_data))
        with rvm.transaction() as tx:
            tx.setVisible(visible)
            tx.setNation(model.nation)
            tx.setMarks(model.marks)
            tx.setCurPercent(model.cur_percentile)
            tx.setCurAvgDamage(model.cur_avg_damage)
            tx.setFill(model.fill)
            tx.setHasData(model.has_data)
            tx.setCarouselRows(rows)
            tx.setCarouselSmall(small)
            tx.setEndDamageRequired(model.end_damage_required)
            tx.setLabels(_labels_json())
            arr = tx.getTicks()
            arr.clear()
            for tk in model.ticks:
                tv = MarkTickVM()
                tv.setPercent(tk.percent)
                tv.setMarkCount(tk.mark_count)
                tv.setDamageRequired(tk.damage_required)
                tv.setReached(bool(tk.reached))
                # Compose the nation mark art here (asset knowledge lives in the adapter,
                # not the pure domain). "" -> the widget uses a generic glyph.
                tv.setIcon(fmt.mark_icon_url(model.nation, tk.mark_count))
                arr.addViewModel(tv)
            arr.invalidate()
        # Nudge the host sub-view so its data re-syncs to JS (nested-model updates may not
        # bubble a data-changed event on their own).
        if host_vm is not None:
            try:
                with host_vm.transaction() as _h:
                    pass
            except Exception:
                pass
    except Exception:
        LOG_CURRENT_EXCEPTION()
