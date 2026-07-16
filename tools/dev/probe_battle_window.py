# -*- coding: utf-8 -*-
"""Live probe: force-open the in-battle MoE overlay WINDOW and push a synthetic, visible
model -- to isolate RENDERING (does the registered Gameface window paint over the battle
HUD?) from the real data path.

Run inside a running battle (live or replay) via the debug REPL:
    py -3 tools/dev/repl_client.py "execfile(r'<abs path>/tools/dev/probe_battle_window.py')"

Expected: a THREE-row readout appears over the HUD (bottom-left by default) showing
~3,141 / 2,718  (row 1), 84.73% (+1.5%) (row 2), and 974 with the spotting icon (row 3).
All three rows are forced (hasBaseline + assist) so the row-2/3 backdrops render together --
this is the state to screenshot when verifying the backdrop alignment/height fix. If it shows,
rendering + the window/layer/res_map are good and only the CSS position needs calibration; if
the layout id prints < 0, the res_map layout isn't registered yet (needs the one-time client
restart after deploying).
"""
from moe_calculator.bridge import battle_view

layout = battle_view.MoEBattleView._layoutID()
print("[probe] MoEBattleView res_map layoutID =", layout, "(>=0 means registered)")

view = battle_view.open_window()
print("[probe] open_window ->", view)

if view is not None:
    rvm = view.viewModel
    with rvm.transaction() as tx:
        tx.setVisible(True)
        tx.setCombinedDamage(3141)
        tx.setProjAvgDamage(2718)
        tx.setCurPercent(84.73)
        tx.setPctDelta(1.5)
        tx.setHasData(True)
        tx.setHasBaseline(True)      # baseline present -> proj/percent/delta render (not dashed)
        # Force the optional counted-assistance row so ALL THREE rows (and their backdrops)
        # render at once -- the state to screenshot for the backdrop alignment/height check.
        tx.setAssistVisible(True)
        tx.setCountedAssist(974)
        tx.setAssistKind("spot")     # spotting -> radio-waves icon on row 3
    print("[probe] pushed synthetic 3-row model -- overlay should paint now (rows 1-3)")
else:
    print("[probe] window did NOT open -- check layoutID above / python.log")
