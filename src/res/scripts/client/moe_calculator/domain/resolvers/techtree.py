# -*- coding: utf-8 -*-
"""Example resolver: turn the snapshot's tech-tree unlocks into bar ticks.

A resolver is a pure function snapshot -> [Tick] (or a small result dict) for ONE
category of the bar. build_model() calls the resolvers in priority order and wraps
the winner in a ResearchProgressModel. Add a resolver module per mode as your mod
grows; keep each one engine-free so it unit-tests on plain inputs.
"""
from moe_calculator.domain import types as t


def resolve(snapshot):
    """Return tech-tree ticks ordered by XP cost (remaining/unresearched only).

    Each tick is priced at its OWN cost, not a cumulative running total: tech-tree
    items are independently researchable, so a cheaper sibling must not inflate
    another item's position or block its affordability.
    """
    spendable = snapshot.vehicle_xp + snapshot.free_xp
    remaining = [u for u in snapshot.tech_unlocks if not u.researched]
    remaining.sort(key=lambda u: u.xp_cost)
    ticks = []
    for u in remaining:
        # category carries the unlock kind ('vehicle' | 'module') so the view can
        # draw a distinct glyph for the next-tank tick vs module ticks.
        ticks.append(t.Tick(
            xp_position=u.xp_cost, category=u.kind, icon=u.icon, name=u.name,
            xp_required=u.xp_cost, affordable=(u.xp_cost <= spendable),
            completed=False, action_id=u.int_cd))
    return ticks
