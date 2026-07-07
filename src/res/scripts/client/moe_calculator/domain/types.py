# -*- coding: utf-8 -*-
"""Engine-free data types shared by the domain layer. 2/3 compatible.

This is the boundary between the game engine and the pure logic: the adapter layer
reads the live client into a MoESnapshot, the domain layer turns that into a MoEModel,
and the bridge marshals the model to the Gameface widget. NOTHING here may import a
game symbol -- that is what lets the domain unit-test on plain Python 3 (see tests/).
"""


class MoESnapshot(object):
    """Engine-free description of the selected vehicle's Marks of Excellence state.

    The engine adapter produces this; the domain layer consumes only this.

    - `marks`          : current marks on gun, 0..3 (dossier marksOnGun).
    - `cur_percentile` : current damage rating as a percentile 0.0..100.0
                         (dossier damageRating; how far toward the next mark).
    - `cur_avg_damage` : current moving-average combined damage (dossier movingAvgDamage).
    - `thresholds`     : {1: dmg, 2: dmg, 3: dmg, 100: dmg} combined-damage required for
                         each mark plus the 100th-percentile goalpost (key 100), fetched
                         from the external table; {} when unknown/not loaded yet.
    - `nation`         : nation id string for the mark art ('germany', 'ussr', ...); ''.
    - `has_vehicle`    : whether a vehicle is actually selected (False -> bar hidden).
    """
    def __init__(self, vehicle_int_cd=0, nation="", marks=0, cur_percentile=0.0,
                 cur_avg_damage=0, thresholds=None, has_vehicle=True):
        self.vehicle_int_cd = vehicle_int_cd
        self.nation = nation
        self.marks = marks
        self.cur_percentile = cur_percentile
        self.cur_avg_damage = cur_avg_damage
        self.thresholds = thresholds or {}
        self.has_vehicle = has_vehicle


class MarkTick(object):
    """One of the three milestone ticks on the bar.

    - `percent`         : fixed axis position 65 / 85 / 95.
    - `mark_count`      : 1 / 2 / 3 (which mark this tick represents).
    - `damage_required` : combined damage needed for this mark, or 0 when unknown
                          (widget then hides the requirement label for this tick).
    - `reached`         : True when the player already holds this mark (marks >= count).
    - `icon`            : the mark-art URL; filled by the adapter/bridge (engine/asset
                          knowledge), left "" by the pure domain.
    """
    def __init__(self, percent, mark_count, damage_required=0, reached=False, icon=""):
        self.percent = percent
        self.mark_count = mark_count
        self.damage_required = damage_required
        self.reached = reached
        self.icon = icon


class MoEModel(object):
    """Output of build_model(). The bar axis is the percentile 0..100; `fill` is the
    current percentile (how close to the next mark). Ticks are always the three
    milestones in ascending order."""
    def __init__(self, nation, marks, cur_percentile, cur_avg_damage, fill, ticks,
                 vehicle_int_cd=0, has_data=False, end_damage_required=0):
        self.nation = nation
        self.marks = marks                       # 0..3
        self.cur_percentile = cur_percentile     # 0.0..100.0
        self.cur_avg_damage = cur_avg_damage     # raw combined damage
        self.fill = fill                         # 0..100 (clamped percentile)
        self.ticks = ticks                       # [MarkTick] * 3, ascending
        self.vehicle_int_cd = vehicle_int_cd
        # Combined damage for the 100th percentile (the bar's right-edge goalpost, beyond
        # the 3 marks). 0 when unknown / external table not loaded.
        self.end_damage_required = end_damage_required
        # True when at least one tick carries a real damage requirement (the external
        # table was loaded for this vehicle). Lets the view/tests know data is present.
        self.has_data = has_data
