# REPL experiment -- does injecting onto OUR OWN child sub-view of the battle MainView
# make the overlay render? Run this while IN A BATTLE (live or replay).
#   execfile(r'C:\Users\Dmytro Vasylkivskyi\14th_ua-moe-calculator\tools\dev\probe_battle_subview.py')
#
# Hypothesis (source-confirmed via InjectComponentAdaptor + main_view.py): a View added as
# a child of windowsManager.getMainWindow().content (the battle MainView) becomes an entry
# in the battle Gameface document's window.subViews, so OpenWG index.js scans its
# ModInjectModel and injects MoEBattle.js/.css into the HUD document -> overlay renders.
# Uses R.aliases.common.none() -- the same inert layout our WORKING garage sub-view uses.
#
# Pushes a SYNTHETIC visible model so rendering is tested independently of the empty-in-
# replay dossier (BUG B). If the overlay appears -> approach confirmed; wire it into
# mod_moe_calculator._install_battle. If not -> fall back to piggyback / native window.
import traceback

_PLACE_ID = 0x4D6F45  # "MoE"

echo('=== MoE battle sub-view render experiment ===')
try:
    from helpers import dependency
    from skeletons.gui.impl import IGuiLoader
    from gui.impl.pub.view_component import ViewComponent
    from moe_calculator.bridge import battle_bridge as B

    gui = dependency.instance(IGuiLoader)
    mw = gui.windowsManager.getMainWindow()
    echo('mainWindow=%r' % (mw,))
    if mw is None:
        echo('NO MAIN WINDOW -- not in a battle/hangar? abort.')
    else:
        mainView = mw.content
        echo('mainView=%r flags=%r uid=%r' % (
            mainView, getattr(mainView, 'viewFlags', None), getattr(mainView, 'uniqueID', None)))

        # Idempotent re-run: drop a child from a previous experiment run.
        try:
            mainView.removeChild(_PLACE_ID, True)
            echo('(removed prior experiment child)')
        except Exception:
            pass

        child = ViewComponent()  # layoutID = R.aliases.common.none(); ViewFlags.VIEW
        # ORDER MATTERS: inject ModInjectModel onto the VM BEFORE the view loads/registers,
        # else OpenWG's subViews.onAdded fires with no ModInjectModel and never re-scans.
        rvm = B.attach(child.getViewModel())
        echo('attach rvm=%r' % (rvm,))
        echo('host VM (pre-add) with ModInjectModel = %r' % (child.getViewModel(),))
        # Add as a child of the battle MainView with loadImmediately=False, then load, so
        # ModInjectModel is already present when the subView is registered to JS.
        mainView.addChild(_PLACE_ID, child, False)
        try:
            child.load()
        except Exception:
            echo('child.load() raised:\n' + traceback.format_exc())
        echo('child added+loaded: %r uid=%r' % (child, child.uniqueID))

        # SYNTHETIC visible model -> forces the widget to render regardless of dossier data.
        with rvm.transaction() as tx:
            tx.setVisible(True)
            tx.setCombinedDamage(1234)
            tx.setProjAvgDamage(1500)
            tx.setCurPercent(84.73)
            tx.setPctDelta(1.2)
            tx.setHasData(True)
        # Nudge the host so the nested-model change re-syncs to JS.
        try:
            with child.getViewModel().transaction() as _h:
                pass
        except Exception:
            pass
        echo('pushed SYNTHETIC visible model -> LOOK AT SCREEN (bottom-left) for the MoE overlay.')
        echo('expect: "MoE dmg 1,234 / avg 1,500" and "MoE % 84.73% / d +1.2%"')
except Exception:
    echo(traceback.format_exc())
