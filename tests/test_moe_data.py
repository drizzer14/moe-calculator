# -*- coding: utf-8 -*-
"""Tests for adapter/moe_data: the source ROUTER. It selects a provider by
build_config.MOE_DATA_SOURCE and delegates the whole surface. We flip the constant and assert
delegation to a fake provider, plus the real per-provider is_estimated()/record_sample()
behaviour. (The tomato state-machine tests now live in tests/test_moe_tomato.py.)"""
from moe_calculator import build_config
from moe_calculator.adapter import moe_data


class _FakeProvider(object):
    def __init__(self):
        self.calls = []

    def get_thresholds(self, int_cd):
        self.calls.append(("get_thresholds", int_cd))
        return {1: 1, 2: 2, 3: 3, 100: 4}

    def start(self):
        self.calls.append(("start",))

    def add_ready_listener(self, cb):
        self.calls.append(("add_ready_listener",))
        cb()

    def is_loaded(self):
        self.calls.append(("is_loaded",))
        return True

    def record_sample(self, int_cd, percentile, avg_damage):
        self.calls.append(("record_sample", int_cd, percentile, avg_damage))


def test_routes_to_offline_when_configured(monkeypatch):
    monkeypatch.setattr(build_config, "MOE_DATA_SOURCE", "offline")
    fake = _FakeProvider()
    monkeypatch.setattr(moe_data, "moe_offline", fake)
    assert moe_data._provider() is fake
    assert moe_data.get_thresholds(1073) == {1: 1, 2: 2, 3: 3, 100: 4}
    moe_data.start()
    moe_data.record_sample(1073, 80.0, 1500)
    assert ("get_thresholds", 1073) in fake.calls
    assert ("record_sample", 1073, 80.0, 1500) in fake.calls
    assert ("start",) in fake.calls


def test_routes_to_tomato_by_default(monkeypatch):
    monkeypatch.setattr(build_config, "MOE_DATA_SOURCE", "tomato")
    fake = _FakeProvider()
    monkeypatch.setattr(moe_data, "moe_tomato", fake)
    assert moe_data._provider() is fake
    moe_data.get_thresholds(1073)
    assert ("get_thresholds", 1073) in fake.calls


def test_unknown_source_falls_back_to_tomato(monkeypatch):
    # Any value other than "offline" resolves to the tomato provider (fail-safe default).
    monkeypatch.setattr(build_config, "MOE_DATA_SOURCE", "banana")
    from moe_calculator.adapter import moe_tomato
    assert moe_data._provider() is moe_tomato


def test_default_constant_is_tomato():
    # The in-repo default (before any build-time override) must be the GitHub/dev source.
    assert build_config.MOE_DATA_SOURCE == "tomato"
