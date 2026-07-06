# -*- coding: utf-8 -*-
"""Pure formatting / value helpers for the read-side adapter.

These carry NO game-engine imports so they can be unit-tested on plain inputs
(Python 3, no client). Everything here is best-effort and side-effect-free.
2/3-compatible.
"""

# Mark-art resource sizes shipped by the client (see MarkOnGunAchievement.getIcons).
MARK_ICON_SIZE = "95x85"


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
    """Percentile float -> string like '84.7%'. Clamped display; 0 -> '0%'."""
    try:
        p = float(p or 0.0)
    except (TypeError, ValueError):
        return "0%"
    if p <= 0:
        return "0%"
    if decimals <= 0:
        return "%d%%" % int(round(p))
    return ("%.*f%%" % (decimals, p))


def mark_icon_url(nation, mark_count, size=MARK_ICON_SIZE):
    """Nation MoE art URL for a given mark count (1/2/3), mirroring the client's
    MarkOnGunAchievement.__getIconPath template:
      gui/maps/icons/marksOnGun/<size>/<nation>_<count>_<mark|marks>.png
    Suffix is 'mark' for 1, 'marks' for 2-3. Returns '' when nation is unknown, so
    the widget can fall back to a generic glyph."""
    if not nation:
        return ""
    try:
        count = int(mark_count)
    except (TypeError, ValueError):
        return ""
    if count < 1:
        count = 1
    ctx = "mark" if count < 2 else "marks"
    return "img://gui/maps/icons/marksOnGun/%s/%s_%d_%s.png" % (size, nation, count, ctx)
