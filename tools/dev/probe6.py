# REPL discovery #6 -- verify the live in-battle mount + the pushed model.
# execfile(r'C:\Users\Dmytro Vasylkivskyi\14th_ua-moe-calculator\tools\dev\probe6.py')
import traceback
echo('--- mount ---')
try:
    from gui.impl.pub.main_view import MainView
    echo('MainView._moe_battle_patched=%r' % (getattr(MainView, '_moe_battle_patched', False),))
except Exception:
    echo(traceback.format_exc())
try:
    from moe_calculator.bridge import battle_bridge as B
    echo('battle_bridge._active=%r' % (B._active,))
except Exception:
    echo(traceback.format_exc())

echo('--- live snapshot + model (our adapter/domain) ---')
try:
    from moe_calculator.adapter import battle_adapter as A
    from moe_calculator.adapter import moe_data
    from moe_calculator.domain.battle_builder import build_battle_model
    snap = A.build_battle_snapshot()
    echo('SNAP has_vehicle=%r in_battle=%r intCD=%r nation=%r' % (
        snap.has_vehicle, snap.in_battle, snap.vehicle_int_cd, snap.nation))
    echo('SNAP dmg=%r assist=%r stun=%r team=%r preAvg=%r prePct=%r' % (
        snap.damage, snap.assist, snap.stun, snap.team_damage, snap.pre_avg_damage, snap.pre_percentile))
    echo('SNAP thresholds=%r loaded=%r' % (snap.thresholds, moe_data.is_loaded()))
    m = build_battle_model(snap)
    echo('MODEL cd=%r proj=%r pct=%r delta=%r hasData=%r' % (
        m.combined_damage, m.proj_avg_damage, m.cur_percent, m.pct_delta, m.has_data))
except Exception:
    echo(traceback.format_exc())
