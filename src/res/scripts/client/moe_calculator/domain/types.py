# -*- coding: utf-8 -*-
"""Engine-free data types shared by the domain layer. 2/3 compatible.

This is the boundary between the game engine and the pure logic: the adapter layer
reads the live client into a VehicleSnapshot, the domain layer turns that into a
ResearchProgressModel, and the bridge marshals the model to the Gameface widget.
NOTHING here may import a game symbol -- that is what lets the domain unit-test on
plain Python 3 (see tests/). Extend these dataclass-ish objects as your mod grows.
"""


class Mode(object):
    """The bar's resolved mode -- a small set of string constants (an enum without the
    enum module, so it stays 2.7-friendly and marshals as a plain string to JS). These
    VALUES are the wire contract with the widget; keep them in lockstep with the MODE
    map in the .js. Add modes as your mod grows (field mods, prestige, ...)."""
    TECH_TREE = "tech_tree"     # something still to research: modules + next vehicles
    COMPLETE = "complete"       # nothing left -> a "done" badge
    HIDDEN = "hidden"           # the resolved mode is disabled by a user toggle ->
                                # bar_visible() returns False (the view never renders it)


class Tick(object):
    """One mark on the bar. `category` drives the per-tick glyph the widget renders
    (see domain/constants.py Category); `action_id` carries the clickable identity
    (0 = not individually actionable)."""
    def __init__(self, xp_position, category, icon, name,
                 xp_required, affordable, completed, action_id=0):
        self.xp_position = xp_position
        self.category = category
        self.icon = icon
        self.name = name
        self.xp_required = xp_required
        self.affordable = affordable
        self.completed = completed
        self.action_id = action_id


class UnlockItem(object):
    """A tech-tree unlock (module or next vehicle) read from the live client."""
    def __init__(self, int_cd, name, icon, xp_cost, kind, researched, prereqs_met=True):
        self.int_cd = int_cd
        self.name = name
        self.icon = icon
        self.xp_cost = xp_cost
        self.kind = kind                  # 'module' | 'vehicle' (see Category)
        self.researched = researched
        self.prereqs_met = prereqs_met


class VehicleSnapshot(object):
    """Engine-free description of the selected vehicle's state.

    The engine adapter produces this; the domain layer consumes only this. All XP
    fields are real ints (never None) and lists are in natural progression order.
    """
    def __init__(self, tier, is_elite, vehicle_xp, free_xp, tech_unlocks=None,
                 vehicle_class="", vehicle_int_cd=0):
        self.tier = tier                          # 1..N
        self.is_elite = is_elite                  # True = fully researched
        self.vehicle_xp = vehicle_xp              # unspent accumulated vehicle XP
        self.free_xp = free_xp                    # global free XP
        self.tech_unlocks = tech_unlocks or []    # [UnlockItem]
        self.vehicle_class = vehicle_class        # class id ('mediumTank' etc.)
        self.vehicle_int_cd = vehicle_int_cd      # compact-descriptor id (0 if unknown)


class ResearchProgressModel(object):
    """Output of build_model(). Fill is two stacked segments (vehicle XP, then free
    XP); the view draws fill_vehicle first and fill_free on top."""
    def __init__(self, mode, scale_min, scale_max, fill_vehicle, fill_free, ticks,
                 spendable_xp=0, vehicle_class=""):
        self.mode = mode
        self.scale_min = scale_min
        self.scale_max = scale_max
        self.fill_vehicle = fill_vehicle       # first stacked segment (vehicle XP)
        self.fill_free = fill_free             # second stacked segment (free XP)
        self.ticks = ticks                     # [Tick], ordered by xp_position
        # Total spendable XP (vehicle combat XP + global free XP) -- set on every model
        # so the view can compute per-item affordability in any mode.
        self.spendable_xp = spendable_xp
        self.vehicle_class = vehicle_class
