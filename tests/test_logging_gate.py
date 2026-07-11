# -*- coding: utf-8 -*-
"""Guards that a RELEASE build stays quiet.

The contract:
  * All chatty/internal diagnostics go through `_compat.LOG_DEBUG`, which is gated on `DEBUG`.
  * `DEBUG` ships False. Flip it True ONLY for local dev; never commit it True.
  * Genuine errors still go through the unconditional, path-safe `LOG_CURRENT_EXCEPTION`.

These tests fail loudly if anyone re-introduces a raw `LOG_NOTE(...)` call site (unconditional
logging into a player's python.log) or commits `DEBUG = True`.
"""
import os
import re

from moe_calculator import _compat


# The whole shipped client tree (both the gui/mods entry point and the moe_calculator package).
_CLIENT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "src", "res", "scripts", "client"))

# _compat.py is the ONE place allowed to name LOG_NOTE: it defines the in-client/no-op fallback
# and LOG_DEBUG forwards to it. Everything else must call LOG_DEBUG (gated) instead.
_ALLOWED = {os.path.join(_CLIENT, "moe_calculator", "_compat.py")}

_LOG_NOTE_CALL = re.compile(r"\bLOG_NOTE\s*\(")
_LOG_NOTE_IMPORT = re.compile(r"\bimport\b.*\bLOG_NOTE\b")


def _py_files():
    for dirpath, dirs, files in os.walk(_CLIENT):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in files:
            if name.endswith(".py"):
                yield os.path.join(dirpath, name)


def test_debug_flag_ships_false():
    """A release must never carry DEBUG=True -- that is exactly what leaked in 0.2.2."""
    assert _compat.DEBUG is False, "DEBUG must be False in committed source (flip only for local dev)"


def test_no_raw_log_note_call_sites():
    """No module outside _compat may call LOG_NOTE directly -- verbose logging must be gated
    through LOG_DEBUG so a release build is silent by default."""
    offenders = []
    for path in _py_files():
        if path in _ALLOWED:
            continue
        with open(path, "rb") as fh:
            text = fh.read().decode("utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            if _LOG_NOTE_CALL.search(line) or _LOG_NOTE_IMPORT.search(line):
                rel = os.path.relpath(path, _CLIENT).replace(os.sep, "/")
                offenders.append("%s:%d: %s" % (rel, lineno, line.strip()))
    assert not offenders, (
        "raw LOG_NOTE usage found -- route verbose logging through the gated LOG_DEBUG:\n  "
        + "\n  ".join(offenders))


def test_log_debug_is_gated(monkeypatch):
    """LOG_DEBUG forwards to LOG_NOTE only when DEBUG is True; otherwise it is a no-op."""
    calls = []
    monkeypatch.setattr(_compat, "LOG_NOTE", lambda *a, **k: calls.append(a))

    monkeypatch.setattr(_compat, "DEBUG", False)
    _compat.LOG_DEBUG("should not appear")
    assert calls == []

    monkeypatch.setattr(_compat, "DEBUG", True)
    _compat.LOG_DEBUG("should appear")
    assert calls == [("should appear",)]
