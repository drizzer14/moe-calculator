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
