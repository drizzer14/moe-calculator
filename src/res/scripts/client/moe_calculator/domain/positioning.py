# -*- coding: utf-8 -*-
"""Pure, engine-free placement math for the in-battle overlay window.

The overlay is a fixed-size Wulf surface positioned in the engine's LOGICAL GUI space
(physical px / interfaceScale). WG's own efficiency panel is anchored at a FIXED LOGICAL
offset from the screen edge -- confirmed in-client at 1x and 2x: the panel corner sits at
the same logical coordinate regardless of interface scale. So we place our window at a fixed
logical offset too (see constants.BATTLE_ANCHOR_X/Y) -- NO per-scale multiplication -- and
just clamp it to the window's movable extent (space - surface), which the caller recovers
with a far-sentinel calibration.

Anchoring convention: x is measured from the LEFT edge, y from the BOTTOM edge (so a larger
y_from_bottom RAISES the panel -- that's the hook the Phase-2 damage-log-aware anchor uses).
2/3-compatible, engine-free, unit-testable with the client closed.
"""


def damage_log_summary_hidden(total, blocked, assist, assist_stun):
    """True when ALL FOUR "Summarized damage" DAMAGE_LOG flags are unticked.

    When every summary total (damage / blocked / assist-damage / assist-stun) is off, WG
    collapses the summary block and the damage-log events shift UP -- so the overlay must
    move to the raised anchor (constants.BATTLE_ANCHOR_Y_RAISED). Any one flag ticked keeps
    the block present -> default anchor. Each flag is bool()-coerced so getSetting's 0/1/None
    read correctly, and the fail-soft "treat an unreadable flag as ticked" default (see
    battle_adapter) lands on the DEFAULT anchor rather than wrongly raising the panel."""
    return not (bool(total) or bool(blocked) or bool(assist) or bool(assist_stun))


def efficiency_panel_wide(flags, values, threshold):
    """True when any ENABLED "Summarized damage" total exceeds `threshold` (goes 5-digit).

    A five-digit total widens WG's efficiency panel by one character, colliding with the
    overlay -- so the caller shifts the overlay right (constants.BATTLE_ANCHOR_X_SHIFT). Only
    ENABLED totals count: a huge value whose summary flag is unticked isn't drawn, so it can't
    widen the panel. `flags` and `values` are aligned tuples (total, blocked, assist, stun):
    `flags` from battle_adapter.read_damage_log_summary_flags(), `values` from
    read_efficiency_totals(). Each flag is bool()-coerced (getSetting's 0/1/None) and each
    value guarded against None. The fail-soft reads default flags to ticked / values to 0, so a
    bad read never wrongly triggers the shift on a disabled/zero total."""
    return any(bool(f) and (v or 0) > threshold for f, v in zip(flags, values))


def anchor_top_left(max_x, max_y, x_from_left, y_from_bottom):
    """Top-left (x, y) in logical GUI space for the overlay window.

    `max_x, max_y` is the movable extent (= logical space - surface size) recovered by the
    caller's far-sentinel clamp. `x_from_left` / `y_from_bottom` are fixed logical offsets
    from the left/bottom screen edges. The result is clamped on-screen: x into [0, max_x],
    y into [0, max_y] (y = max_y - y_from_bottom, so y_from_bottom=0 is bottom-flush)."""
    x = min(max(0, x_from_left), max_x)
    y = min(max(0, max_y - y_from_bottom), max_y)
    return x, y
