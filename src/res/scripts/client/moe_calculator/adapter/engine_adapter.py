# -*- coding: utf-8 -*-
"""PC-only engine adapter: read the live WoT client into a MoESnapshot.

This is the ONLY layer that touches live game symbols on the read side. Every read is
wrapped in a _safe guard so one unreadable subsystem degrades gracefully instead of
blanking the whole bar. Symbols verified against the EU 2.3 decompiled client:
- vehicle dossier TOTAL block: MarkOnGunAchievement.getValue()/getDamageRating() and
  the movingAvgDamage record (gui/shared/gui_items/dossier/achievements/mark_on_gun.py;
  read pattern from gui/impl/lobby/tooltips/carousel_vehicle_tooltip.py).
- the 65/85/95% damage thresholds come from adapter/moe_data (the official Wargaming API).
"""
from CurrentVehicle import g_currentVehicle

from moe_calculator._compat import LOG_CURRENT_EXCEPTION, _safe, _safe_int
from moe_calculator.domain import types as t
from moe_calculator.domain import moe_estimate
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
        thresholds = moe_data.get_thresholds(int_cd)
        # Fallback: if the WG request for this tank completed with no usable data (errored /
        # not in the API), extrapolate from the player's own dossier point (movingAvgDamage @
        # this percentile) via the offline estimator, so the bar still shows numbers rather
        # than blank labels. A still-pending fetch does NOT trigger this (needs_estimate is
        # False) -- we wait for it. The estimate is per-read, not cached into the WG table.
        if not thresholds and moe_data.needs_estimate(int_cd):
            thresholds = _estimate_thresholds(percentile, avg_damage)

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


def _estimate_thresholds(percentile, avg_damage):
    """Extrapolate {1,2,3,100: dmg} from the player's single dossier point (avg_damage at
    `percentile`) using the offline estimator's universal prior -- the WG-request-error
    fallback. Returns {} when the point is unusable (never-played / degenerate). Pure math,
    guarded."""
    try:
        p = float(percentile or 0.0)
        d = float(avg_damage or 0)
        if d <= 0.0 or p <= 0.0 or p >= 100.0:
            return {}
        return moe_estimate.thresholds_from_samples([(d, p / 100.0)])
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return {}


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
