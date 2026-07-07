# -*- coding: utf-8 -*-
"""Tests for the tooltip label resolver. Runs on plain Python 3 (no game engine), so
labels() exercises the degraded path we care about: WG keys unresolved -> English
fallback, unknown language -> English, missing key -> ''."""
from moe_calculator.adapter import i18n


def teardown_function(_):
    i18n.reset_cache()


def test_labels_fall_back_to_english_without_engine():
    lab = i18n.labels()
    assert lab["title"] == "Marks of Excellence"
    assert lab["avgDamage"] == "Average Damage"
    assert lab["marks"] == "Marks"
    assert lab["toNextMark"] == "To next mark"
    assert lab["goal"] == "Goal"
    # every declared key is present and non-empty (the JS reads them by name)
    for key in list(i18n._WG_KEYS) + list(i18n._BUNDLED):
        assert lab.get(key)


def test_labels_are_cached():
    first = i18n.labels()
    assert i18n.labels() is first
    i18n.reset_cache()
    assert i18n.labels() is not first


def test_client_language_defaults_out_of_client():
    assert i18n._client_language() == "en"


def test_bundled_known_language_differs_from_english():
    ru = i18n._bundled("toNextMark", "ru")
    assert ru and ru != "To next mark"


def test_bundled_unknown_language_falls_back_to_en():
    assert i18n._bundled("toNextMark", "zz") == "To next mark"


def test_bundled_missing_key_is_empty():
    assert i18n._bundled("nope", "en") == ""


def _with_fake_makestring(monkeypatch, fn):
    """Inject a fake `helpers.i18n.makeString` so _wg_text's live path is exercisable."""
    import sys, types
    helpers = types.ModuleType("helpers")
    helpers_i18n = types.ModuleType("helpers.i18n")
    helpers_i18n.makeString = fn
    helpers.i18n = helpers_i18n
    monkeypatch.setitem(sys.modules, "helpers", helpers)
    monkeypatch.setitem(sys.modules, "helpers.i18n", helpers_i18n)


def test_wg_text_returns_real_translation(monkeypatch):
    _with_fake_makestring(monkeypatch, lambda k: "Average Damage")
    assert i18n._wg_text("#menu:tank_params/avgDamage") == "Average Damage"


def test_wg_text_treats_tail_echo_as_miss(monkeypatch):
    # The live client echoes the key TAIL on a miss; that must NOT be accepted as text.
    _with_fake_makestring(monkeypatch, lambda k: k.split(":", 1)[1])
    assert i18n._wg_text("#achievements:marksOnGunHeader") is None


def test_wg_text_treats_hash_echo_as_miss(monkeypatch):
    _with_fake_makestring(monkeypatch, lambda k: k)
    assert i18n._wg_text("#achievements:whatever") is None
