# REPL: inject the LOUD probe script onto our own battle child sub-view.
#   execfile(r'C:\Users\Dmytro Vasylkivskyi\14th_ua-moe-calculator\tools\dev\probe_inject_test.py')
# Answers: does OpenWG index.js inject into the battle MainView document, and is it visible?
import traceback
_PLACE_ID = 0x50524F42  # "PROB"
_COUI = "coui://gui/gameface/mods/14th_ua/MoECalculator/probe_inject.js"
echo('=== MoE inject PROBE (loud) ===')
try:
    from helpers import dependency
    from skeletons.gui.impl import IGuiLoader
    from gui.impl.pub.view_component import ViewComponent
    import openwg_gameface

    gui = dependency.instance(IGuiLoader)
    mw = gui.windowsManager.getMainWindow()
    mainView = mw.content
    echo('mainView=%r' % (mainView,))
    try:
        mainView.removeChild(_PLACE_ID, True)
        echo('(removed prior probe child)')
    except Exception:
        pass

    child = ViewComponent()
    # Inject BEFORE load so ModInjectModel is present when subViews.onAdded fires.
    openwg_gameface.gf_mod_inject(child.getViewModel(), 'MoEProbe', modules=[_COUI])
    echo('host VM = %r' % (child.getViewModel(),))
    mainView.addChild(_PLACE_ID, child, False)
    try:
        child.load()
    except Exception:
        echo('child.load() raised:\n' + traceback.format_exc())
    echo('probe child added+loaded uid=%r -> WATCH SCREEN for a big RED box + check python.log for MOE_PROBE' % (child.uniqueID,))
except Exception:
    echo(traceback.format_exc())
