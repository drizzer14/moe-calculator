# -*- coding: utf-8 -*-
"""Tests for the engine-free parts of the adapter layer: pure formatting. These import no
game symbols, so they run on plain Python 3. (The WG-API parser lives in test_moe_wgapi.py.)"""
from moe_calculator.adapter import format as fmt


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
