# -*- coding: utf-8 -*-
"""Engine-free tests for the Onslaught (COMP7) pre-battle vehicle-ban hide/reveal wiring in
battle_bridge:

* `_on_comp7_ban_phase` reads the controller's `getArenaPrebattlePhase()` fail-soft: PREPICK(1)
  or VOTING(2) add the "comp7_vehicle_ban" sentinel to `_open_overlays`, any OTHER value --
  including a failed/raising read -- discards it. Always schedules a refresh.
* `_arm_comp7_ban_listener()` resolves the controller via `battle_adapter._comp7_vehicle_ban_ctrl`;
  None (non-Onslaught / absent package) arms nothing and does not raise; a real controller gets
  subscribed exactly once (idempotent) plus one initial-state read.
* `_disarm_comp7_ban_listener()` detaches the handler and nulls the module global; safe to call
  when nothing was armed.

Technique mirrors test_battle_bridge_spotlight.py's fake-game-symbol stubbing.
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
from moe_calculator.adapter import battle_adapter


class _FakeEvent(object):
    """List-backed +=/-=/`in` fake, mirroring how the suite fakes WoT Event objects."""
    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def __isub__(self, handler):
        self.handlers.remove(handler)
        return self

    def __contains__(self, handler):
        return handler in self.handlers


class _FakeComp7Ctrl(object):
    def __init__(self, phase=0):
        self.phase = phase
        self.raises = False
        self.onBanPhaseUpdated = _FakeEvent()

    def getArenaPrebattlePhase(self):
        if self.raises:
            raise RuntimeError("boom")
        return self.phase


def setup_function(_):
    battle_bridge._open_overlays.clear()
    battle_bridge._comp7_ban_ctrl = None


teardown_function = setup_function


# --- _on_comp7_ban_phase -------------------------------------------------------

def _refresh_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(battle_bridge, "_schedule_refresh", lambda: calls.append(1))
    return calls


def test_on_comp7_ban_phase_prepick_adds_sentinel(monkeypatch):
    calls = _refresh_calls(monkeypatch)
    battle_bridge._comp7_ban_ctrl = _FakeComp7Ctrl(phase=battle_bridge._COMP7_PHASE_PREPICK)
    battle_bridge._on_comp7_ban_phase()
    assert "comp7_vehicle_ban" in battle_bridge._open_overlays
    assert calls == [1]


def test_on_comp7_ban_phase_voting_adds_sentinel(monkeypatch):
    calls = _refresh_calls(monkeypatch)
    battle_bridge._comp7_ban_ctrl = _FakeComp7Ctrl(phase=battle_bridge._COMP7_PHASE_VOTING)
    battle_bridge._on_comp7_ban_phase()
    assert "comp7_vehicle_ban" in battle_bridge._open_overlays
    assert calls == [1]


def test_on_comp7_ban_phase_none_discards_sentinel(monkeypatch):
    calls = _refresh_calls(monkeypatch)
    battle_bridge._open_overlays.add("comp7_vehicle_ban")
    battle_bridge._comp7_ban_ctrl = _FakeComp7Ctrl(phase=0)
    battle_bridge._on_comp7_ban_phase()
    assert "comp7_vehicle_ban" not in battle_bridge._open_overlays
    assert calls == [1]


def test_on_comp7_ban_phase_pick_discards_sentinel(monkeypatch):
    calls = _refresh_calls(monkeypatch)
    battle_bridge._open_overlays.add("comp7_vehicle_ban")
    battle_bridge._comp7_ban_ctrl = _FakeComp7Ctrl(phase=3)
    battle_bridge._on_comp7_ban_phase()
    assert "comp7_vehicle_ban" not in battle_bridge._open_overlays
    assert calls == [1]


def test_on_comp7_ban_phase_raising_read_discards_never_wedges(monkeypatch):
    calls = _refresh_calls(monkeypatch)
    battle_bridge._open_overlays.add("comp7_vehicle_ban")
    ctrl = _FakeComp7Ctrl(phase=battle_bridge._COMP7_PHASE_VOTING)
    ctrl.raises = True
    battle_bridge._comp7_ban_ctrl = ctrl
    battle_bridge._on_comp7_ban_phase()  # must not raise
    assert "comp7_vehicle_ban" not in battle_bridge._open_overlays
    assert calls == [1]


# --- _arm_comp7_ban_listener / _disarm_comp7_ban_listener ----------------------

def test_arm_comp7_ban_listener_noop_when_controller_absent(monkeypatch):
    monkeypatch.setattr(battle_adapter, "_comp7_vehicle_ban_ctrl", lambda: None)
    battle_bridge._arm_comp7_ban_listener()  # must not raise
    assert battle_bridge._comp7_ban_ctrl is None
    assert battle_bridge._open_overlays == set()


def test_arm_comp7_ban_listener_subscribes_once_and_reads_initial_state(monkeypatch):
    ctrl = _FakeComp7Ctrl(phase=battle_bridge._COMP7_PHASE_VOTING)
    monkeypatch.setattr(battle_adapter, "_comp7_vehicle_ban_ctrl", lambda: ctrl)

    battle_bridge._arm_comp7_ban_listener()
    assert battle_bridge._comp7_ban_ctrl is ctrl
    assert ctrl.onBanPhaseUpdated.handlers == [battle_bridge._on_comp7_ban_phase]
    # One-shot initial read done during arm, without the event ever firing.
    assert "comp7_vehicle_ban" in battle_bridge._open_overlays

    battle_bridge._arm_comp7_ban_listener()  # re-arm (e.g. a second mount) must not double-subscribe
    assert ctrl.onBanPhaseUpdated.handlers == [battle_bridge._on_comp7_ban_phase]


def test_disarm_comp7_ban_listener_detaches_and_nulls_global(monkeypatch):
    ctrl = _FakeComp7Ctrl(phase=battle_bridge._COMP7_PHASE_VOTING)
    monkeypatch.setattr(battle_adapter, "_comp7_vehicle_ban_ctrl", lambda: ctrl)
    battle_bridge._arm_comp7_ban_listener()

    battle_bridge._disarm_comp7_ban_listener()
    assert battle_bridge._comp7_ban_ctrl is None
    assert ctrl.onBanPhaseUpdated.handlers == []


def test_disarm_comp7_ban_listener_safe_when_nothing_armed():
    battle_bridge._comp7_ban_ctrl = None
    battle_bridge._disarm_comp7_ban_listener()  # must not raise
    assert battle_bridge._comp7_ban_ctrl is None
