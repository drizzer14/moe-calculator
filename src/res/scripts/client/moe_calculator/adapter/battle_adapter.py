# -*- coding: utf-8 -*-
"""PC-only engine adapter: read the LIVE BATTLE client into a BattleSnapshot.

Mirror of engine_adapter.py for the in-battle path. Every read is _safe-guarded so one
unreadable subsystem degrades to a hidden overlay rather than blanking or crashing.

All symbols below are VERIFIED against the on-disk decompile at ~/wot-eu (StranikS-Scan
branch 2.3; see the wotmod-debug-repl harness skill for the clone location):
  - IBattleSessionProvider.shared.{personalEfficiencyCtrl, vehicleState}  (battle_session.py)
  - PersonalEfficiencyController.getTotalEfficiency(eType) + onTotalEfficiencyUpdated event
    (gui/battle_control/controllers/personal_efficiency_ctrl.py)
  - PERSONAL_EFFICIENCY_TYPE.{DAMAGE=1, ASSIST_DAMAGE=2, STUN=32}  (battle_constants.py). The
    controller tracks these three separately, but ASSIST_DAMAGE merges spot+track (only the
    post-battle summary splits them) -- hence combined damage is an approximation.
  - vehicleState.getControllingVehicleID() (vehicle_state_ctrl.py) -> arena.vehicles[vid]
    ['vehicleType'].type.compactDescr = intCD (the standard arena vehicle-info shape).

Still confirm live (behaviour, not symbol names): ARENA_PERIOD gating and that a played
tank has thresholds. The dossier baseline (pre_avg / pre_percentile) and the tomato.gg
thresholds are the SAME reads the garage path uses -- we reuse engine_adapter._read_moe
and moe_data.
"""
import BigWorld

from moe_calculator._compat import LOG_CURRENT_EXCEPTION, LOG_NOTE, _safe, _safe_int
from moe_calculator.domain import battle_types as bt
from moe_calculator.adapter import engine_adapter
from moe_calculator.adapter import moe_data
from moe_calculator.adapter import baseline_cache


def _session_provider():
    from helpers import dependency
    from skeletons.gui.battle_session import IBattleSessionProvider
    return dependency.instance(IBattleSessionProvider)


def _efficiency_ctrl():
    """The personal-efficiency controller feeding the battle damage panel, or None."""
    sp = _session_provider()
    if sp is None or sp.shared is None:
        return None
    return sp.shared.personalEfficiencyCtrl


def _read_efficiency():
    """(damage, assist, stun) accumulated this battle so far. assist = spot+track MERGED
    live (only post-battle splits them). Fail-soft to (0, 0, 0)."""
    try:
        from gui.battle_control.battle_constants import PERSONAL_EFFICIENCY_TYPE as PE
        ctrl = _efficiency_ctrl()
        if ctrl is None:
            return 0, 0, 0
        damage = _safe_int(lambda: ctrl.getTotalEfficiency(PE.DAMAGE), 0)
        assist = _safe_int(lambda: ctrl.getTotalEfficiency(PE.ASSIST_DAMAGE), 0)
        stun = _safe_int(lambda: ctrl.getTotalEfficiency(PE.STUN), 0)
        return damage, assist, stun
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return 0, 0, 0


def _player_vehicle_descr():
    """The player's controlled arena vehicle descriptor (has .type.compactDescr = intCD),
    or None. Sourced from the observed/controlled vehicle so it also works while spectating
    in a replay."""
    try:
        sp = _session_provider()
        vsc = sp.shared.vehicleState if (sp and sp.shared) else None
        if vsc is None:
            return None
        vid = _safe(lambda: vsc.getControllingVehicleID(), 0)
        arena = BigWorld.player().arena
        if not vid or arena is None:
            return None
        vinfo = arena.vehicles.get(vid)
        if not vinfo:
            return None
        return vinfo.get("vehicleType")
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return None


def _player_vehicle_int_cd(descr):
    if descr is None:
        return 0
    return _safe_int(lambda: descr.type.compactDescr, 0)


def _player_nation(descr):
    if descr is None:
        return ""
    try:
        import nations
        nation_id = descr.type.id[0]
        return _safe(lambda: nations.NAMES[nation_id], "") or ""
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return ""


def _in_battle():
    """True during the active combat period. Fail-open (True) when unreadable: if we could
    read a vehicle + efficiency, showing the overlay is the safe default."""
    try:
        from constants import ARENA_PERIOD
        arena = BigWorld.player().arena
        if arena is None:
            return True
        return arena.period == ARENA_PERIOD.BATTLE
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return True


def build_battle_snapshot():
    """Read the live battle into a BattleSnapshot. Returns has_vehicle=False (never None)
    when the player vehicle is unreadable, so the bridge hides the overlay uniformly."""
    try:
        descr = _player_vehicle_descr()
        int_cd = _player_vehicle_int_cd(descr)
        if not int_cd:
            return bt.BattleSnapshot(has_vehicle=False, in_battle=_in_battle())

        damage, assist, stun = _read_efficiency()
        # Career baseline. The dossier engine_adapter._read_moe uses is a LOBBY resource --
        # getVehicleDossier returns None in battle, so this reads (0, 0.0) here. Fall back to
        # the baseline snapshotted while the tank was in the garage (see baseline_cache).
        _marks, pre_percentile, pre_avg = engine_adapter._read_moe(int_cd)
        if (pre_percentile or 0) <= 0 and (pre_avg or 0) <= 0:
            cached = baseline_cache.get(int_cd)
            if cached is not None:
                pre_percentile, pre_avg = cached
                LOG_NOTE("[moe-battle] baseline from garage cache: pct=%.2f avg=%d"
                         % (pre_percentile, pre_avg))
            else:
                LOG_NOTE("[moe-battle] no baseline (tank not seen in garage this session)")
        thresholds = moe_data.get_thresholds(int_cd)
        nation = _player_nation(descr)

        return bt.BattleSnapshot(
            vehicle_int_cd=int_cd,
            nation=nation,
            damage=damage,
            assist=assist,
            stun=stun,
            team_damage=0,          # no team-damage efficiency bucket live; documented caveat
            pre_avg_damage=pre_avg,
            pre_percentile=pre_percentile,
            thresholds=thresholds,
            has_vehicle=True,
            in_battle=_in_battle())
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return bt.BattleSnapshot(has_vehicle=False, in_battle=False)
