# -*- coding: utf-8 -*-
"""MoE-threshold source facade.

The rest of the mod imports `from moe_calculator.adapter import moe_data` and calls
get_thresholds / start / add_ready_listener / is_loaded. This module keeps that surface stable
while delegating to the sole provider, `moe_wgapi` (the official Wargaming API). It used to
route between a tomato.gg scrape and an offline estimator; both were retired in favor of the
authoritative WG-API distribution, so this is now a thin pass-through kept as the stable
import seam (so a future source swap touches one file, not every caller).
"""
from moe_calculator.adapter import moe_wgapi


def get_thresholds(int_cd):
    return moe_wgapi.get_thresholds(int_cd)


def start():
    return moe_wgapi.start()


def add_ready_listener(cb):
    return moe_wgapi.add_ready_listener(cb)


def is_loaded():
    return moe_wgapi.is_loaded()


def needs_estimate(int_cd):
    """True when the WG request for this tank completed without data (errored / no data), so the
    caller should fall back to the offline estimator rather than wait for a pending fetch."""
    return moe_wgapi.needs_estimate(int_cd)
