# -*- coding: utf-8 -*-
"""Mode state machine: turn a VehicleSnapshot into a ResearchProgressModel.

Per selected vehicle, in priority order:
- something still to research -> TECH_TREE (modules + next vehicles).
- nothing left -> COMPLETE (a "fully researched" badge).

Fill is the player's spendable XP shown as two stacked segments: vehicle XP first,
then global free XP. The view treats a scale_min == scale_max range as 100% (guard
divide-by-zero). This is the extension point: add a resolver + a branch here for each
new mode (field mods, prestige, ...), highest priority first. Pure and engine-free.
"""
from moe_calculator.domain import types as t
from moe_calculator.domain.resolvers import techtree


def _max_pos(ticks, default):
    return max([tk.xp_position for tk in ticks]) if ticks else default


def _on(enabled, mode):
    """Whether `mode` is enabled. `enabled` is a set of Mode strings the user has left
    ON; None means "all on" (the default, so callers/tests that pass no toggle set
    behave exactly as before). A mode absent from a non-None set is OFF."""
    return enabled is None or mode in enabled


def bar_visible(overlay_closed, hide_always, hide_when_complete, mode, in_garage):
    """Whether the bar should render, combining engine state (a tank-setup overlay
    open -> overlay_closed is False; the plain garage is mounted -> in_garage is True)
    with two user settings. Pure and engine-free so it unit-tests on plain inputs.

    - hide_always: master switch -> never show.
    - Mode.HIDDEN: the vehicle's resolved mode is turned off by a per-mode toggle.
    - in_garage: show ONLY in the plain garage view (fail-closed allowlist).
    - hide_when_complete: hide only on fully-progressed vehicles (Mode.COMPLETE).
    - otherwise follow the overlay state (hidden while a setup overlay is open)."""
    if hide_always:
        return False
    if mode == t.Mode.HIDDEN:
        return False
    if not in_garage:
        return False
    if hide_when_complete and mode == t.Mode.COMPLETE:
        return False
    return overlay_closed


def build_model(snapshot, enabled=None):
    """`enabled` is the set of Mode strings the user has left ON (None = all on). The
    mode is resolved by the priority chain; if the resolved mode is OFF, the bar is
    HIDDEN -- there is NO fall-through to a lower-priority mode, and COMPLETE is
    reached only when the vehicle is genuinely done (no branch matched)."""
    fill_vehicle = snapshot.vehicle_xp
    fill_free = snapshot.free_xp
    spendable = fill_vehicle + fill_free
    veh_class = snapshot.vehicle_class

    def _hidden():
        # The resolved mode is toggled off: a placeholder model carrying Mode.HIDDEN so
        # bar_visible() hides the bar (the view never renders it).
        return t.ResearchProgressModel(
            mode=t.Mode.HIDDEN, scale_min=0, scale_max=0,
            fill_vehicle=fill_vehicle, fill_free=fill_free, ticks=[],
            spendable_xp=spendable, vehicle_class=veh_class)

    def _emit(mode, model):
        # Honor the per-mode toggle: a mode this vehicle RESOLVED to but which the user
        # turned off hides the bar -- NO fall-through to a lower-priority mode.
        return model if _on(enabled, mode) else _hidden()

    # Research takes priority: while ANY tech unlock is still unresearched, show the
    # tech tree. techtree.resolve returns remaining-only ticks, so its emptiness is
    # the exact "nothing left to research" signal.
    ticks = techtree.resolve(snapshot)
    if ticks:
        return _emit(t.Mode.TECH_TREE, t.ResearchProgressModel(
            mode=t.Mode.TECH_TREE, scale_min=0, scale_max=_max_pos(ticks, 0),
            fill_vehicle=fill_vehicle, fill_free=fill_free, ticks=ticks,
            spendable_xp=spendable, vehicle_class=veh_class))

    # Nothing left to research: COMPLETE (a genuine end-state, never toggled).
    return t.ResearchProgressModel(
        mode=t.Mode.COMPLETE, scale_min=0, scale_max=0,
        fill_vehicle=fill_vehicle, fill_free=fill_free, ticks=[],
        spendable_xp=spendable, vehicle_class=veh_class)
