# -*- coding: utf-8 -*-
"""Bridge: attach our Gameface widget to a hangar sub-view and push the model.

OpenWG's JS injector scans hangar SUB-views for a `ModInjectModel` and loads the
listed assets into the hangar document. So we inject onto a sub-view's ViewModel
(HangarVehicleParamsPresenter) and also hang our own data model on it (property
`moe_calculatorModel`), which the widget JS reads via ModelObserver("MoECalculator").

This is the seam between the engine and the pure domain: it READS via the adapter,
builds the model via the domain, and MARSHALS it into Wulf ViewModels. ViewModel API
(string/number/array, transaction, addViewModel, _addViewModelProperty) must be
verified live. See the wotmod-architecture harness skill for the listener re-arm
rationale and the Wulf MAP-arg gotcha.
"""
import BigWorld
from CurrentVehicle import g_currentVehicle
from helpers import dependency
from skeletons.gui.shared import IItemsCache

from moe_calculator._compat import LOG_CURRENT_EXCEPTION, LOG_NOTE
from moe_calculator.adapter import engine_adapter
from moe_calculator.adapter import actions
from moe_calculator.domain.builder import build_model, bar_visible
from moe_calculator.domain.types import Mode
from moe_calculator.bridge.view_models import ResearchVM, TickVM
from moe_calculator.bridge.wulf_args import cmd_int_arg as _cmd_int_arg
import openwg_gameface

WIDGET_NAME = "MoECalculator"
DATA_PROP = "moe_calculatorModel"
COUI = "coui://gui/gameface/mods/14th_ua/MoECalculator"

# (host_vm, rvm) for the currently-mounted widget. Importable so the entry point and
# the dev REPL can drive refreshes without poking module-private state.
_active = None

# Set while a coalesced refresh is already queued for the next tick, so a burst of
# onSyncCompleted fires collapses to a single deferred refresh().
_refresh_pending = False


# --- engine event subscriptions -------------------------------------------------
# WoT's Events store STRONG refs to their delegates, but the battle entry/exit
# teardown rebuilds the hangar space -- repopulating the event lists with WG's own
# presenters while dropping ours. So subscribing once is not enough:
# install_all_listeners() re-arms on every hangar mount, membership-checked (not a
# 'did we subscribe' flag). Handlers are module-level functions, so their identity is
# stable across re-arms. We subscribe via getattr/+=/setattr (i.e. `holder.attr +=
# handler`), NOT `event += handler` on a local: WoT's Event augmented-add does not
# reliably mutate the shared object in place, so the result MUST be stored back onto
# the attribute or the subscription is silently lost (the bar then never updates).

def _on_vehicle_changed(*args, **kwargs):
    try:
        refresh()
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _on_sync_completed(*args, **kwargs):
    # IItemsCache.onSyncCompleted(updateReason, invalidItems). Coalesce onto the next
    # tick so a burst collapses to one push and CurrentVehicle has rebuilt its item.
    try:
        _schedule_refresh()
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _vehicle_holder():
    return g_currentVehicle


def _stats_holder():
    return dependency.instance(IItemsCache)


# (label, holder-getter, event-attribute, handler) -- what the bar listens to.
#   vehicle : vehicle-selection changes
#   stats   : items-cache syncs (free-XP convert, research buys, XP)
_LISTENERS = (
    ("vehicle", _vehicle_holder, "onChanged", _on_vehicle_changed),
    ("stats", _stats_holder, "onSyncCompleted", _on_sync_completed),
)


def _arm(label, get_holder, attr, handler):
    """Subscribe `handler` to holder.<attr> iff not already present, storing the
    augmented Event back onto the attribute. Self-healing + idempotent; guarded so a
    not-yet-ready holder just skips (retried next mount)."""
    try:
        holder = get_holder()
        if holder is None:
            return
        event = getattr(holder, attr)
        if event is not None and handler not in event:
            event += handler
            setattr(holder, attr, event)
            LOG_NOTE("[moe_calculator] %s listener (re)armed" % label)
    except Exception:
        LOG_CURRENT_EXCEPTION()


def install_all_listeners():
    """(Re)arm every engine listener. Safe to call on every hangar mount -- the battle
    exit teardown drops the hangar-scoped delegates and this restores them."""
    for entry in _LISTENERS:
        _arm(*entry)


def _schedule_refresh():
    """Coalesce a refresh onto the next tick. BigWorld.callback runs on the main
    thread, so the push transaction is safe -- never use a timer thread here."""
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


# --- Reverse channel: handlers for JS click commands -------------------------

def _on_research_unlock(*args):
    try:
        int_cd = _cmd_int_arg(args)
        LOG_NOTE("[moe_calculator] researchUnlock intCD=%s" % int_cd)
        if int_cd:
            actions.research_unlock(int_cd)
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _on_open_research(*args):
    try:
        actions.open_research()
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _connect_commands(rvm):
    """Wire the reverse-channel commands to their handlers. The command objects are
    Wulf events that support +=. A fresh ResearchVM is created per attach(), so
    there's no double-subscription to guard against."""
    try:
        rvm.researchUnlock += _on_research_unlock
        rvm.openResearch += _on_open_research
    except Exception:
        LOG_CURRENT_EXCEPTION()


# --- garage-visibility signals (engine reads) --------------------------------

def _bar_visible():
    """Overlay-closed signal: True unless a tank-setup / ammo overlay is open. Stub
    -> True (fail open). Wire to ILoadoutController.interactor as your mod grows."""
    return True


def _in_garage():
    """True only when the plain garage view is the visible lobby state. Stub -> True.
    Wire to the lobby state machine's visible leaf id as your mod grows (fail CLOSED
    once wired: a positive garage confirmation should be required)."""
    return True


# --- mount + push ------------------------------------------------------------

def attach(host_vm):
    """Load assets into the hangar doc + expose our data model on the sub-view.
    Returns the ResearchVM instance to push into, or None on failure."""
    global _active
    try:
        openwg_gameface.gf_mod_inject(
            host_vm, WIDGET_NAME,
            styles=[COUI + "/MoECalculator.css"],
            modules=[COUI + "/MoECalculator.js"])
        rvm = ResearchVM()
        _connect_commands(rvm)
        host_vm._addViewModelProperty(DATA_PROP, rvm)
        _active = (host_vm, rvm)
        return rvm
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return None


def refresh():
    """Re-push the current vehicle's model into the mounted widget."""
    if _active is None:
        LOG_NOTE("[moe_calculator] refresh: no active widget")
        return False
    push(_active[1], host_vm=_active[0])
    return True


def push(rvm, host_vm=None):
    """Recompute the model for the selected vehicle and write it into rvm."""
    if rvm is None:
        return
    try:
        snap = engine_adapter.build_snapshot()
        if snap is None:
            return
        model = build_model(snap)  # pass mod_settings.enabled_modes() once you add toggles
        LOG_NOTE("[moe_calculator] push mode=%s ticks=%d" % (model.mode, len(model.ticks)))
        with rvm.transaction() as tx:
            # hide_always / hide_when_complete default False here; wire them to your
            # settings (e.g. ModsSettingsAPI) as your mod grows.
            tx.setVisible(bar_visible(_bar_visible(), False, False, model.mode, _in_garage()))
            tx.setMode(model.mode)
            tx.setScaleMin(model.scale_min)
            tx.setScaleMax(model.scale_max)
            tx.setFillVehicle(model.fill_vehicle)
            tx.setFillFree(model.fill_free)
            tx.setSpendableXp(model.spendable_xp or 0)
            arr = tx.getTicks()
            arr.clear()
            for t in model.ticks:
                tv = TickVM()
                tv.setPosition(t.xp_position)
                tv.setXpRequired(t.xp_required)
                tv.setCategory(t.category)
                tv.setName(t.name or "")
                tv.setAffordable(bool(t.affordable))
                tv.setActionId(t.action_id or 0)
                arr.addViewModel(tv)
            arr.invalidate()
        # Nudge the host sub-view so its data re-syncs to JS (nested-model updates may
        # not bubble a data-changed event on their own).
        if host_vm is not None:
            try:
                with host_vm.transaction() as _h:
                    pass
            except Exception:
                pass
    except Exception:
        LOG_CURRENT_EXCEPTION()


# Referenced so the Mode import isn't flagged unused; also documents that the widget
# never sees Mode.HIDDEN (the bar isn't pushed visible for it).
_HIDDEN = Mode.HIDDEN
