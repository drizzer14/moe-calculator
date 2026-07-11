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


def test_percent_exact_half_rounds_half_away():
    # An exact .5 at decimals=0 must round half-AWAY-from-zero (what the py2.7 client does),
    # NOT half-to-even (what py3's built-in round() would do -> "84%"). Regression guard for
    # the py2/py3 rounding divergence.
    assert fmt.percent(84.5, decimals=0) == "85%"
    assert fmt.percent(85.5, decimals=0) == "86%"  # py3 round(85.5) == 86 too; half-away here


def test_signed_percent_exact_half_rounds_half_away():
    # signed_percent(0.5, decimals=0): half-away -> "+1%" (py3 round(0.5)==0 -> would be "0%").
    assert fmt.signed_percent(0.5, decimals=0) == "+1%"
    assert fmt.signed_percent(-0.5, decimals=0) == "-1%"
    assert fmt.signed_percent(2.5, decimals=0) == "+3%"  # py3 round(2.5)==2 -> the divergence
