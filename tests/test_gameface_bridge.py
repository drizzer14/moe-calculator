# -*- coding: utf-8 -*-
"""Engine-free tests for the garage bridge's reverse channel (`_on_set_position`).

The bridge normally imports live game symbols at module top (helpers, skeletons, Wulf,
OpenWG), so -- mirroring conftest's documented fake-game-symbol technique -- we install bare
stub modules into sys.modules BEFORE importing gameface_bridge. These stubs only satisfy the
imports; every assertion drives real behavior by spying on `mod_settings.set_position`, never
these stubs. Only `_on_set_position`'s pure guard/parse logic is exercised here; the mount /
inject / marshal path needs the live client and is out of scope for a unit test."""
import sys
import types


def _stub(name, **attrs):
    """Install a stub module (creating any missing parent packages) so a top-level game import
    resolves under pytest. Idempotent: only fills attrs that are absent."""
    parts = name.split(".")
    for i in range(1, len(parts) + 1):
        p = ".".join(parts[:i])
        if p not in sys.modules:
            sys.modules[p] = types.ModuleType(p)
    mod = sys.modules[name]
    for key, value in attrs.items():
        if not hasattr(mod, key):
            setattr(mod, key, value)
    return mod


# CurrentVehicle + BigWorld are already stubbed by conftest; add the rest gameface_bridge needs.
_stub("helpers", dependency=types.SimpleNamespace(instance=lambda *a, **k: None))
_stub("skeletons.gui.shared", IItemsCache=object)


class _StubViewModel(object):
    def __init__(self, *a, **k):
        pass


class _StubArray(object):
    def __init__(self, *a, **k):
        pass


_stub("frameworks.wulf", ViewModel=_StubViewModel, Array=_StubArray)
_stub("openwg_gameface", gf_mod_inject=lambda *a, **k: None)

from moe_calculator.bridge import gameface_bridge  # noqa: E402


class _WulfMap(object):
    """A Wulf-wrapped map: not a dict, but exposes .get(key) -- as delivered by the engine."""
    def __init__(self, d):
        self._d = d

    def get(self, key):
        return self._d.get(key)


def _spy_set_position(monkeypatch):
    """Replace mod_settings.set_position with a recorder and return the call list."""
    calls = []
    monkeypatch.setattr(
        gameface_bridge.mod_settings, "set_position",
        lambda x, y, w=0, h=0: calls.append((x, y, w, h)))
    return calls


def test_persists_a_real_pin(monkeypatch):
    # A positive (x, y) drag release persists, carrying the capture viewport (w, h).
    calls = _spy_set_position(monkeypatch)
    gameface_bridge._on_set_position({"x": 100, "y": 200, "w": 1920, "h": 1080})
    assert calls == [(100, 200, 1920, 1080)]


def test_persists_from_wulf_wrapped_map(monkeypatch):
    # The engine may deliver a Wulf map object rather than a plain dict.
    calls = _spy_set_position(monkeypatch)
    gameface_bridge._on_set_position(_WulfMap({"x": 50, "y": 60, "w": 800, "h": 600}))
    assert calls == [(50, 60, 800, 600)]


def test_persists_without_viewport(monkeypatch):
    # w/h absent -> stored as 0 (unknown), but a valid pin still persists.
    calls = _spy_set_position(monkeypatch)
    gameface_bridge._on_set_position({"x": 10, "y": 20})
    assert calls == [(10, 20, 0, 0)]


def test_drops_when_x_not_positive(monkeypatch):
    # x <= 0 is the auto sentinel / a bad measurement -> never clobber the stored pin.
    calls = _spy_set_position(monkeypatch)
    gameface_bridge._on_set_position({"x": 0, "y": 200, "w": 1920, "h": 1080})
    gameface_bridge._on_set_position({"x": -5, "y": 200, "w": 1920, "h": 1080})
    assert calls == []


def test_drops_when_y_not_positive(monkeypatch):
    calls = _spy_set_position(monkeypatch)
    gameface_bridge._on_set_position({"x": 100, "y": 0, "w": 1920, "h": 1080})
    gameface_bridge._on_set_position({"x": 100, "y": -1, "w": 1920, "h": 1080})
    assert calls == []


def test_drops_the_parse_failure_signature(monkeypatch):
    # A missing / unparseable map parses to (0, 0) -- the drop guard swallows it.
    calls = _spy_set_position(monkeypatch)
    gameface_bridge._on_set_position({})
    gameface_bridge._on_set_position({"x": "nope", "y": "nope"})
    assert calls == []


def test_never_raises_into_js(monkeypatch):
    # A handler that raised would propagate into the Wulf command dispatch; it must swallow.
    def _boom(*a, **k):
        raise RuntimeError("MSA exploded")

    monkeypatch.setattr(gameface_bridge.mod_settings, "set_position", _boom)
    # Must not raise.
    gameface_bridge._on_set_position({"x": 100, "y": 200, "w": 1920, "h": 1080})
