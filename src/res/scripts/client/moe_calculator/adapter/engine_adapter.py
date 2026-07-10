# -*- coding: utf-8 -*-
"""PC-only engine adapter: read the live WoT client into a MoESnapshot.

This is the ONLY layer that touches live game symbols on the read side. Every read is
wrapped in a _safe guard so one unreadable subsystem degrades gracefully instead of
blanking the whole bar. Symbols verified against the EU 2.3 decompiled client:
- vehicle dossier TOTAL block: MarkOnGunAchievement.getValue()/getDamageRating() and
  the movingAvgDamage record (gui/shared/gui_items/dossier/achievements/mark_on_gun.py;
  read pattern from gui/impl/lobby/tooltips/carousel_vehicle_tooltip.py).
- the 65/85/95% damage thresholds come from adapter/moe_data (the source router: tomato.gg
  table on the GitHub build, or an offline estimator fed by the (avg_damage, percentile)
  samples this adapter records on the WGMods build).
"""
from CurrentVehicle import g_currentVehicle

from moe_calculator._compat import LOG_CURRENT_EXCEPTION, _safe, _safe_int
from moe_calculator.domain import types as t
from moe_calculator.adapter import moe_data
from moe_calculator.adapter import baseline_cache


def build_snapshot():
    """Read the selected vehicle into a MoESnapshot. Returns a snapshot with
    has_vehicle=False (never None) when no vehicle is selected, so the bridge can hide
    the bar uniformly."""
    try:
        if not g_currentVehicle.isPresent():
            return t.MoESnapshot(has_vehicle=False)
        veh = g_currentVehicle.item

        int_cd = _safe_int(lambda: veh.intCD, 0)
        nation = _safe(lambda: veh.nationName, "") or ""
        marks, percentile, avg_damage = _read_moe(int_cd)
        # Snapshot the career baseline for the in-battle overlay -- the dossier this reads is
        # unavailable in battle, so battle_adapter falls back to this cache (see baseline_cache).
        baseline_cache.remember(int_cd, percentile, avg_damage)
        # Feed the offline threshold estimator one (avg_damage, percentile) sample -- this is
        # the ONLY place with a live dossier. No-op under the tomato source; guarded + deduped
        # inside record_sample, so redundant garage refreshes don't grow the store.
        moe_data.record_sample(int_cd, percentile, avg_damage)
        thresholds = moe_data.get_thresholds(int_cd)

        return t.MoESnapshot(
            vehicle_int_cd=int_cd,
            nation=nation,
            marks=marks,
            cur_percentile=percentile,
            cur_avg_damage=avg_damage,
            thresholds=thresholds,
            has_vehicle=True)
    except Exception:
        # Whole-body guard (matches battle_adapter.build_battle_snapshot): any unexpected
        # raise in the tail -- baseline_cache / get_thresholds / snapshot construction --
        # degrades to a hidden bar instead of propagating into the hangar mount.
        LOG_CURRENT_EXCEPTION()
        return t.MoESnapshot(has_vehicle=False)


def _read_moe(int_cd):
    """Read (marks 0-3, current percentile float, current moving-avg combined damage)
    from the vehicle's TOTAL dossier. Guarded/fail-soft to (0, 0.0, 0): a never-played
    vehicle simply has no records (getRecordValue would KeyError)."""
    try:
        from helpers import dependency
        from skeletons.gui.shared import IItemsCache
        from dossiers2.ui.achievements import MARK_ON_GUN_RECORD, ACHIEVEMENT_BLOCK
        items = dependency.instance(IItemsCache).items
        dossier = items.getVehicleDossier(int_cd)
        if dossier is None:
            return 0, 0.0, 0
        stats = dossier.getTotalStats()
        mog = stats.getAchievement(MARK_ON_GUN_RECORD)
        marks = _safe_int(lambda: mog.getValue(), 0)
        # getDamageRating() already divides the stored damageRating by 100 -> e.g. 84.7.
        percentile = float(_safe(lambda: mog.getDamageRating(), 0.0) or 0.0)
        avg_damage = _safe_int(
            lambda: dossier.getRecordValue(ACHIEVEMENT_BLOCK.TOTAL, "movingAvgDamage"), 0)
        return marks, percentile, avg_damage
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return 0, 0.0, 0
