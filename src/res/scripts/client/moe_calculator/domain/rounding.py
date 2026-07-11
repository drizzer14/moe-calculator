# -*- coding: utf-8 -*-
"""Interpreter-independent rounding. Pure, engine-free, 2/3-compatible.

The mod RUNS on Python 2.7.18 (the game client) but its unit tests run on Python 3.13.
The built-in `round()` disagrees between them at an exact `.5` boundary:

  - Python 2.7 rounds half **away from zero**  (round(84.5) -> 85.0, round(-0.5) -> -1.0)
  - Python 3   rounds half **to even** (banker's)  (round(84.5) -> 84,  round(-0.5) ->  0)

So a value landing exactly on `.5` ships one unit different from what the py3 test asserts --
the suite would then NOT verify the in-game display at those points. `round_half_away` fixes
the tie-break rule to half-away-from-zero on BOTH interpreters, matching the py2.7 client, so
the tests pin exactly what the game shows. Use it everywhere a displayed / threshold integer
(or fixed-decimal) value is produced.
"""
import math


def round_half_away(x, ndigits=0):
    """Round `x` to `ndigits` decimals, breaking exact halves AWAY from zero -- matching
    CPython 2.7's built-in round() and independent of the running interpreter. NaN passes
    through unchanged (callers clamp/guard NaN separately)."""
    x = float(x)
    if x != x:  # NaN
        return x
    factor = 10.0 ** ndigits
    scaled = x * factor
    if scaled >= 0.0:
        r = math.floor(scaled + 0.5)
    else:
        r = math.ceil(scaled - 0.5)
    return r / factor


def iround_half_away(x):
    """`round_half_away(x)` as an int -- the common `int(round(x))` idiom, deterministic."""
    return int(round_half_away(x))
