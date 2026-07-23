# -*- coding: utf-8 -*-
"""Tests for the engine-free domain layer. These run on Python 3 (no game engine)
because the domain + wulf_args modules import zero game symbols -- that separation is
the whole point of the layering."""
from moe_calculator.domain import types as t
from moe_calculator.domain.builder import build_model, bar_visible
from moe_calculator.domain.constants import MARK_PERCENTS
from moe_calculator.bridge import wulf_args as w


# --- build_model -------------------------------------------------------------

def _snap(**kw):
    base = dict(vehicle_int_cd=1073, nation="germany", marks=1, cur_percentile=72.5,
                cur_avg_damage=1500, thresholds={1: 1291, 2: 1858, 3: 2287})
    base.update(kw)
    return t.MoESnapshot(**base)


def test_three_ticks_at_fixed_percents():
    m = build_model(_snap())
    assert [tk.percent for tk in m.ticks] == list(MARK_PERCENTS)
    assert [tk.mark_count for tk in m.ticks] == [1, 2, 3]


def test_thresholds_mapped_per_mark():
    m = build_model(_snap())
    assert [tk.damage_required for tk in m.ticks] == [1291, 1858, 2287]
    assert m.has_data is True


def test_reached_reflects_current_marks():
    m = build_model(_snap(marks=2))
    assert [tk.reached for tk in m.ticks] == [True, True, False]
    m0 = build_model(_snap(marks=0))
    assert [tk.reached for tk in m0.ticks] == [False, False, False]
    m3 = build_model(_snap(marks=3))
    assert [tk.reached for tk in m3.ticks] == [True, True, True]


def test_fill_is_current_percentile_clamped():
    assert build_model(_snap(cur_percentile=72.5)).fill == 72.5
    assert build_model(_snap(cur_percentile=140.0)).fill == 100.0
    assert build_model(_snap(cur_percentile=-5.0)).fill == 0.0


def test_nan_percentile_clamps_to_zero_not_propagated():
    # A NaN cur_percentile (e.g. a bad dossier read) must be clamped, not passed through to the
    # widget: NaN compares False against the bounds, so the naive clamp would leak it.
    m = build_model(_snap(cur_percentile=float("nan")))
    assert m.fill == 0.0
    assert m.cur_percentile == 0.0


def test_missing_thresholds_degrade_gracefully():
    m = build_model(_snap(thresholds={}))
    # still three ticks with reached state + current readout, just no damage labels
    assert len(m.ticks) == 3
    assert [tk.damage_required for tk in m.ticks] == [0, 0, 0]
    assert m.has_data is False
    assert m.cur_avg_damage == 1500
    assert m.marks == 1


def test_partial_thresholds():
    m = build_model(_snap(thresholds={1: 1291}))
    assert [tk.damage_required for tk in m.ticks] == [1291, 0, 0]
    assert m.has_data is True


def test_end_damage_required_from_100_key():
    # The 100th-percentile goalpost comes from thresholds[100]; absent -> 0.
    m = build_model(_snap(thresholds={1: 1291, 2: 1858, 3: 2287, 100: 2641}))
    assert m.end_damage_required == 2641
    assert build_model(_snap(thresholds={1: 1291})).end_damage_required == 0
    assert build_model(_snap(thresholds={})).end_damage_required == 0


def test_never_played_zeros():
    m = build_model(_snap(marks=0, cur_percentile=0.0, cur_avg_damage=0, thresholds={}))
    assert m.fill == 0.0
    assert m.marks == 0
    assert all(not tk.reached for tk in m.ticks)


# --- bar_visible -------------------------------------------------------------

def test_bar_visible_gates():
    # visible in the plain garage, overlay closed, vehicle selected
    assert bar_visible(True, True, True) is True
    # hidden while a setup overlay is open
    assert bar_visible(False, True, True) is False
    # not in the plain garage -> hidden (fail-closed allowlist)
    assert bar_visible(True, False, True) is False
    # no vehicle selected -> hidden
    assert bar_visible(True, True, False) is False


def test_bar_visible_disabled_setting_hides():
    # "Garage Widget Enabled" off is a hard override: hides an otherwise-visible bar.
    assert bar_visible(True, True, True, enabled=False) is False
    # Default (enabled) preserves prior behavior.
    assert bar_visible(True, True, True, enabled=True) is True
    assert bar_visible(True, True, True) is True


# --- wulf_args (JS command argument parsing) --------------------------------

class _WulfMap(object):
    """Stand-in for a Wulf-wrapped map: not a dict, but has .get(key)."""
    def __init__(self, d):
        self._d = d

    def get(self, key):
        return self._d.get(key)


def test_cmd_xy_arg_variants():
    # The setPosition arg is a BARE MAP {x, y, w, h} (no {value:...} wrap). Parse a plain dict
    # and a Wulf-wrapped map object; a missing key or a non-numeric value degrades to 0.
    assert w.cmd_xy_arg([{"x": 10, "y": 20}]) == (10, 20)
    assert w.cmd_xy_arg([_WulfMap({"x": 3, "y": 4})]) == (3, 4)
    assert w.cmd_xy_arg([{"x": 10}]) == (10, 0)          # missing y -> 0
    assert w.cmd_xy_arg([{"y": 20}]) == (0, 20)          # missing x -> 0
    assert w.cmd_xy_arg([{}]) == (0, 0)                  # both missing -> (0, 0)
    assert w.cmd_xy_arg([{"x": "50", "y": "60"}]) == (50, 60)   # numeric strings coerce
    assert w.cmd_xy_arg([{"x": "nope", "y": 20}]) == (0, 20)    # non-numeric -> 0
    assert w.cmd_xy_arg([{"x": None, "y": None}]) == (0, 0)
    assert w.cmd_xy_arg([]) == (0, 0)
    assert w.cmd_xy_arg(None) == (0, 0)


def test_cmd_wh_arg_variants():
    # The capture-viewport (w, h) rides the same bare MAP; same tolerance as cmd_xy_arg.
    assert w.cmd_wh_arg([{"w": 1920, "h": 1080}]) == (1920, 1080)
    assert w.cmd_wh_arg([_WulfMap({"w": 2560, "h": 1440})]) == (2560, 1440)
    assert w.cmd_wh_arg([{"w": 800}]) == (800, 0)        # missing h -> 0
    assert w.cmd_wh_arg([{"h": 600}]) == (0, 600)        # missing w -> 0
    assert w.cmd_wh_arg([{}]) == (0, 0)                  # both missing -> (0, 0)
    assert w.cmd_wh_arg([{"w": "1024", "h": "768"}]) == (1024, 768)  # numeric strings coerce
    assert w.cmd_wh_arg([{"w": "bad", "h": 768}]) == (0, 768)        # non-numeric -> 0
    assert w.cmd_wh_arg([]) == (0, 0)
    assert w.cmd_wh_arg(None) == (0, 0)


def test_cmd_xy_and_wh_share_one_map():
    # A single {x, y, w, h} map yields both pairs -- how _on_set_position reads a drag release.
    arg = [{"x": 100, "y": 200, "w": 1920, "h": 1080}]
    assert w.cmd_xy_arg(arg) == (100, 200)
    assert w.cmd_wh_arg(arg) == (1920, 1080)
