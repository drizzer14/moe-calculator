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
tank has thresholds. The dossier baseline (pre_avg / pre_percentile) and the MoE thresholds
are the SAME reads the garage path uses -- we reuse engine_adapter._read_moe and the moe_data
facade (the official Wargaming API). Battle reads only the thresholds the garage path already
cached (the dossier / garage roster is unreadable here).
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


def _settings_core():
    """The ISettingsCore instance, or None. Its .interfaceScale exposes get() (the float
    multiplier) and onScaleChanged (an Event) -- used to re-place the overlay on scale
    changes. Fail-soft: a missing core just means no live re-placement."""
    try:
        from helpers import dependency
        from skeletons.account_helpers.settings_core import ISettingsCore
        return dependency.instance(ISettingsCore)
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return None


def read_damage_log_summary_flags():
    """The four "Summarized damage" DAMAGE_LOG flags as a (total, blocked, assist, stun)
    tuple of bools. Feeds domain.positioning.damage_log_summary_hidden to pick the overlay
    anchor. Fail-soft: an unreadable core OR an unreadable individual flag defaults that flag
    to TRUE (ticked) so the predicate lands on the DEFAULT (un-raised) anchor -- we never
    raise the panel on a bad read."""
    try:
        from account_helpers.settings_core.settings_constants import DAMAGE_LOG
        core = _settings_core()
        if core is None:
            return True, True, True, True
        get = lambda name: bool(_safe(lambda: core.getSetting(name), True))
        return (get(DAMAGE_LOG.TOTAL_DAMAGE), get(DAMAGE_LOG.BLOCKED_DAMAGE),
                get(DAMAGE_LOG.ASSIST_DAMAGE), get(DAMAGE_LOG.ASSIST_STUN))
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return True, True, True, True


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


def read_efficiency_totals():
    """The four "Summarized damage" totals as (damage, blocked, assist, stun) ints, ALIGNED to
    read_damage_log_summary_flags()' order. Feeds domain.positioning.efficiency_panel_wide to
    decide the 5-digit right-shift. Unlike _read_efficiency (which reads only the three totals
    that feed the combined-damage math), this also reads BLOCKED_DAMAGE, since WG's panel draws
    a blocked row too. Fail-soft to 0 per value (a bad read -> 0 -> below threshold -> no shift)."""
    try:
        from gui.battle_control.battle_constants import PERSONAL_EFFICIENCY_TYPE as PE
        ctrl = _efficiency_ctrl()
        if ctrl is None:
            return 0, 0, 0, 0
        damage = _safe_int(lambda: ctrl.getTotalEfficiency(PE.DAMAGE), 0)
        blocked = _safe_int(lambda: ctrl.getTotalEfficiency(PE.BLOCKED_DAMAGE), 0)
        assist = _safe_int(lambda: ctrl.getTotalEfficiency(PE.ASSIST_DAMAGE), 0)
        stun = _safe_int(lambda: ctrl.getTotalEfficiency(PE.STUN), 0)
        return damage, blocked, assist, stun
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return 0, 0, 0, 0


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


def _is_spectating():
    """True when a DIFFERENT vehicle than the player's OWN is being observed -- i.e. the
    local player has died and is spectating a teammate (postmortem free-look).

    This is the exact test WG itself uses (hit_direction_ctrl/ctrl.py):
      arenaDP.getPlayerVehicleID() != vehicleState.getControllingVehicleID()
    NOT Avatar.isObserver() -- that's true only for the dedicated observer/spectator ROLE
    (training rooms), not normal postmortem spectating.

    Fail-soft to False (overlay stays visible) when either id is unreadable, and the
    bool()/bool() guard makes a transient 0 mid-switch fail-safe rather than wrongly hiding."""
    try:
        from gui.battle_control import avatar_getter
        own = _safe_int(lambda: avatar_getter.getPlayerVehicleID(), 0)
        sp = _session_provider()
        vsc = sp.shared.vehicleState if (sp and sp.shared) else None
        observed = _safe_int(lambda: vsc.getControllingVehicleID(), 0) if vsc else 0
        return bool(own) and bool(observed) and own != observed
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return False


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
    """True whenever the overlay should be up: from arena spin-up through the post-battle
    aftermath -- WAITING / PREBATTLE (the prestart countdown) / BATTLE / AFTERBATTLE -- so
    the readout shows from the START of the battle and STAYS up once the result is decided
    (the last stats freeze), disappearing only when the player leaves the arena. Excludes
    only IDLE. Teardown is driven separately by onAvatarBecomeNonPlayer (battle exit), NOT
    by the result being decided.
    ARENA_PERIOD is an ordered enum (IDLE=0, WAITING=1, PREBATTLE=2, BATTLE=3, AFTERBATTLE=4).
    Fail-open (True) when unreadable: if we could read a vehicle + efficiency, showing the
    overlay is the safe default."""
    try:
        from constants import ARENA_PERIOD
        arena = BigWorld.player().arena
        if arena is None:
            return True
        return arena.period in (ARENA_PERIOD.WAITING, ARENA_PERIOD.PREBATTLE,
                                ARENA_PERIOD.BATTLE, ARENA_PERIOD.AFTERBATTLE)
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
        # A real >0 in-battle read (rare) trusts itself; otherwise the baseline is trusted iff
        # the garage read this tank this session -- including a genuine 0-career freshly-bought
        # tank (baseline_cache.seen), which the >0 value cache alone can't record. Only a tank
        # never opened in the garage (replay / relogin) stays untrusted -> BUG B dashes it.
        baseline_known = ((pre_percentile or 0) > 0 or (pre_avg or 0) > 0
                          or baseline_cache.seen(int_cd))
        if (pre_percentile or 0) <= 0 and (pre_avg or 0) <= 0:
            cached = baseline_cache.get(int_cd)
            if cached is not None:
                pre_percentile, pre_avg = cached
                LOG_NOTE("[moe-battle] baseline from garage cache: pct=%.2f avg=%d"
                         % (pre_percentile, pre_avg))
            elif baseline_known:
                LOG_NOTE("[moe-battle] genuine 0 baseline (tank seen in garage, 0 career)")
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
            in_battle=_in_battle(),
            is_spectating=_is_spectating(),
            baseline_known=baseline_known)
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return bt.BattleSnapshot(has_vehicle=False, in_battle=False)
