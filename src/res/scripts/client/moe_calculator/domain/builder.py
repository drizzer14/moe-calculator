# -*- coding: utf-8 -*-
"""Turn a MoESnapshot into a MoEModel. Pure and engine-free.

The bar axis is the percentile 0..100. The three ticks sit at the fixed MARK_PERCENTS
(65/85/95); each carries the combined-damage requirement for that mark (from the
external table, or 0 when unknown) and whether the player already holds it. `fill` is
the current damage rating (percentile) -- the game's own authoritative "distance to
next mark", independent of the fetched thresholds, so the fill stays correct even if
the external table is a different vintage.
"""
from moe_calculator.domain import types as t
from moe_calculator.domain.constants import MARK_PERCENTS, MARK_COUNTS, AXIS_MIN, AXIS_MAX


def _clamp(value, lo, hi):
    return lo if value < lo else hi if value > hi else value


def build_model(snapshot):
    """Build the three-tick MoE model from the snapshot. Always returns a model with
    three ticks; visibility is decided separately by bar_visible()."""
    percentile = _clamp(float(snapshot.cur_percentile or 0.0), AXIS_MIN, AXIS_MAX)
    thresholds = snapshot.thresholds or {}

    ticks = []
    has_data = False
    for percent, count in zip(MARK_PERCENTS, MARK_COUNTS):
        required = int(thresholds.get(count, 0) or 0)
        if required > 0:
            has_data = True
        ticks.append(t.MarkTick(
            percent=percent,
            mark_count=count,
            damage_required=required,
            reached=(snapshot.marks or 0) >= count,
            icon=""))

    return t.MoEModel(
        nation=snapshot.nation or "",
        marks=snapshot.marks or 0,
        cur_percentile=percentile,
        cur_avg_damage=int(snapshot.cur_avg_damage or 0),
        fill=percentile,
        ticks=ticks,
        vehicle_int_cd=snapshot.vehicle_int_cd or 0,
        has_data=has_data)


def bar_visible(overlay_closed, in_garage, has_vehicle):
    """Whether the bar should render. Pure/engine-free so it unit-tests on plain inputs.

    - has_vehicle : a vehicle must be selected.
    - in_garage   : show ONLY in the plain garage (fail-closed allowlist; the vehicle-
                    params sub-view we inject into stays mounted on other lobby views).
    - overlay_closed : hidden while a tank-setup overlay (ammo/equipment/...) is open.
    """
    if not has_vehicle:
        return False
    if not in_garage:
        return False
    return overlay_closed
