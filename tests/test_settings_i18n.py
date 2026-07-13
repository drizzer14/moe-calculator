# -*- coding: utf-8 -*-
"""Unit tests for the settings-panel translation resolver (engine-free).

settings_i18n is pure except client_language(); it imports cleanly under pytest
because _compat guards the game's debug_utils. The single engine read is exercised
by faking a `helpers` module in sys.modules. Mirrors the sibling Garage Progress Bar
mod's test_settings_i18n."""
import sys
import types

from moe_calculator.adapter import settings_i18n as S
from moe_calculator.adapter import i18n

# The full key set every language block must cover (== the English master's keys).
_KEYS = set(S._PANEL[u"en"].keys())
# Every non-English language we ship a block for.
_SHIPPED = [c for c in S._PANEL if c != u"en"]


# --- resolve ---------------------------------------------------------------

def test_resolve_en_has_all_keys_shaped():
    r = S.resolve(u"en")
    assert set(r.keys()) == _KEYS
    for entry in r.values():
        assert u"label" in entry
    # Both current rows carry a header+body tooltip.
    assert u"ttHeader" in r[u"garageWidget"] and u"ttBody" in r[u"garageWidget"]
    assert u"ttHeader" in r[u"battleWidget"] and u"ttBody" in r[u"battleWidget"]


def test_resolve_de_differs_from_english():
    en = S.resolve(u"en")
    de = S.resolve(u"de")
    assert set(de.keys()) == _KEYS
    assert de[u"garageWidget"][u"label"] != en[u"garageWidget"][u"label"]
    assert de[u"garageWidget"][u"label"] == u"Garage-Widget aktiviert"


def test_resolve_unknown_is_full_english():
    assert S.resolve(u"xx") == S.resolve(u"en")
    assert S.resolve(u"") == S.resolve(u"en")
    assert S.resolve(None) == S.resolve(u"en")


def test_resolve_per_key_fallback(monkeypatch):
    # A synthetic language that translated ONLY one key falls back to English for the
    # rest -- proving fallback is per key, not per language.
    partial = {u"garageWidget": S._row(u"ZZ", u"ZZ", u"zz")}
    monkeypatch.setitem(S._PANEL, u"zz", partial)
    r = S.resolve(u"zz")
    assert r[u"garageWidget"][u"label"] == u"ZZ"
    assert r[u"battleWidget"] == S._PANEL[u"en"][u"battleWidget"]  # English fallback


def test_every_shipped_language_covers_all_keys():
    for code in _SHIPPED:
        assert set(S._PANEL[code].keys()) == _KEYS, (
            u"language %s is missing keys: %s" % (code, _KEYS - set(S._PANEL[code])))


# --- battleAltKey (the "show only while Alt held" peek setting) --------------

def test_battle_alt_key_present_in_master_and_col1():
    assert u"battleAltKey" in S._PANEL[u"en"]
    assert u"battleAltKey" in S.COL1_KEYS
    en = S.resolve(u"en")
    assert en[u"battleAltKey"][u"label"] == u"Battle Widget on Alt Key"
    assert u"ttHeader" in en[u"battleAltKey"] and u"ttBody" in en[u"battleAltKey"]


def test_battle_alt_key_keeps_alt_literal_in_every_language():
    # "Alt" is a keyboard key -- it must NOT be translated in any shipped language. Assert the
    # literal token appears in the label, header and body of every block.
    for code in S._PANEL:
        entry = S._PANEL[code][u"battleAltKey"]
        assert u"Alt" in entry[u"label"], u"%s label lost 'Alt'" % code
        assert u"Alt" in entry[u"ttHeader"], u"%s header lost 'Alt'" % code
        assert u"Alt" in entry[u"ttBody"], u"%s body lost 'Alt'" % code


def test_battle_alt_key_ukrainian_translated():
    uk = S.resolve(u"uk")
    assert uk[u"battleAltKey"][u"label"] == u"Віджет у бою по клавіші Alt"


# --- _norm -----------------------------------------------------------------

def test_norm_cases():
    assert S._norm(u"en") == u"en"
    assert S._norm(u"EN") == u"en"
    assert S._norm(u"en-US") == u"en"       # region suffix -> primary subtag
    assert S._norm(u"pt_BR") == u"pt"       # unknown full -> primary subtag
    assert S._norm(u"ua") == u"uk"          # alias
    assert S._norm(u"UA") == u"uk"          # alias, case-insensitive
    assert S._norm(None) == u""
    assert S._norm(u"") == u""


# --- markup + rendering ----------------------------------------------------

def test_render_assembles_tooltip_markup():
    out = S._render({u"label": u"L", u"ttHeader": u"H", u"ttBody": u"B"})
    assert out[u"text"] == u"L"
    assert out[u"tooltip"] == u"{HEADER}H{/HEADER}{BODY}B{/BODY}"


def test_render_label_only_has_no_tooltip():
    out = S._render({u"label": u"L"})
    assert out == {u"text": u"L"}
    assert u"tooltip" not in out


# --- marking ---------------------------------------------------------------

def test_build_marks_only_fallback_keys(monkeypatch):
    partial = {u"garageWidget": S._row(u"ZZ", u"ZZ", u"zz")}
    monkeypatch.setitem(S._PANEL, u"zz", partial)
    monkeypatch.setattr(i18n, u"MARK_UNTRANSLATED", True)
    b = S.build(u"zz")
    # Translated key: no underscore marker.
    assert not b[u"garageWidget"][u"text"].startswith(u"_")
    # Fallback key: underscore-marked text and tooltip.
    assert b[u"battleWidget"][u"text"].startswith(u"_")
    assert b[u"battleWidget"][u"tooltip"].startswith(u"_")


def test_build_en_client_never_marks(monkeypatch):
    monkeypatch.setattr(i18n, u"MARK_UNTRANSLATED", True)
    b = S.build(u"en")
    for entry in b.values():
        assert not entry[u"text"].startswith(u"_")


# --- client_language guard -------------------------------------------------

def test_client_language_reads_helpers(monkeypatch):
    fake = types.ModuleType(u"helpers")
    fake.getClientLanguage = lambda: u"de"
    monkeypatch.setitem(sys.modules, u"helpers", fake)
    assert S.client_language() == u"de"


def test_client_language_normalizes_alias(monkeypatch):
    fake = types.ModuleType(u"helpers")
    fake.getClientLanguage = lambda: u"ua"
    monkeypatch.setitem(sys.modules, u"helpers", fake)
    assert S.client_language() == u"uk"


def test_client_language_falls_back_to_english_on_error(monkeypatch):
    fake = types.ModuleType(u"helpers")

    def _boom():
        raise RuntimeError(u"no client")

    fake.getClientLanguage = _boom
    monkeypatch.setitem(sys.modules, u"helpers", fake)
    assert S.client_language() == u"en"


def test_panel_text_uses_client_language(monkeypatch):
    fake = types.ModuleType(u"helpers")
    fake.getClientLanguage = lambda: u"de"
    monkeypatch.setitem(sys.modules, u"helpers", fake)
    t = S.panel_text()
    assert t[u"garageWidget"][u"text"] == u"Garage-Widget aktiviert"
