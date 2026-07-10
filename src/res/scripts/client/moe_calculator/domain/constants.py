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

# Threshold key 100 is the bar's right-edge "goalpost" -- the combined damage at the 100th
# percentile. The WG API returns it directly (percentile=100), so the normal path carries it
# as-is. GOALPOST_PERCENTILE is used ONLY by the offline estimator fallback (moe_estimate),
# which fires when a WG-API request errors: the true 100th percentile is +infinity under a
# continuous distribution, so the estimator reads the goalpost off a high-but-finite percentile.
GOALPOST_PERCENTILE = 99

# The full percentile axis the bar spans.
AXIS_MIN = 0
AXIS_MAX = 100

# --- fetch-list working set --------------------------------------------------
# The persistent list of owned tank ids we maintain thresholds for is capped at this size
# (also the WG API's tank_id-per-request cap, so the whole list fits one batch fetch).
FETCH_LIST_CAP = 100

# A tank drops out of the fetch list if it hasn't been played within this window (the
# session-open purge). Measured against the vehicle's last-battle timestamp; a freshly bought
# tank is stamped with the purchase time so it survives ~7 days even if never played.
STALE_WINDOW_SECONDS = 7 * 24 * 3600

# Threshold data is served without refetching while now < updated_at + this (the cache-freshness
# fallback TTL). Single source shared by moe_wgapi.fresh_table (cache-adopt gate) and
# fetch_list.needs_refetch (the "don't refetch every session" throttle). This is the time-based
# backstop; a fetch that reveals a changed WG `updated_at` forces a full refetch sooner
# (fetch_list.data_changed + moe_wgapi._poll).
REVALIDATE_SECONDS = 7 * 24 * 3600

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
# (WG panels are Flash -- no runtime position API). Phase 2 adds a separate raised anchor
# (BATTLE_ANCHOR_*_RAISED) used when the damage-log summary block collapses.
BATTLE_ANCHOR_X = 264
BATTLE_ANCHOR_Y = 0

# Phase 2: the RAISED anchor used when the "Summarized damage" group is fully unticked (all four
# DAMAGE_LOG summary flags off -> WG collapses the summary block and the damage-log events shift
# up, so the overlay moves to keep tracking them). Its OWN X + Y (independent of the default
# above, which stays signed-off) -- both fixed logical-px offsets, scale-invariant. Calibrated
# empirically against the collapsed layout (the summary block is Flash-side, no runtime px API).
BATTLE_ANCHOR_X_RAISED = 215
BATTLE_ANCHOR_Y_RAISED = 33
