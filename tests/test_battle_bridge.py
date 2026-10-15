# -*- coding: utf-8 -*-
"""Engine-free tests for the per-vehicle progress-bar MODE OVERRIDE wiring in battle_bridge:

* `_window_gates()` must resolve the effective variant through `variant_overrides.effective`,
  keyed off the currently-played vehicle's intCD (`_current_int_cd`), rather than reading
  `mod_settings.progress_bar_variant()` directly -- so a stored per-vehicle override actually
  swaps which of the two centre-screen bars is gated on.
* `_on_variant_toggle()` (the hotkey handler) must no-op with no known vehicle (pregame /
  spectating), and otherwise persist the flip via `variant_overrides.toggle` and re-apply
  settings so the swap takes effect immediately.

Technique mirrors test_battle_bridge_prediction.py's fake-game-symbol stubbing.
"""
import sys
import types


def _stub(name, **attrs):
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


class _Permissive(object):
    def __init__(self, *a, **k):
        pass


_stub("frameworks.wulf", ViewModel=_Permissive, Array=_Permissive, ViewSettings=_Permissive,
      ViewFlags=object(), WindowFlags=object(), WindowLayer=object(), PositionAnchor=object())
_stub("gui.impl.pub", ViewImpl=_Permissive, WindowImpl=_Permissive)
_stub("openwg_gameface",
      gf_mod_inject=lambda *a, **k: None)

from moe_calculator.bridge import battle_bridge
from moe_calculator.bridge import mod_settings


def setup_function(_):
    battle_bridge._current_int_cd = None


teardown_function = setup_function


def test_window_gates_honors_override(monkeypatch):
    monkeypatch.setattr(mod_settings, "progress_bar_enabled", lambda: True)
    monkeypatch.setattr(mod_settings, "battle_enabled", lambda: False)
    monkeypatch.setattr(mod_settings, "progress_bar_variant", lambda: 0)   # default Efficiency
    monkeypatch.setattr(battle_bridge.variant_overrides, "effective",
                        lambda icd, default: 1 if icd == 555 else default)
    battle_bridge._current_int_cd = 555
    gates = dict((m, e) for e, m in battle_bridge._window_gates())
    assert gates[battle_bridge.progress_view] is True
    assert gates[battle_bridge.efficiency_view] is False
    battle_bridge._current_int_cd = None
    gates = dict((m, e) for e, m in battle_bridge._window_gates())
    assert gates[battle_bridge.efficiency_view] is True


def test_variant_toggle_persists_and_reapplies(monkeypatch):
    calls = {"toggle": [], "apply": 0}
    monkeypatch.setattr(battle_bridge.variant_overrides, "toggle",
                        lambda icd, d: calls["toggle"].append((icd, d)) or 1)
    monkeypatch.setattr(battle_bridge, "apply_settings",
                        lambda: calls.__setitem__("apply", calls["apply"] + 1))
    monkeypatch.setattr(mod_settings, "progress_bar_variant", lambda: 0)
    battle_bridge._current_int_cd = None
    battle_bridge._on_variant_toggle()
    assert calls["toggle"] == [] and calls["apply"] == 0
    battle_bridge._current_int_cd = 555
    battle_bridge._on_variant_toggle()
    assert calls["toggle"] == [(555, 0)] and calls["apply"] == 1


# --- _maybe_auto_toggle: the automatic per-vehicle mode toggle, fired on mount -----------------

def _wire_auto_toggle(monkeypatch, threshold, pct, effective, default_variant=0):
    monkeypatch.setattr(mod_settings, "progress_auto_toggle_threshold", lambda: threshold)
    monkeypatch.setattr(mod_settings, "progress_bar_variant", lambda: default_variant)
    monkeypatch.setattr(battle_bridge.battle_adapter, "pre_percentile", lambda cd: pct)
    monkeypatch.setattr(battle_bridge.variant_overrides, "effective", lambda cd, d: effective)


def test_maybe_auto_toggle_noop_with_no_known_vehicle(monkeypatch):
    calls = []
    monkeypatch.setattr(battle_bridge.variant_overrides, "toggle",
                        lambda icd, d: calls.append((icd, d)))
    _wire_auto_toggle(monkeypatch, threshold=50, pct=90.0, effective=0)
    battle_bridge._maybe_auto_toggle(None)
    assert calls == []


def test_maybe_auto_toggle_noop_below_threshold(monkeypatch):
    calls = []
    monkeypatch.setattr(battle_bridge.variant_overrides, "toggle",
                        lambda icd, d: calls.append((icd, d)))
    _wire_auto_toggle(monkeypatch, threshold=50, pct=49.9, effective=0)
    battle_bridge._maybe_auto_toggle(555)
    assert calls == []


def test_maybe_auto_toggle_fires_once_when_qualifying(monkeypatch):
    calls = []
    monkeypatch.setattr(battle_bridge.variant_overrides, "toggle",
                        lambda icd, d: calls.append((icd, d)) or 1)
    _wire_auto_toggle(monkeypatch, threshold=50, pct=90.0, effective=0, default_variant=0)
    battle_bridge._maybe_auto_toggle(555)
    assert calls == [(555, 0)]


def test_maybe_auto_toggle_is_idempotent_on_a_second_qualifying_mount(monkeypatch):
    # THE key behavioral guarantee: once the vehicle is overridden, a REPEAT qualifying battle
    # must not flip it back. effective now != default_variant -- should_auto_toggle's own guard.
    calls = []
    monkeypatch.setattr(battle_bridge.variant_overrides, "toggle",
                        lambda icd, d: calls.append((icd, d)) or 1)
    _wire_auto_toggle(monkeypatch, threshold=50, pct=90.0, effective=1, default_variant=0)
    battle_bridge._maybe_auto_toggle(555)
    assert calls == []
