# -*- coding: utf-8 -*-
"""MoE-threshold source ROUTER.

The rest of the mod imports `from moe_calculator.adapter import moe_data` and calls
get_thresholds / start / add_ready_listener / is_loaded / record_sample. This module keeps that
surface stable while delegating to whichever provider the build selected
(build_config.MOE_DATA_SOURCE):

  - "tomato"  -> moe_tomato  : fetch the crowd-sourced table from tomato.gg (GitHub release).
  - "offline" -> moe_offline : estimate thresholds from the client's own dossier samples, no
                               external API (WGMods release).

The active provider is resolved per call (the constant is static at runtime; resolving per call
also lets tests flip MOE_DATA_SOURCE). Both providers expose the same surface -- the tomato one
supplies an inert record_sample() so the router never needs to branch per method.
"""
from moe_calculator import build_config
from moe_calculator.adapter import moe_tomato
from moe_calculator.adapter import moe_offline


def _provider():
    if build_config.MOE_DATA_SOURCE == "offline":
        return moe_offline
    return moe_tomato


def get_thresholds(int_cd):
    return _provider().get_thresholds(int_cd)


def start():
    return _provider().start()


def add_ready_listener(cb):
    return _provider().add_ready_listener(cb)


def is_loaded():
    return _provider().is_loaded()


def record_sample(int_cd, percentile, avg_damage):
    """Record a per-player (avg_damage, percentile) sample for a tank (offline provider). A
    no-op under the tomato provider -- the caller records unconditionally on every garage read."""
    return _provider().record_sample(int_cd, percentile, avg_damage)
