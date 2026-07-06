# -*- coding: utf-8 -*-
"""Parse the arguments a Gameface/Wulf command invocation carries.

Engine-free and unit-testable (Wulf delivers a single MAP argument per command; the
JS side wraps a scalar as {value: id}). A plain dict, a Wulf-wrapped map (any object
with a .get(key)), or a bare scalar are all tolerated. Best-effort and
side-effect-free. 2/3-compatible.
"""
from moe_calculator._compat import LOG_CURRENT_EXCEPTION


def map_get(a, key):
    """Read `key` from a JS-supplied argument that may be a plain dict or a Wulf-wrapped
    map. Returns None if unreadable."""
    if isinstance(a, dict):
        return a.get(key)
    getter = getattr(a, "get", None)
    if callable(getter):
        try:
            return a.get(key)
        except Exception:
            return None
    return None


def cmd_int_arg(args):
    """Extract the int id a JS command invocation carried. Wulf delivers a single MAP
    argument (the JS side wraps the id as {value: id}); pull our key out of it,
    tolerating a plain dict, a wrapped map, or a bare scalar. 0 = nothing usable."""
    try:
        if not args:
            return 0
        a = args[0]
        if isinstance(a, dict):
            a = a.get("value", a.get("id"))
        else:
            getter = getattr(a, "get", None)
            if callable(getter):
                try:
                    a = a.get("value")
                except Exception:
                    pass
        try:
            return int(a)
        except (TypeError, ValueError):
            return 0
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return 0


def cmd_xy_arg(args):
    """Extract the (x, y) pixel pair a JS `setPosition` invocation carried. Wulf
    delivers a single MAP argument ({x, y}); pull both keys, tolerating a plain dict or
    a wrapped map. Missing/invalid -> 0 (auto)."""
    def as_int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0
    try:
        if not args:
            return 0, 0
        a = args[0]
        return as_int(map_get(a, "x")), as_int(map_get(a, "y"))
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return 0, 0
