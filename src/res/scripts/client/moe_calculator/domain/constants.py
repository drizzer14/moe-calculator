# -*- coding: utf-8 -*-
"""Shared constants used across the domain, adapter, and view.

Centralizing them means a typo is a NameError instead of a silently mismatched value.
The mark milestone percents are the wire contract with the widget JS -- keep them in
lockstep with the MARK_PERCENTS array in the .js. 2/3-compatible, engine-free.
"""


# The three Marks of Excellence milestones, as percentiles of the vehicle's player
# population combined-damage distribution. 1 mark = 65th percentile, 2 = 85th, 3 = 95th.
# Index 0..2 <-> mark count 1..3. These positions are FIXED (the bar axis is the
# percentile 0..100), so the ticks always sit at the same spots regardless of vehicle.
MARK_PERCENTS = (65, 85, 95)

# Mark counts, parallel to MARK_PERCENTS.
MARK_COUNTS = (1, 2, 3)

# The full percentile axis the bar spans.
AXIS_MIN = 0
AXIS_MAX = 100

# In-battle projected-rating (EWMA) coefficient. WG's Marks rating is a moving average
# over "~50-100 battles"; we model it as an EWMA newAvg = prevAvg + k*(CD - prevAvg) with
# k = 2/(N+1), N=100 (k ~= 0.0198). N/k are community-reverse-engineered, NOT WG-confirmed
# -- treat as an assumption to validate against real replays (see TASKS/in-battle-moe-panel.md).
EWMA_N = 100
EWMA_K = 2.0 / (EWMA_N + 1)

# In-battle overlay window anchor, in FIXED logical-GUI-space px. WG's efficiency panel is
# laid out in logical units (physical px / interfaceScale), so its screen corner sits at the
# SAME logical coordinate at every interface scale -- a fixed logical offset tracks it with
# NO per-scale multiplication (confirmed in-client at 1x AND 2x; the old fraction-of-space
# anchor wrongly doubled X to ~529 at 1x). X is measured from the LEFT edge, Y from the
# BOTTOM edge (0 = bottom-flush). Calibrated empirically to WG's efficiency panel corner
# (WG panels are Flash -- no runtime position API). Phase 2's raised anchor is a larger Y.
BATTLE_ANCHOR_X = 264
BATTLE_ANCHOR_Y = 0
