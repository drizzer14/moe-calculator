# -*- coding: utf-8 -*-
"""Pure formatting / value helpers for the read-side adapter.

These carry NO game-engine imports so they can be unit-tested on plain inputs
(Python 3, no client). Everything here is best-effort and side-effect-free.
2/3-compatible.
"""
from moe_calculator.domain.rounding import round_half_away, iround_half_away


def thousands(n):
    """Integer -> grouped string, e.g. 2910 -> '2,910'. Non-positive -> '0'."""
    try:
        n = int(n or 0)
    except (TypeError, ValueError):
        return "0"
    if n <= 0:
        return "0"
    # Manual grouping (locale-free, 2/3-safe).
    s = str(n)
    out = []
    while len(s) > 3:
        out.insert(0, s[-3:])
        s = s[:-3]
    out.insert(0, s)
    return ",".join(out)


def percent(p, decimals=1):
    """Percentile float -> string like '84.7%'; <=0 -> '0%'. No upper clamp -- percent(140.0)
    yields '140.0%'; callers pre-clamp to 0..100 when a bounded display is required."""
    try:
        p = float(p or 0.0)
    except (TypeError, ValueError):
        return "0%"
    if p <= 0:
        return "0%"
    if decimals <= 0:
        return "%d%%" % iround_half_away(p)
    return ("%.*f%%" % (decimals, p))


def signed_percent(p, decimals=1):
    """Signed percentile delta -> '+0.4%' / '-1.2%'; zero AT DISPLAY PRECISION -> '0%'.
    Used for the in-battle 'how much this battle moves your standing' readout. A tiny delta
    that rounds to 0 at `decimals` (e.g. -0.04 at 1 dp) reads '0%' with no misleading sign
    rather than '-0.0%'."""
    try:
        p = float(p or 0.0)
    except (TypeError, ValueError):
        return "0%"
    if round_half_away(p, decimals if decimals > 0 else 0) == 0:
        return "0%"
    sign = "+" if p > 0 else "-"
    mag = abs(p)
    if decimals <= 0:
        return "%s%d%%" % (sign, iround_half_away(mag))
    return "%s%.*f%%" % (sign, decimals, mag)
