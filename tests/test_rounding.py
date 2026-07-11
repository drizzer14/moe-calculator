# -*- coding: utf-8 -*-
"""Unit tests for the interpreter-independent rounding helper (domain/rounding).

These pin the half-AWAY-from-zero tie-break that matches the Python 2.7 game client, so the
py3 suite verifies exactly what ships (py3's built-in round() would break these ties to even)."""
import math

from moe_calculator.domain import rounding as r


def test_round_half_away_integer_halves():
    # Exact .5 boundaries round AWAY from zero (py2), not to even (py3 built-in).
    assert r.round_half_away(0.5) == 1.0
    assert r.round_half_away(1.5) == 2.0
    assert r.round_half_away(2.5) == 3.0        # py3 round(2.5) == 2 -- the divergence
    assert r.round_half_away(84.5) == 85.0
    assert r.round_half_away(-0.5) == -1.0
    assert r.round_half_away(-2.5) == -3.0


def test_round_half_away_non_halves_unchanged():
    assert r.round_half_away(84.4) == 84.0
    assert r.round_half_away(84.6) == 85.0
    assert r.round_half_away(-84.6) == -85.0
    assert r.round_half_away(0.0) == 0.0


def test_round_half_away_decimals():
    assert r.round_half_away(0.05, 1) == 0.1
    assert r.round_half_away(-0.05, 1) == -0.1


def test_round_half_away_nan_passthrough():
    assert math.isnan(r.round_half_away(float("nan")))


def test_iround_half_away_returns_int():
    v = r.iround_half_away(2.5)
    assert v == 3 and isinstance(v, int)
    assert r.iround_half_away(-2.5) == -3
