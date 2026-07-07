# -*- coding: utf-8 -*-
"""Live probe: force-open the in-battle MoE overlay WINDOW and push a synthetic, visible
model -- to isolate RENDERING (does the registered Gameface window paint over the battle
HUD?) from the real data path.

Run inside a running battle (live or replay) via the debug REPL:
    py -3 tools/dev/repl_client.py "execfile(r'<abs path>/tools/dev/probe_battle_window.py')"

Expected: a two-row readout appears over the HUD (bottom-left by default) showing
~3,141 / 2,718 / 84.73% / +1.5%. If it shows, rendering + the window/layer/res_map are
good and only the CSS position needs calibration; if the layout id prints < 0, the res_map
layout isn't registered yet (needs the one-time client restart after deploying).
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
    print("[probe] pushed synthetic visible model -- overlay should paint now")
else:
    print("[probe] window did NOT open -- check layoutID above / python.log")
