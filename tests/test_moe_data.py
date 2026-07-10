# -*- coding: utf-8 -*-
"""Tests for adapter/moe_data: the thin facade over the sole provider (moe_wgapi). It just
delegates the surface (get_thresholds / start / add_ready_listener / is_loaded), so we assert
each call reaches moe_wgapi. (The provider's own logic lives in tests/test_moe_wgapi.py.)"""
from moe_calculator.adapter import moe_data


def test_get_thresholds_delegates(monkeypatch):
    calls = []
    monkeypatch.setattr(moe_data.moe_wgapi, "get_thresholds",
                        lambda cd: calls.append(("get_thresholds", cd)) or {1: 1, 2: 2, 3: 3, 100: 4})
    assert moe_data.get_thresholds(1073) == {1: 1, 2: 2, 3: 3, 100: 4}
    assert ("get_thresholds", 1073) in calls


def test_start_delegates(monkeypatch):
    calls = []
    monkeypatch.setattr(moe_data.moe_wgapi, "start", lambda: calls.append("start"))
    moe_data.start()
    assert calls == ["start"]


def test_add_ready_listener_delegates(monkeypatch):
    seen = []
    monkeypatch.setattr(moe_data.moe_wgapi, "add_ready_listener", lambda cb: seen.append(cb))
    cb = lambda: None
    moe_data.add_ready_listener(cb)
    assert seen == [cb]


def test_is_loaded_delegates(monkeypatch):
    monkeypatch.setattr(moe_data.moe_wgapi, "is_loaded", lambda: True)
    assert moe_data.is_loaded() is True


def test_needs_estimate_delegates(monkeypatch):
    monkeypatch.setattr(moe_data.moe_wgapi, "needs_estimate", lambda cd: cd == 42)
    assert moe_data.needs_estimate(42) is True
    assert moe_data.needs_estimate(7) is False
