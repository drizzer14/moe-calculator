# -*- coding: utf-8 -*-
"""Pure logic for the persistent MoE fetch list -- the capped, recency-ranked working set of
owned tank ids we maintain thresholds for.

The *list* is membership + recency ("which tanks we want data for"); the fetched thresholds
live elsewhere (adapter/moe_wgapi._table + its own cache file). Keeping them separate lets the
existing threshold-cache freshness + _table/_seen/_inflight dedup do the 24h-throttle work,
while this module owns only the set arithmetic:

  bootstrap_ids   : the session-open seed when the list is empty (selected + recent-30d).
  add_with_eviction : add a tank, evicting the least-recently-played member when full.
  remove_id       : drop a sold tank.
  purge_stale     : session-open drop of tanks not played within the window.
  needs_refetch   : the boolean "is the current data older than the revalidation window".

Everything is pure (no engine imports): the caller passes now_epoch / recency_map / cap so
each function is directly unit-testable, mirroring garage_roster.rank_by_recency. Recency is
epoch seconds; a missing entry is treated as 0 (never played -> oldest). Defaults come from
domain/constants so the cap / window / ttl have a single source.
"""
from moe_calculator.domain import constants


def _recency(recency_map, cd):
    """Recency (epoch s) for a tank, 0 (oldest) when unknown/unparseable. Pure."""
    try:
        return int(recency_map.get(cd, 0) or 0)
    except (TypeError, ValueError, AttributeError):
        return 0


def bootstrap_ids(selected_cd, recent_cds, recency_map, now_epoch,
                  cap=constants.FETCH_LIST_CAP, max_age=constants.STALE_WINDOW_SECONDS):
    """Seed an empty list: the selected vehicle (always kept, even if never played) plus the
    recently-played owned vehicles played within `max_age`, capped at `cap`.

    `recent_cds` is expected pre-ranked by the caller (most-recently-played first). It is
    filtered to played-within-window, deduped against `selected_cd` and each other with order
    preserved, and the selected tank takes the first slot. Returns an ordered int list."""
    cutoff = now_epoch - max_age
    result = []
    seen = set()
    if selected_cd:
        result.append(int(selected_cd))
        seen.add(int(selected_cd))
    for cd in recent_cds:
        if not cd or cd in seen:
            continue
        if _recency(recency_map, cd) < cutoff:
            continue
        result.append(int(cd))
        seen.add(int(cd))
    return result[:cap]


def add_with_eviction(current, recency_map, new_cd, cap=constants.FETCH_LIST_CAP):
    """Add `new_cd`, returning (new_list, evicted_cd_or_None).

    Idempotent: an id already present returns the list unchanged and no eviction. With room to
    spare the id is appended. When the list is full the least-recently-played CURRENT member is
    evicted first (tie -> largest intCD, exactly the element rank_by_recency would drop off the
    tail), then the new id is appended. Pure."""
    ids = [int(c) for c in current]
    new_cd = int(new_cd)
    if new_cd in ids:
        return ids, None
    if len(ids) < cap:
        return ids + [new_cd], None
    victim = sorted(ids, key=lambda cd: (_recency(recency_map, cd), -cd))[0]
    kept = [cd for cd in ids if cd != victim]
    return kept + [new_cd], victim


def remove_id(current, cd):
    """Return `current` with `cd` removed (unchanged if absent). Pure."""
    cd = int(cd)
    return [int(c) for c in current if int(c) != cd]


def purge_stale(current, recency_map, now_epoch, max_age=constants.STALE_WINDOW_SECONDS):
    """Split `current` into (kept, purged) by recency: keep tanks played at or after
    now_epoch - max_age (boundary inclusive), purge the rest. Pure."""
    cutoff = now_epoch - max_age
    kept, purged = [], []
    for cd in current:
        (kept if _recency(recency_map, cd) >= cutoff else purged).append(int(cd))
    return kept, purged


def needs_refetch(updated_at, now_epoch, ttl=constants.REVALIDATE_SECONDS):
    """True when the current data is missing or older than the revalidation window -- i.e. a
    fresh batch fetch is due. False while now_epoch < updated_at + ttl (so repeated sessions in
    the same day serve the cache without refetching). Pure."""
    try:
        return now_epoch >= int(updated_at) + ttl
    except (TypeError, ValueError):
        return True
