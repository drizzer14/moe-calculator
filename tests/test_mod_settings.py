# -*- coding: utf-8 -*-
"""Tests for the settings module's pure merge logic. merge_settings is the only piece that
must be correct without the game: it turns whatever ModsSettingsAPI hands back (or nothing)
into the two booleans the bridges read. The MSA registration/glue is not unit-tested (it
needs the client)."""
from moe_calculator.bridge.mod_settings import (
    merge_settings, DEFAULTS, GARAGE_KEY, BATTLE_KEY)


def test_defaults_when_empty_or_none():
    # No saved store (fresh install / MSA absent) -> both widgets enabled.
    assert merge_settings(None) == DEFAULTS
    assert merge_settings({}) == DEFAULTS
    assert DEFAULTS == {GARAGE_KEY: True, BATTLE_KEY: True}


def test_overlays_known_keys():
    out = merge_settings({GARAGE_KEY: False, BATTLE_KEY: True})
    assert out == {GARAGE_KEY: False, BATTLE_KEY: True}
    out2 = merge_settings({GARAGE_KEY: True, BATTLE_KEY: False})
    assert out2 == {GARAGE_KEY: True, BATTLE_KEY: False}


def test_partial_dict_fills_missing_with_defaults():
    # Only one key present -> the other falls back to its default (True).
    out = merge_settings({GARAGE_KEY: False})
    assert out == {GARAGE_KEY: False, BATTLE_KEY: True}


def test_unknown_keys_ignored():
    out = merge_settings({GARAGE_KEY: False, "bogus": 123, "settingsVersion": 9})
    assert out == {GARAGE_KEY: False, BATTLE_KEY: True}
    assert "bogus" not in out


def test_values_coerced_to_bool():
    out = merge_settings({GARAGE_KEY: 0, BATTLE_KEY: 1})
    assert out[GARAGE_KEY] is False
    assert out[BATTLE_KEY] is True


def test_non_dict_input_degrades_to_defaults():
    assert merge_settings("nonsense") == DEFAULTS
    assert merge_settings(42) == DEFAULTS
    assert merge_settings([GARAGE_KEY]) == DEFAULTS


def test_returns_fresh_dict_not_defaults_alias():
    # Must not hand back a reference to DEFAULTS (a caller mutating it would corrupt the base).
    out = merge_settings({})
    out[GARAGE_KEY] = False
    assert DEFAULTS[GARAGE_KEY] is True
