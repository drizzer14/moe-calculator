# -*- coding: utf-8 -*-
"""Engine-shim + best-effort guard helpers shared across the adapter/bridge layers.

`debug_utils` is a game symbol: it exists in the running client but not under the
Python 3 test interpreter. Rather than copy-paste the guarded fallback import in
every module, they import `LOG_CURRENT_EXCEPTION` / `LOG_DEBUG` from here -- one place
that resolves the real thing in-client and degrades to a no-op out of client (so the
engine-free helper modules still import under pytest). `LOG_DEBUG` additionally gates all
verbose diagnostics behind the `DEBUG` release switch so a shipped build stays silent.

`_safe` / `_safe_int` are the read-side guard idiom (run a getter, log + fall back to a
default on any failure) lifted here so more than one module can share them.

Adapter/bridge only -- the engine-free `domain/` layer must NOT import this. 2/3-compatible.
"""
# RELEASE SWITCH. Verbose diagnostics (lifecycle, placement, data payloads) go through
# LOG_DEBUG, which writes to WoT's python.log ONLY when this is True. A shipped build MUST
# leave it False so the release stays quiet -- unconditional notes have no place in a player's
# log. Flip to True ONLY for local dev and NEVER commit it True (tests/test_logging_gate.py
# fails the build if you do). Genuine errors are reported separately through the always-on,
# path-safe LOG_CURRENT_EXCEPTION.
DEBUG = False

try:
    from debug_utils import LOG_CURRENT_EXCEPTION, LOG_NOTE
except Exception:
    def LOG_CURRENT_EXCEPTION():
        pass

    def LOG_NOTE(*args, **kwargs):
        pass


def LOG_DEBUG(*args, **kwargs):
    """Gated verbose note: forwards to LOG_NOTE only when DEBUG is True, else a no-op.

    Use this for ANYTHING informational or internal (payloads, lists, lifecycle, placement) so
    the release build stays silent. Reserve LOG_CURRENT_EXCEPTION for real failures. Read DEBUG
    off the module at call time (not captured) so tests can toggle it via monkeypatch."""
    if DEBUG:
        LOG_NOTE(*args, **kwargs)


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
