# -*- coding: utf-8 -*-
"""Tests for domain/fetch_list -- the pure set arithmetic behind the persistent fetch list.

Every rule from the spec is covered here without the game engine (the functions take
now_epoch / recency_map / cap as args). Engine reads + persistence live in the adapter and are
exercised in-client.
"""
from moe_calculator.domain import fetch_list
from moe_calculator.domain import constants

NOW = 1_700_000_000
WINDOW = constants.STALE_WINDOW_SECONDS  # 30 days
TTL = constants.REVALIDATE_SECONDS       # 24h


# --- bootstrap_ids -----------------------------------------------------------

def test_bootstrap_empty_recent_yields_just_selected():
    assert fetch_list.bootstrap_ids(10, [], {}, NOW) == [10]


def test_bootstrap_keeps_selected_even_if_never_played():
    # Selected tank has no recency entry (never played) but must still lead the list.
    assert fetch_list.bootstrap_ids(10, [], {}, NOW) == [10]


def test_bootstrap_filters_recent_to_played_within_window():
    recency = {20: NOW - 1000, 30: NOW - WINDOW - 1}  # 30 is just past the window
    assert fetch_list.bootstrap_ids(10, [20, 30], recency, NOW) == [10, 20]


def test_bootstrap_preserves_caller_ranked_order():
    recency = {20: NOW - 5, 30: NOW - 10, 40: NOW - 1}
    # Caller pre-ranked as [30, 20, 40]; we preserve it (after the selected slot).
    assert fetch_list.bootstrap_ids(10, [30, 20, 40], recency, NOW) == [10, 30, 20, 40]


def test_bootstrap_dedupes_selected_out_of_recent():
    recency = {10: NOW - 1, 20: NOW - 2}
    assert fetch_list.bootstrap_ids(10, [10, 20], recency, NOW) == [10, 20]


def test_bootstrap_no_selection_is_recent_only():
    recency = {20: NOW - 1, 30: NOW - 2}
    assert fetch_list.bootstrap_ids(None, [20, 30], recency, NOW) == [20, 30]


def test_bootstrap_caps_total_including_selected():
    recent = list(range(100, 200))  # 100 recent ids
    recency = dict((cd, NOW - 1) for cd in recent)
    out = fetch_list.bootstrap_ids(10, recent, recency, NOW, cap=5)
    assert len(out) == 5
    assert out[0] == 10  # selected keeps its slot


def test_bootstrap_boundary_played_exactly_at_cutoff_is_kept():
    recency = {20: NOW - WINDOW}  # exactly on the cutoff -> inclusive keep
    assert fetch_list.bootstrap_ids(None, [20], recency, NOW) == [20]


# --- add_with_eviction -------------------------------------------------------

def test_add_appends_when_room():
    out, evicted = fetch_list.add_with_eviction([1, 2], {}, 3, cap=5)
    assert out == [1, 2, 3]
    assert evicted is None


def test_add_existing_is_idempotent():
    out, evicted = fetch_list.add_with_eviction([1, 2, 3], {}, 2, cap=5)
    assert out == [1, 2, 3]
    assert evicted is None


def test_add_full_evicts_least_recently_played():
    recency = {1: NOW - 10, 2: NOW - 5, 3: NOW - 1}
    out, evicted = fetch_list.add_with_eviction([1, 2, 3], recency, 9, cap=3)
    assert evicted == 1                # oldest last-battle time
    assert out == [2, 3, 9]


def test_add_full_tie_evicts_largest_cd():
    # Two never-played tanks (recency 0) tie -> drop the largest intCD (matches rank_by_recency).
    out, evicted = fetch_list.add_with_eviction([5, 7], {}, 9, cap=2)
    assert evicted == 7
    assert out == [5, 9]


# --- remove_id ---------------------------------------------------------------

def test_remove_present():
    assert fetch_list.remove_id([1, 2, 3], 2) == [1, 3]


def test_remove_absent_is_unchanged():
    assert fetch_list.remove_id([1, 2, 3], 9) == [1, 2, 3]


# --- purge_stale -------------------------------------------------------------

def test_purge_keeps_recent_drops_old():
    recency = {1: NOW - 1000, 2: NOW - WINDOW - 1, 3: NOW - 5}
    kept, purged = fetch_list.purge_stale([1, 2, 3], recency, NOW)
    assert kept == [1, 3]
    assert purged == [2]


def test_purge_boundary_is_inclusive():
    recency = {1: NOW - WINDOW}  # exactly on the cutoff -> kept
    kept, purged = fetch_list.purge_stale([1], recency, NOW)
    assert kept == [1]
    assert purged == []


def test_purge_buy_time_now_is_kept():
    # A freshly bought tank stamped with recency = now survives the purge.
    kept, purged = fetch_list.purge_stale([1], {1: NOW}, NOW)
    assert kept == [1]
    assert purged == []


def test_purge_never_played_is_dropped():
    kept, purged = fetch_list.purge_stale([1], {}, NOW)  # recency 0 -> ancient
    assert kept == []
    assert purged == [1]


def test_purge_empty():
    assert fetch_list.purge_stale([], {}, NOW) == ([], [])


# --- needs_refetch -----------------------------------------------------------

def test_needs_refetch_missing_updated_at():
    assert fetch_list.needs_refetch(0, NOW) is True
    assert fetch_list.needs_refetch(None, NOW) is True


def test_needs_refetch_within_ttl_is_false():
    assert fetch_list.needs_refetch(NOW - 3600, NOW) is False


def test_needs_refetch_past_ttl_is_true():
    assert fetch_list.needs_refetch(NOW - TTL - 1, NOW) is True


def test_needs_refetch_boundary_is_true():
    # now == updated_at + ttl -> due (>= boundary).
    assert fetch_list.needs_refetch(NOW - TTL, NOW) is True
