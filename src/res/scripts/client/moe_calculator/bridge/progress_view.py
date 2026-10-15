# -*- coding: utf-8 -*-
"""The centre-screen transient MoE progress bar (the "Moving Average" variant) as its own
OpenWG-registered Gameface window.

A thin instantiation of bridge/bar_window.BarHost -- read that module for the whole hosting model
(why a registered window, why WindowLayer.WINDOW, why NOT WINDOW_FULLSCREEN, why the surface size is
a JS push, why each bar needs its OWN singleton and layout). The bar-specific facts are the
five arguments below and nothing else. The module-level functions stay module-level because
battle_bridge (and its tests) treat this module AS the window handle.

PC-only (needs the live client); not imported under pytest without stubs. Python 2.7 runtime.
"""
from moe_calculator.bridge import mod_settings
from moe_calculator.bridge.bar_window import BarHost
from moe_calculator.bridge.view_models import ProgressVM
from moe_calculator.domain.constants import (
    PROGRESS_ANCHOR_X_OFFSET, PROGRESS_ANCHOR_Y_FRAC,
    PROGRESS_ANCHOR_Y_SHIFT, PROGRESS_ANCHOR_Y_SHIFT_LARGE, PROGRESS_MM_GAP,
    PROGRESS_MM_GAP_LARGE, PROGRESS_MM_GAP_BOTTOM, PROGRESS_MM_TRACK_X,
    PROGRESS_MM_TRACK_X_LARGE)

# View name declared in res/gui/gen_resources/com.14th_ua.moe_calculator.json -- keep in lockstep.
RES_MAP_ITEM_ID = "MoEProgressView"

_host = BarHost(RES_MAP_ITEM_ID, ProgressVM,
                PROGRESS_ANCHOR_Y_FRAC, PROGRESS_ANCHOR_X_OFFSET, PROGRESS_ANCHOR_Y_SHIFT,
                PROGRESS_ANCHOR_Y_SHIFT_LARGE, PROGRESS_MM_TRACK_X, PROGRESS_MM_TRACK_X_LARGE,
                PROGRESS_MM_GAP_BOTTOM, "[moe-bar]", mm_gap=PROGRESS_MM_GAP,
                mm_gap_large=PROGRESS_MM_GAP_LARGE,
                variant=mod_settings.PROGRESS_VARIANT_MOVING_AVERAGE)

open_window = _host.open_window
close_window = _host.close_window
active_view = _host.active_view
apply_position = _host.apply_position
drag = _host.drag
has_placed = _host.has_placed
ensure_placed = _host.ensure_placed
