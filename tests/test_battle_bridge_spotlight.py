# -*- coding: utf-8 -*-
"""Engine-free tests for WoT 2.4.0.0 "Spotlight" (prebattle_highlights) hide/reveal wiring in
battle_bridge:

* `_on_spotlight_start` / `_on_spotlight_end` add/discard the "prebattle_highlights" sentinel
  in `_open_overlays` and schedule a refresh.
* `_arm_overlay_listeners()` is fail-soft AND all-or-nothing on the spotlight pair: an old
  client's `GameEvent` missing either member must leave the spotlight listeners unsubscribed
  (never armed-to-hide with no way to restore) without raising, while a client with both
  members subscribes both.

Technique mirrors test_battle_bridge.py's fake-game-symbol stubbing.
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


class _FakeEventBus(object):
    def __init__(self):
        self.calls = []

    def addListener(self, event, handler, scope=None):
        self.calls.append((event, handler, scope))


class _Scope(object):
    BATTLE = "battle"


def _install_gui_shared(monkeypatch, spotlight_members):
    """Install fake `gui.shared` (+`.events`) with the four scoreboard GameEvent members
    always present, plus whichever spotlight members `spotlight_members` names."""
    bus = _FakeEventBus()

    class _GameEvent(object):
        FULL_STATS = "full_stats"
        FULL_STATS_QUEST_PROGRESS = "full_stats_quest_progress"
        FULL_STATS_PERSONAL_RESERVES = "full_stats_personal_reserves"
        EVENT_STATS = "event_stats"

    for name in spotlight_members:
        setattr(_GameEvent, name, name.lower())

    shared_mod = types.ModuleType("gui.shared")
    shared_mod.g_eventBus = bus
    shared_mod.EVENT_BUS_SCOPE = _Scope
    events_mod = types.ModuleType("gui.shared.events")
    events_mod.GameEvent = _GameEvent
    monkeypatch.setitem(sys.modules, "gui.shared", shared_mod)
    monkeypatch.setitem(sys.modules, "gui.shared.events", events_mod)
    return bus


def setup_function(_):
    battle_bridge._overlay_listeners_armed = False
    battle_bridge._open_overlays.clear()


teardown_function = setup_function


def test_spotlight_start_adds_sentinel_and_schedules_refresh(monkeypatch):
    calls = []
    monkeypatch.setattr(battle_bridge, "_schedule_refresh", lambda: calls.append(1))
    battle_bridge._on_spotlight_start(object())
    assert "prebattle_highlights" in battle_bridge._open_overlays
    assert calls == [1]


def test_spotlight_end_discards_sentinel_and_schedules_refresh(monkeypatch):
    calls = []
    battle_bridge._open_overlays.add("prebattle_highlights")
    monkeypatch.setattr(battle_bridge, "_schedule_refresh", lambda: calls.append(1))
    battle_bridge._on_spotlight_end(object())
    assert "prebattle_highlights" not in battle_bridge._open_overlays
    assert calls == [1]


def test_arm_overlay_listeners_skips_spotlight_pair_when_either_member_missing(monkeypatch):
    for present in ([], ["GO_TO_PREBATTLE_HIGHLIGHTS"], ["RETURN_FROM_PREBATTLE_HIGHLIGHTS"]):
        battle_bridge._overlay_listeners_armed = False
        bus = _install_gui_shared(monkeypatch, present)
        battle_bridge._arm_overlay_listeners()  # must not raise
        handlers = [h for _ev, h, _scope in bus.calls]
        assert battle_bridge._on_spotlight_start not in handlers
        assert battle_bridge._on_spotlight_end not in handlers
        assert len(bus.calls) == 4  # only the scoreboard listeners armed
        assert battle_bridge._overlay_listeners_armed is True


def test_arm_overlay_listeners_subscribes_spotlight_pair_when_both_members_present(monkeypatch):
    bus = _install_gui_shared(
        monkeypatch, ["GO_TO_PREBATTLE_HIGHLIGHTS", "RETURN_FROM_PREBATTLE_HIGHLIGHTS"])
    battle_bridge._arm_overlay_listeners()
    events_and_handlers = [(ev, h) for ev, h, _scope in bus.calls]
    assert ("go_to_prebattle_highlights", battle_bridge._on_spotlight_start) in events_and_handlers
    assert ("return_from_prebattle_highlights",
            battle_bridge._on_spotlight_end) in events_and_handlers
    assert len(bus.calls) == 6
    assert battle_bridge._overlay_listeners_armed is True
