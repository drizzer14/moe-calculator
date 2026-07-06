# -*- coding: utf-8 -*-
"""Pure formatting / value helpers for the read-side adapter.

These carry NO game-engine imports so they can be unit-tested on plain inputs
(Python 3, no client). Everything here is best-effort and side-effect-free.
2/3-compatible.
"""

_ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI"]


def roman(n):
    """Tier / level number -> roman numeral, e.g. 8 -> 'VIII'. 0 or out-of-range
    falls back to the decimal string (or '' for non-positive)."""
    n = int(n or 0)
    if 0 < n < len(_ROMAN):
        return _ROMAN[n]
    return str(n) if n > 0 else ""
