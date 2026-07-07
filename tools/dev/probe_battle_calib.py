# -*- coding: utf-8 -*-
"""Live CSS/JS-calibration harness for the in-battle MoE overlay.

Forces the overlay WINDOW's Gameface document to RELOAD from disk (re-fetching the
edited MoEBattle.html/js/css in res_mods) via the Wulf Window.reload() proxy call, then
re-pins a FIXED synthetic visible model so the readout stays put with known numbers
while we tune position/size/layout.

Why reload() and not close()+open(): recreating the view reuses the framework's cached
page template (reopening shows the STALE document). Window.reload() -> proxy.reload()
re-fetches the document from disk in place, busting the cache, without a client relaunch.
The Python-side ViewModel (BattleMoEVM) stays bound across the reload, so re-pinning the
synthetic values right after makes them render as soon as the JS re-subscribes.

    py -3 tools/dev/repl_client.py "execfile(r'<abs>/tools/dev/probe_battle_calib.py')"

Synthetic values: 3,141 dmg / 2,718 avg / 84.73% / +1.5% delta.
Pause the replay first so live efficiency pushes don't overwrite the synthetic model.
"""
from moe_calculator.bridge import battle_view as bv

# Ensure the window is open (opens it if not); reload the live one for a fresh doc load.
view = bv.open_window()
if view is not None and bv._active is not None:
    window = bv._active[0]
    try:
        window.reload()
        echo("calib: window.reload() called -- document re-fetched from disk")
    except Exception as e:
        echo("calib: reload() failed (%r) -- falling back to close+open" % (e,))
        bv.close_window()
        view = bv.open_window()

if view is not None:
    rvm = view.viewModel
    with rvm.transaction() as tx:
        tx.setVisible(True)
        tx.setCombinedDamage(3141)
        tx.setProjAvgDamage(2718)
        tx.setCurPercent(84.73)
        tx.setPctDelta(1.5)
        tx.setHasData(True)
    echo("calib: pinned synthetic model (layoutID=%s)" % bv.MoEBattleView._layoutID())
else:
    echo("calib: window unavailable -- check python.log")
