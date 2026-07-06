# -*- coding: utf-8 -*-
"""PC-only engine adapter: read the live WoT client into a VehicleSnapshot.

This is the ONLY layer that touches live game symbols on the read side. Every read is
wrapped in a _safe guard so one unreadable subsystem degrades gracefully (a safe
default) instead of blanking the whole bar. As your mod grows, split the per-subsystem
reads into their own reader modules and compose them here (see the wotmod-architecture
harness skill). Symbols must be verified against the decompiled client.
"""
from CurrentVehicle import g_currentVehicle

from moe_calculator._compat import LOG_CURRENT_EXCEPTION, _safe, _safe_int
from moe_calculator.domain import types as t
from moe_calculator.domain.constants import Category


def build_snapshot():
    """Read the selected vehicle into a VehicleSnapshot, or None if unavailable."""
    if not g_currentVehicle.isPresent():
        return None
    try:
        veh = g_currentVehicle.item
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return None

    return t.VehicleSnapshot(
        tier=_safe_int(lambda: veh.level, 0),
        is_elite=_safe(lambda: bool(veh.isElite), False),
        vehicle_xp=_safe_int(lambda: veh.xp, 0),
        free_xp=_free_xp(),
        tech_unlocks=_read_tech_unlocks(veh),
        vehicle_class=_safe(lambda: veh.type, "") or "",
        vehicle_int_cd=_safe_int(lambda: veh.intCD, 0))


def _free_xp():
    """Global free XP from the items cache, guarded to 0 when unreadable."""
    try:
        from helpers import dependency
        from skeletons.gui.shared import IItemsCache
        stats = dependency.instance(IItemsCache).items.stats
        return _safe_int(lambda: stats.freeXP, 0)
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return 0


def _read_tech_unlocks(veh):
    """The vehicle's tech-tree unlock rows -> [UnlockItem]. A minimal stub: fill in
    the real read against the decompiled client (veh.getUnlocksDescrs() and the
    items cache). Guarded -> [] so a read failure leaves the bar empty, not broken."""
    try:
        items = []
        # TODO: iterate veh.getUnlocksDescrs() (unlockIdx, xpCost, itemCD, required)
        # and classify each itemCD as Category.VEHICLE or Category.MODULE.
        _ = Category  # kept referenced until the real read is wired in
        return items
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return []
