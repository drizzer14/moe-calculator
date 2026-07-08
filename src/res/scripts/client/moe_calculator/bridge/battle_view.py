# -*- coding: utf-8 -*-
"""Host the in-battle MoE overlay as a standalone OpenWG-registered Gameface WINDOW
over the battle HUD.

Why a window and not the garage-style sub-view inject: the battle HUD has NO shared
full-screen Gameface document to inject a position:fixed overlay into -- each WG battle
Gameface view (DeathCam / Postmortem / BattleNotifier / Tab) is composited by Flash at
its own placeId, so `openwg_gameface.gf_mod_inject` (which appends assets to a sub-view's
host document) has nothing to attach to in battle. Instead we register our OWN Gameface
view (mods/configs/res_map/MoEBattleView.json -> the MoEBattleView.html bundle) and open
it as a content-sized, input-transparent top-layer window (content-sized -- NOT full-screen
-- so it never captures the mouse hit-test outside the small readout corner; see
MoEBattleWindow for the Ctrl+click/hover-steal reasoning).

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

from frameworks.wulf import ViewSettings, ViewFlags, WindowFlags, WindowLayer, PositionAnchor
from gui.impl.pub import ViewImpl, WindowImpl
from openwg_gameface import ModDynAccessor

from moe_calculator.bridge.view_models import BattleMoEVM
from moe_calculator.domain.constants import BATTLE_ANCHOR_X, BATTLE_ANCHOR_Y
from moe_calculator.domain.positioning import anchor_top_left

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


# The window is placed at a FIXED logical-GUI-space offset from the screen's bottom-left edge
# (domain.constants.BATTLE_ANCHOR_X/Y), which tracks WG's (logical-unit) efficiency panel at
# every interface scale -- see domain/positioning.py for WHY a fixed offset beats the old
# `_ANCHOR_VW/_VH` fraction (the fraction was correct only at the 2x it was tuned at and
# drifted at 1x). We always move() with a TOP-LEFT anchor: the surface is a fixed ~256x256
# (windowSize is read-only -- confirmed live -- so it does NOT shrink to the CSS box), and a
# BOTTOM anchor clamps to the top when the offset is smaller than the window height.

# A large sentinel offset used to clamp the window to the far corner (LEFT/TOP anchor) so we
# can read back the movable extent (= logical space - windowSize) and place proportionally.
# Any value beyond the space works; the engine clamps it to (space - windowSize).
_FAR = 1 << 20


class MoEBattleWindow(WindowImpl):
    """Content-sized, input-transparent window hosting MoEBattleView over the HUD.

    NOT full-screen (was, until the Ctrl+click/hover steal fix). A full-screen Coherent
    WINDOW stacked over the Scaleform HUD captures the mouse hit-test across the WHOLE
    screen whenever the cursor is raised (Ctrl) -- `pointer-events:none` only stops our own
    DOM from being an event target, it does NOT make the window RECTANGLE transparent to the
    engine's cross-surface hit-test. Dropping WINDOW_FULLSCREEN makes the surface size to the
    content (the small readout box in MoEBattle.css), so only that bottom-left corner covers
    the screen -- the minimap (bottom-right), target markers, and radial menu stay
    click-through. WG precedent for a decoratorless, content-sized, movable WINDOW:
    gui/impl/lobby/offers/offer_banner_window.py (WindowFlags.WINDOW + load() + center()).

    Layer = WINDOW (7), deliberately BELOW the in-battle menu. The Esc/ingame menu
    (VIEW_ALIAS.INGAME_MENU, ingameMenu.swf) is registered at WindowLayer.TOP_WINDOW (10)
    with isModal=True. A window ABOVE a modal window becomes the keyboard sink and starves
    the menu of input -- the bug we hit at OVERLAY (11). Sitting below the menu's layer lets
    its modality correctly gate input away from our (input-less, pointer-events:none) overlay
    while we still render above the battle HUD views (battle MainView, below WINDOW)."""

    def __init__(self, content):
        super(MoEBattleWindow, self).__init__(
            WindowFlags.WINDOW, content=content, layer=WindowLayer.WINDOW)

    def _onReady(self):
        # Show WITHOUT taking focus -- an info-only overlay must never grab battle input.
        self.show(focus=False)
        _place(self)


def _place(window):
    """Position the window's TOP-LEFT at the fixed logical anchor over WG's efficiency panel.
    move() operates in a LOGICAL GUI space (physical px / interfaceScale) and the surface is a
    fixed size, so we can't just multiply physical screenSize(). Instead self-calibrate: clamp
    to the far corner to read the movable extent (= space - windowSize), then place at the
    fixed logical offset (domain.anchor_top_left) -- resolution- and interface-scale-invariant.
    move() needs the window attached to its area, which load() does before _onReady fires.
    Fail-soft: a positioning error must never blank the overlay."""
    try:
        window.move(_FAR, _FAR, xAnchor=PositionAnchor.LEFT, yAnchor=PositionAnchor.TOP)
        max_x, max_y = window.position
        x, y = anchor_top_left(max_x, max_y, BATTLE_ANCHOR_X, BATTLE_ANCHOR_Y)
        window.move(x, y, xAnchor=PositionAnchor.LEFT, yAnchor=PositionAnchor.TOP)
    except Exception:
        LOG_CURRENT_EXCEPTION()


def apply_position():
    """Re-place the currently-open overlay window at its logical anchor. Called on interface-
    scale change (battle_bridge) so the overlay keeps tracking WG's panel mid-battle. No-op
    (fail-soft) when the window is closed."""
    if _active is None:
        return
    _place(_active[0])


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
        LOG_NOTE("[moe-battle] overlay window opened (layoutID=%s, layer=WINDOW, content-sized)"
                 % layout)
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
