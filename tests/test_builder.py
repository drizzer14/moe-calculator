# -*- coding: utf-8 -*-
"""Starter tests for the engine-free layers. These run on Python 3 (no game engine)
because the domain + wulf_args modules import zero game symbols -- that separation is
the whole point of the layering. Grow these as you add resolvers and modes."""
from moe_calculator.domain import types as t
from moe_calculator.domain.builder import build_model, bar_visible
from moe_calculator.bridge import wulf_args as w


def _u(cd, cost, researched=False, kind="module"):
    return t.UnlockItem(cd, "u%d" % cd, "u%d.png" % cd, cost, kind, researched, True)


# --- build_model -------------------------------------------------------------

def test_not_elite_is_tech_tree():
    snap = t.VehicleSnapshot(tier=6, is_elite=False, vehicle_xp=500, free_xp=0,
                             tech_unlocks=[_u(1, 1000), _u(2, 500)])
    m = build_model(snap)
    assert m.mode == t.Mode.TECH_TREE
    assert m.scale_min == 0
    assert m.scale_max == 1000          # max own cost (per-item, not cumulative)
    assert m.fill_vehicle == 500
    assert m.fill_free == 0
    # ticks sort by cost; each carries the unlock kind as its category + int_cd id
    assert [tk.xp_position for tk in m.ticks] == [500, 1000]
    assert [tk.action_id for tk in m.ticks] == [2, 1]
    assert all(tk.category == "module" for tk in m.ticks)


def test_fill_is_two_segments_and_affordability():
    snap = t.VehicleSnapshot(tier=5, is_elite=False, vehicle_xp=800, free_xp=300,
                             tech_unlocks=[_u(1, 600), _u(2, 5000)])
    m = build_model(snap)
    assert m.fill_vehicle == 800
    assert m.fill_free == 300
    assert m.spendable_xp == 1100
    # spendable = 1100 affords the 600 tick, not the 5600 tick
    assert [tk.affordable for tk in m.ticks] == [True, False]


def test_nothing_left_is_complete():
    snap = t.VehicleSnapshot(tier=8, is_elite=True, vehicle_xp=0, free_xp=0,
                             tech_unlocks=[_u(1, 1000, researched=True)])
    m = build_model(snap)
    assert m.mode == t.Mode.COMPLETE
    assert m.ticks == []
    assert m.scale_min == m.scale_max     # zero-width range -> view renders 100%


# --- per-mode toggles (enabled set) -----------------------------------------

def test_tech_tree_disabled_hides():
    snap = t.VehicleSnapshot(tier=6, is_elite=False, vehicle_xp=500, free_xp=0,
                             tech_unlocks=[_u(1, 1000)])
    m = build_model(snap, {t.Mode.COMPLETE})   # TECH_TREE not in the enabled set
    assert m.mode == t.Mode.HIDDEN
    assert m.ticks == []


def test_enabled_none_is_all_on():
    snap = t.VehicleSnapshot(tier=6, is_elite=False, vehicle_xp=0, free_xp=0,
                             tech_unlocks=[_u(1, 1000)])
    assert build_model(snap).mode == t.Mode.TECH_TREE
    assert build_model(snap, None).mode == t.Mode.TECH_TREE


# --- bar_visible -------------------------------------------------------------

def test_bar_visible_gates():
    # visible in the plain garage with the overlay closed
    assert bar_visible(True, False, False, t.Mode.TECH_TREE, True) is True
    # hidden while a setup overlay is open
    assert bar_visible(False, False, False, t.Mode.TECH_TREE, True) is False
    # master hide-always wins
    assert bar_visible(True, True, False, t.Mode.TECH_TREE, True) is False
    # not in the plain garage -> hidden (fail-closed allowlist)
    assert bar_visible(True, False, False, t.Mode.TECH_TREE, False) is False
    # hide-when-complete only affects COMPLETE
    assert bar_visible(True, False, True, t.Mode.COMPLETE, True) is False
    assert bar_visible(True, False, True, t.Mode.TECH_TREE, True) is True
    # a HIDDEN model is never shown
    assert bar_visible(True, False, False, t.Mode.HIDDEN, True) is False


# --- wulf_args (JS command argument parsing) --------------------------------

class _WulfMap(object):
    """Stand-in for a Wulf-wrapped map: not a dict, but has .get(key)."""
    def __init__(self, d):
        self._d = d

    def get(self, key):
        return self._d.get(key)


def test_cmd_int_arg_variants():
    assert w.cmd_int_arg([{"value": 123}]) == 123
    assert w.cmd_int_arg([{"id": 456}]) == 456
    assert w.cmd_int_arg([_WulfMap({"value": 789})]) == 789
    assert w.cmd_int_arg([321]) == 321
    assert w.cmd_int_arg([{"value": "55"}]) == 55
    assert w.cmd_int_arg([]) == 0
    assert w.cmd_int_arg(None) == 0
    assert w.cmd_int_arg([{"value": "nope"}]) == 0


def test_cmd_xy_arg_variants():
    assert w.cmd_xy_arg([{"x": 10, "y": 20}]) == (10, 20)
    assert w.cmd_xy_arg([_WulfMap({"x": 3, "y": 4})]) == (3, 4)
    assert w.cmd_xy_arg([{"x": 10}]) == (10, 0)
    assert w.cmd_xy_arg([]) == (0, 0)
    assert w.cmd_xy_arg(None) == (0, 0)
