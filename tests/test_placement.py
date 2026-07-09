# -*- coding: utf-8 -*-
"""Tests for the engine-free collision-aware placement decision. Runs on Python 3 (no
game engine): domain.placement imports zero game symbols. It mirrors the sibling Garage
Progress Bar's suite (see TASKS/collision-aware-injection.md).

The decision walks a priority `order` of candidate sub-view names, given `vms`
(name -> ViewModel, or None/absent when the sub-view has not mounted yet) and a
`has_inject(vm)` predicate (True when that VM already carries a foreign mod's inject
model). The FIRST not-yet-mounted candidate forces WAIT so we never commit to a fallback
while a preferred sub-view is still pending; a mounted+free candidate is INJECTed; a
mounted+occupied one is skipped; BLOCKED only when every candidate is mounted+occupied.
"""
from moe_calculator.domain.placement import (
    choose_placement, WAIT, INJECT, BLOCKED)


# Sentinel ViewModels. `_occupied` marks the ones a foreign mod already claimed; the
# has_inject predicate below is membership in that set (mirrors the live
# `'"ModInjectModel"' in vm.proxy.toString()` detector without needing a real proxy).
_FREE = "vm-free"
_OCCUPIED = "vm-occupied"


def _has_inject(vm):
    return vm == _OCCUPIED


def test_preferred_free_injects_preferred():
    action, name = choose_placement(
        ["params", "stats"], {"params": _FREE}, _has_inject)
    assert (action, name) == (INJECT, "params")


def test_preferred_unmounted_waits():
    # Preferred not mounted yet (explicit None) -> WAIT for it, do not fall through.
    action, name = choose_placement(
        ["params", "stats"], {"params": None}, _has_inject)
    assert (action, name) == (WAIT, "params")


def test_preferred_absent_from_map_also_waits():
    # A name missing from the map is treated identically to an explicit None (unmounted).
    action, name = choose_placement(
        ["params", "stats"], {}, _has_inject)
    assert (action, name) == (WAIT, "params")


def test_fallback_free_but_preferred_pending_waits():
    # The fallback is mounted+free, but the PREFERRED has not mounted yet -> WAIT on the
    # preferred. We must not commit to the fallback while a higher-priority slot is pending.
    action, name = choose_placement(
        ["params", "stats"], {"stats": _FREE}, _has_inject)
    assert (action, name) == (WAIT, "params")


def test_preferred_foreign_fallback_free_injects_fallback():
    # Preferred is foreign-occupied (skip), fallback is mounted+free -> inject the fallback.
    action, name = choose_placement(
        ["params", "stats"], {"params": _OCCUPIED, "stats": _FREE}, _has_inject)
    assert (action, name) == (INJECT, "stats")


def test_preferred_foreign_fallback_pending_waits_on_fallback():
    # Preferred is occupied (skip); the fallback has not mounted yet -> WAIT on the
    # fallback (it may still come up free). Never BLOCKED while a candidate is pending.
    action, name = choose_placement(
        ["params", "stats"], {"params": _OCCUPIED}, _has_inject)
    assert (action, name) == (WAIT, "stats")


def test_all_mounted_and_occupied_is_blocked():
    action, name = choose_placement(
        ["params", "stats"], {"params": _OCCUPIED, "stats": _OCCUPIED}, _has_inject)
    assert action == BLOCKED
    assert name is None


def test_single_candidate_free_injects():
    action, name = choose_placement(["params"], {"params": _FREE}, _has_inject)
    assert (action, name) == (INJECT, "params")


def test_single_candidate_foreign_is_blocked():
    action, name = choose_placement(["params"], {"params": _OCCUPIED}, _has_inject)
    assert action == BLOCKED
    assert name is None


def test_single_candidate_unmounted_waits():
    action, name = choose_placement(["params"], {"params": None}, _has_inject)
    assert (action, name) == (WAIT, "params")


def test_empty_order_is_blocked():
    # Degenerate: no candidates at all -> nothing to place on.
    action, name = choose_placement([], {}, _has_inject)
    assert action == BLOCKED
    assert name is None
