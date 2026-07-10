# -*- coding: utf-8 -*-
"""Read the player's garage roster for the WG-API threshold provider.

`moe_wgapi` fetches thresholds for the *selected* vehicle first, then warms the cache for the
100 most-recently-played owned vehicles. This module supplies both reads:
  - selected_int_cd()      : the currently-selected vehicle's intCD (== WG tank_id).
  - recent_int_cds(limit)  : owned intCDs, most-recently-played first, capped at `limit`.

The recency key is the vehicle dossier's TOTAL last-battle timestamp
(getGlobalStats().getLastBattleTime(), epoch seconds, 0 if never played) -- a purely local
read from the already-synced items cache, no per-vehicle network round-trip. The engine
symbols are imported lazily and every read is fail-soft (None / []), so an unsynced cache (e.g.
in a replay, where getVehicles() returns 0) degrades to "no roster" instead of raising.

rank_by_recency() is pure (no engine imports) and unit-tested; the engine reads are exercised
in-client.
"""
from moe_calculator._compat import LOG_CURRENT_EXCEPTION, _safe_int


def rank_by_recency(int_cds, recency_map, limit=100):
    """Return `int_cds` ordered most-recently-played first, capped at `limit`.

    recency_map maps intCD -> last-battle epoch seconds (missing -> 0 == never played, sorts
    last). Ties (equal recency, e.g. two never-played tanks) break by intCD ascending so the
    order is deterministic across sessions. Pure."""
    ordered = sorted(int_cds, key=lambda cd: (-recency_map.get(cd, 0), cd))
    return ordered[:limit]


def selected_int_cd():
    """The currently-selected vehicle's intCD, or None when nothing is selected / not ready."""
    try:
        from CurrentVehicle import g_currentVehicle
        if not g_currentVehicle.isPresent():
            return None
        cd = _safe_int(lambda: g_currentVehicle.item.intCD, 0)
        return cd or None
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return None


def recent_int_cds(limit=100):
    """Owned (in-inventory) intCDs, most-recently-played first, capped at `limit`.

    Returns [] when the items cache isn't synced yet (getVehicles() -> empty) or on any read
    failure -- the caller retries on the next garage refresh / onSyncCompleted."""
    try:
        from helpers import dependency
        from skeletons.gui.shared import IItemsCache
        from gui.shared.utils.requesters import REQ_CRITERIA
        items = dependency.instance(IItemsCache).items
        vehicles = items.getVehicles(REQ_CRITERIA.INVENTORY)  # {intCD: Vehicle}
        int_cds = list(vehicles.keys())
        if not int_cds:
            return []
        recency = {}
        for cd in int_cds:
            recency[cd] = _safe_int(
                lambda: items.getVehicleDossier(cd).getGlobalStats().getLastBattleTime(), 0)
        return rank_by_recency(int_cds, recency, limit)
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return []
