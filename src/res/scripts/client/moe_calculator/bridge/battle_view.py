# -*- coding: utf-8 -*-
"""Host the in-battle MoE overlay as a standalone OpenWG-registered Gameface WINDOW
over the battle HUD.

Why a window and not the garage-style sub-view inject: the battle HUD has NO shared
full-screen Gameface document to inject a position:fixed overlay into -- each WG battle
Gameface view (DeathCam / Postmortem / BattleNotifier / Tab) is composited by Flash at
its own placeId, so `openwg_gameface.gf_mod_inject` (which appends assets to a sub-view's
host document) has nothing to attach to in battle. Instead we register our OWN Gameface
view (mods/configs/res_map/MoEBattleView.json -> the MoEBattleView.html bundle) and open
it as a full-screen, input-transparent top-layer window.

This mirrors WG's own gui.impl.battle.prebattle.PrebattleHintsWindow (a battle-context
Gameface window): WindowImpl + WindowFlags.WINDOW | WINDOW_FULLSCREEN + layer=OVERLAY.
We deliberately do NOT enter GUI control mode / register a key handler (which is what
PrebattleHints does to CAPTURE input) and we show(focus=False) -- so the overlay never
steals battle input or the cursor. The document is pointer-events:none as a second guard.

The window content view's OWN root ViewModel is our BattleMoEVM; the JS reads it with a
root ModelObserver() and battle_bridge pushes into `view.viewModel`.

    Symbols VERIFIED against the ~/wot-eu decompile (branch 2.3, in the wotmod-debug-repl
    skill) + the extracted me.poliroid.battlehits / net.openwg.gameface bundles:
    - openwg_gameface.ModDynAccessor(itemID) is a deferred DynAccessor; calling it returns
      the layoutID for our res_map itemID (INVALID_RES_ID == -1 until the res_map is
      validated at client start; resolved well before any battle).
    - ViewSettings(layoutID, ViewFlags.VIEW, model); ViewImpl.getViewModel() -> that model.
    - WindowImpl(wndFlags, content=<view>, layer=...); Window._onReady() default shows the
      window (focus=True) -- we override to focus=False.

NOTE: adding the res_map entry triggers a ONE-TIME client restart the first time OpenWG's
ResMapManager rebuilds res_map.json with our layout. PC-only (needs the live client); not
imported under pytest. Python 2.7 runtime.
"""
from moe_calculator._compat import LOG_CURRENT_EXCEPTION, LOG_NOTE

from frameworks.wulf import ViewSettings, ViewFlags, WindowFlags, WindowLayer
from gui.impl.pub import ViewImpl, WindowImpl
from openwg_gameface import ModDynAccessor

from moe_calculator.bridge.view_models import BattleMoEVM

# itemID registered in mods/configs/res_map/MoEBattleView.json -- keep in lockstep.
RES_MAP_ITEM_ID = "MoEBattleView"


class MoEBattleView(ViewImpl):
    """The registered Gameface view; its root ViewModel is our BattleMoEVM."""

    # Deferred resId accessor for our res_map-registered layout. Class-level so the
    # deferred res_map->resId resolution (openwg on_ready) happens once at import.
    _layoutID = ModDynAccessor(RES_MAP_ITEM_ID)

    def __init__(self):
        settings = ViewSettings(self._layoutID(), ViewFlags.VIEW, BattleMoEVM())
        super(MoEBattleView, self).__init__(settings)

    @property
    def viewModel(self):
        return super(MoEBattleView, self).getViewModel()

    def _onLoading(self, *args, **kwargs):
        super(MoEBattleView, self)._onLoading(*args, **kwargs)
        # Push the current model once the view (and its bound VM) is live, so the overlay
        # paints immediately instead of waiting for the next efficiency/arena event. Lazy
        # import avoids a battle_view <-> battle_bridge import cycle.
        try:
            from moe_calculator.bridge import battle_bridge
            battle_bridge.refresh()
        except Exception:
            LOG_CURRENT_EXCEPTION()


class MoEBattleWindow(WindowImpl):
    """Full-screen, input-transparent window hosting MoEBattleView over the HUD.

    Layer = WINDOW (7), deliberately BELOW the in-battle menu. The Esc/ingame menu
    (VIEW_ALIAS.INGAME_MENU, ingameMenu.swf) is registered at WindowLayer.TOP_WINDOW (10)
    with isModal=True. A full-screen window ABOVE a modal window becomes the keyboard
    sink and starves the menu of input -- which is exactly the bug we hit at OVERLAY (11):
    opening the menu in battle stole all input, including the keyboard. Sitting below the
    menu's layer lets its modality correctly gate input away from our (input-less, always
    pointer-events:none) overlay while we still render above the battle HUD views, which
    live in the battle MainView (below the WINDOW layer)."""

    def __init__(self, content):
        super(MoEBattleWindow, self).__init__(
            WindowFlags.WINDOW | WindowFlags.WINDOW_FULLSCREEN,
            content=content, layer=WindowLayer.WINDOW)

    def _onReady(self):
        # Show WITHOUT taking focus -- an info-only overlay must never grab battle input.
        self.show(focus=False)


# Singleton (window, view) for the currently-open overlay (None when closed).
_active = None


def open_window():
    """Idempotently open the overlay window. Returns its MoEBattleView (read
    `.viewModel` to push into), or None on failure / res_map not yet registered."""
    global _active
    if _active is not None:
        return _active[1]
    try:
        layout = MoEBattleView._layoutID()
        if layout is None or layout < 0:
            LOG_NOTE("[moe-battle] res_map layout '%s' unresolved -- a one-time client "
                     "restart is needed for OpenWG to register it." % RES_MAP_ITEM_ID)
            return None
        view = MoEBattleView()
        window = MoEBattleWindow(view)
        # Publish the singleton BEFORE load() so the view's _onLoading initial-push (which
        # calls back through battle_bridge.refresh() -> active_view()) sees us, regardless
        # of whether load() completes synchronously or on a later tick.
        _active = (window, view)
        window.load()
        LOG_NOTE("[moe-battle] overlay window opened (layoutID=%s, layer=OVERLAY)" % layout)
        return view
    except Exception:
        LOG_CURRENT_EXCEPTION()
        _active = None
        return None


def close_window():
    """Destroy the overlay window if open."""
    global _active
    if _active is None:
        return
    window = _active[0]
    _active = None
    try:
        window.destroy()
        LOG_NOTE("[moe-battle] overlay window destroyed")
    except Exception:
        LOG_CURRENT_EXCEPTION()


def active_view():
    """The currently-open MoEBattleView, or None."""
    return None if _active is None else _active[1]
