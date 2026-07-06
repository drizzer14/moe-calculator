# -*- coding: utf-8 -*-
"""PC-only write-side: perform the research / unlock actions the user clicks.

Counterpart to engine_adapter.py, which only READS. Each public function resolves the
currently-selected vehicle and runs WG's own research/unlock flow; the game's
onSyncCompleted (wired in the bridge) then refreshes the bar. Everything is guarded so
a failure degrades to opening WG's native screen for that item -- never a raise back
into the JS bridge, never a silent spend. Symbols must be verified live in the client
(see the wotmod-debug-repl harness skill for probing them).
"""
from CurrentVehicle import g_currentVehicle

from moe_calculator._compat import LOG_CURRENT_EXCEPTION, LOG_NOTE


def research_unlock(int_cd):
    """Research/unlock the tech-tree item `int_cd` for the selected vehicle. Stub:
    wire this to WG's items-actions factory (UNLOCK_ITEM) against the decompiled
    client; falls back to opening the research screen on any failure."""
    veh = _current_vehicle()
    if veh is None:
        return
    try:
        LOG_NOTE("[moe_calculator] research_unlock intCD=%s" % int_cd)
        # TODO: build UnlockProps from veh.getUnlocksDescrs() and call
        #   gui.shared.gui_items.items_actions.factory.doAction(UNLOCK_ITEM, int_cd, props)
        _open_research_screen(veh)
    except Exception:
        LOG_CURRENT_EXCEPTION()
        _open_research_screen(veh)


def open_research():
    """Open WG's research (tech-tree) screen for the selected vehicle -- navigation
    only, never a re-research."""
    veh = _current_vehicle()
    if veh is None:
        return
    _open_research_screen(veh)


def _current_vehicle():
    try:
        if not g_currentVehicle.isPresent():
            return None
        return g_currentVehicle.item
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return None


def _open_research_screen(veh):
    """Open WG's research (tech-tree) screen for the vehicle."""
    try:
        from gui.shared.event_dispatcher import showResearchView
        showResearchView(veh.intCD)
    except Exception:
        LOG_CURRENT_EXCEPTION()
