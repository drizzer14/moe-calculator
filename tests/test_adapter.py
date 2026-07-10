# -*- coding: utf-8 -*-
"""Tests for the engine-free parts of the adapter layer: pure formatting and the
MoE-table HTML parser. These import no game symbols (moe_tomato imports BigWorld/
helpers.http lazily inside the fetch functions), so they run on plain Python 3."""
from moe_calculator.adapter import format as fmt
from moe_calculator.adapter import moe_tomato


# --- format ------------------------------------------------------------------

def test_thousands():
    assert fmt.thousands(2910) == "2,910"
    assert fmt.thousands(709) == "709"
    assert fmt.thousands(1234567) == "1,234,567"
    assert fmt.thousands(0) == "0"
    assert fmt.thousands(None) == "0"
    assert fmt.thousands(-5) == "0"


def test_percent():
    assert fmt.percent(84.7) == "84.7%"
    assert fmt.percent(84.72, decimals=1) == "84.7%"
    assert fmt.percent(90, decimals=0) == "90%"
    assert fmt.percent(0) == "0%"
    assert fmt.percent(None) == "0%"


def test_signed_percent():
    assert fmt.signed_percent(0.4) == "+0.4%"
    assert fmt.signed_percent(-1.2) == "-1.2%"
    assert fmt.signed_percent(0) == "0%"
    assert fmt.signed_percent(None) == "0%"
    assert fmt.signed_percent(2.0, decimals=0) == "+2%"
    assert fmt.signed_percent(-2.0, decimals=0) == "-2%"


def test_signed_percent_sub_precision_reads_zero():
    # A delta that rounds to 0 at the display precision must read "0%" (no misleading
    # "-0.0%" / "+0.0%" sign) -- the signed-zero fix.
    assert fmt.signed_percent(-0.04, decimals=1) == "0%"
    assert fmt.signed_percent(0.04, decimals=1) == "0%"
    assert fmt.signed_percent(0.004, decimals=2) == "0%"
    assert fmt.signed_percent(0.4, decimals=0) == "0%"
    # Just past the rounding boundary still shows a sign.
    assert fmt.signed_percent(0.06, decimals=1) == "+0.1%"


def test_mark_icon_url():
    assert fmt.mark_icon_url("germany", 1) == \
        "img://gui/maps/icons/marksOnGun/95x85/germany_1_mark.png"
    assert fmt.mark_icon_url("germany", 2) == \
        "img://gui/maps/icons/marksOnGun/95x85/germany_2_marks.png"
    assert fmt.mark_icon_url("ussr", 3) == \
        "img://gui/maps/icons/marksOnGun/95x85/ussr_3_marks.png"
    # unknown nation -> empty (widget falls back to a generic glyph)
    assert fmt.mark_icon_url("", 2) == ""


# --- moe_tomato.parse_table --------------------------------------------------

_SAMPLE = (
    'noise...{"65":709,"85":1065,"95":1363,"100":1580,"id":1,"7diff65":3}'
    ',{"65":1291,"85":1858,"95":2287,"100":2641,"id":1073,"foo":9}'
    ',{"65":2518,"85":3508,"95":4290,"100":4935,"id":6017}...tail'
)


def test_parse_table_extracts_records():
    table = moe_tomato.parse_table(_SAMPLE)
    assert table[1] == {1: 709, 2: 1065, 3: 1363, 100: 1580}
    assert table[1073] == {1: 1291, 2: 1858, 3: 2287, 100: 2641}
    assert table[6017] == {1: 2518, 2: 3508, 3: 4290, 100: 4935}
    assert len(table) == 3


def test_parse_table_empty_and_garbage():
    assert moe_tomato.parse_table("") == {}
    assert moe_tomato.parse_table(None) == {}
    assert moe_tomato.parse_table("no records here") == {}


def test_get_thresholds_missing_is_empty(monkeypatch):
    # get_thresholds triggers start(); stub it out so no network/BigWorld is touched.
    monkeypatch.setattr(moe_tomato, "start", lambda: None)
    monkeypatch.setattr(moe_tomato, "_loaded", True, raising=False)
    assert moe_tomato.get_thresholds(999999) == {}
    assert moe_tomato.get_thresholds(None) == {}
