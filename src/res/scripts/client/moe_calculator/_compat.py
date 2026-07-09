# -*- coding: utf-8 -*-
"""Engine-shim + best-effort guard helpers shared across the adapter/bridge layers.

`debug_utils` is a game symbol: it exists in the running client but not under the
Python 3 test interpreter. Rather than copy-paste the guarded fallback import in
every module, they import `LOG_CURRENT_EXCEPTION` / `LOG_NOTE` from here -- one place
that resolves the real thing in-client and degrades to a no-op out of client (so the
engine-free helper modules still import under pytest).

`_safe` / `_safe_int` are the read-side guard idiom (run a getter, log + fall back to a
default on any failure) lifted here so more than one module can share them.

Adapter/bridge only -- the engine-free `domain/` layer must NOT import this. 2/3-compatible.
"""
try:
    from debug_utils import LOG_CURRENT_EXCEPTION, LOG_NOTE
except Exception:
    def LOG_CURRENT_EXCEPTION():
        pass

    def LOG_NOTE(*args, **kwargs):
        pass


def _safe(fn, default):
    """Call `fn`; return its value, or `default` on None / any exception (logged)."""
    try:
        value = fn()
        return default if value is None else value
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return default


def _safe_int(fn, default):
    """Call `fn` and coerce to int; return `default` on None / any exception (logged).
    The int() runs INSIDE the guard, so a non-coercible return (a string, an object)
    falls back to `default` rather than raising through this fail-soft helper."""
    return _safe(lambda: int(fn()), default)
