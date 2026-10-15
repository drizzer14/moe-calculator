# -*- coding: utf-8 -*-
"""Engine-free tests for the Onslaught (COMP7) "onslaught_start" force-hide sentinel in
battle_bridge:

* `_on_mount_refresh` adds "onslaught_start" to `_open_overlays` iff THIS battle is Onslaught
  (`battle_adapter._comp7_vehicle_ban_ctrl()` returns non-None) -- added BEFORE the first push
  so there is no reveal flash -- and hides all three battle windows while it is present.
* `_on_arena_period_changed` is the reveal edge: discards the sentinel once the arena period
  reaches ARENA_PERIOD.BATTLE, never earlier.
* The sentinel is independent of "comp7_vehicle_ban": the ban-phase listener clearing its OWN
  key must still leave the widgets hidden while "onslaught_start" is still set (any key in the
  set hides -- see `_open_overlays`'s own docstring).
* `_on_teardown` discards it so it can never leak into the next mount.

Technique mirrors test_battle_bridge_comp7_ban.py's fake-game-symbol stubbing.
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
from moe_calculator.adapter import battle_adapter
from moe_calculator.domain import battle_types as bt

THR = {65: 2450, 85: 3050, 95: 3620, 100: 4400}


def setup_function(_):
    battle_bridge._open_overlays.clear()
    battle_bridge._in_battle = False
    battle_bridge._current_int_cd = None


teardown_function = setup_function


class _FakeVM(object):
    """Records every set*() call made in a transaction; accepts anything (these tests only
    care about `visible`, not the full field set)."""
    def __init__(self):
        self.props = {}

    def transaction(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __getattr__(self, name):
        if not name.startswith("set"):
            raise AttributeError(name)
        key = name[3].lower() + name[4:]
        return lambda v: self.props.__setitem__(key, v)


def _snap(**over):
    kwargs = dict(vehicle_int_cd=1073, thresholds=dict(THR),
                  has_vehicle=True, in_battle=True, is_spectating=False, baseline_known=True,
                  pre_avg_damage=1850, pre_percentile=73.67)
    kwargs.update(over)
    return bt.BattleSnapshot(**kwargs)


def _model(**over):
    kwargs = dict(combined_damage=500, proj_avg_damage=1867, cur_percent=74.3,
                  pct_delta=0.63, has_data=True, has_baseline=True,
                  counted_assist=0, assist_kind="")
    kwargs.update(over)
    return bt.BattleMoEModel(**kwargs)


def _wire_all_windows_visible(monkeypatch):
    """Make every gate say "show" so the ONLY thing that can force these three pushes
    invisible is the `_open_overlays` sentinel under test."""
    monkeypatch.setattr(mod_settings, "battle_enabled", lambda: True)
    monkeypatch.setattr(mod_settings, "battle_alt_key_enabled", lambda: False)
    monkeypatch.setattr(mod_settings, "counted_assistance_enabled", lambda: False)
    monkeypatch.setattr(mod_settings, "progress_bar_enabled", lambda: True)
    monkeypatch.setattr(mod_settings, "progress_bar_variant",
                        lambda: mod_settings.PROGRESS_VARIANT_EFFICIENCY)
    monkeypatch.setattr(battle_bridge.variant_overrides, "effective", lambda cd, d: d)
    monkeypatch.setattr(battle_bridge.progress_view, "has_placed", lambda: True)
    monkeypatch.setattr(battle_bridge.efficiency_view, "has_placed", lambda: True)


def _all_three_visible(monkeypatch):
    _wire_all_windows_visible(monkeypatch)
    snap, model = _snap(), _model()
    vm = _FakeVM()
    battle_bridge.push(vm, snap, model)
    bar_vm = _FakeVM()
    battle_bridge.push_progress(bar_vm, snap, model)
    eff_vm = _FakeVM()
    battle_bridge.push_efficiency(eff_vm, snap, model)
    return vm.props["visible"], bar_vm.props["visible"], eff_vm.props["visible"]


# --- 1/2: _on_mount_refresh gates the sentinel on Onslaught detection ---------

def test_onslaught_mount_adds_sentinel_and_hides_all_three_windows(monkeypatch):
    monkeypatch.setattr(battle_adapter, "_comp7_vehicle_ban_ctrl", lambda: object())
    monkeypatch.setattr(battle_adapter, "_player_vehicle_descr", lambda: None)
    battle_bridge._on_mount_refresh()
    assert "onslaught_start" in battle_bridge._open_overlays
    assert _all_three_visible(monkeypatch) == (False, False, False)


def test_non_onslaught_mount_does_not_add_sentinel(monkeypatch):
    monkeypatch.setattr(battle_adapter, "_comp7_vehicle_ban_ctrl", lambda: None)
    monkeypatch.setattr(battle_adapter, "_player_vehicle_descr", lambda: None)
    battle_bridge._on_mount_refresh()
    assert "onslaught_start" not in battle_bridge._open_overlays
    assert _all_three_visible(monkeypatch) == (True, True, True)


# --- 3: _on_arena_period_changed is the reveal edge ---------------------------

class _FakeArena(object):
    def __init__(self, period):
        self.period = period


class _FakePlayer(object):
    def __init__(self, period):
        self.arena = _FakeArena(period)


class _ARENA_PERIOD(object):
    PREBATTLE = "prebattle-period"
    BATTLE = "battle-period"
    AFTERBATTLE = "afterbattle-period"


def _install_arena_period(monkeypatch, current_period):
    """Stub `constants.ARENA_PERIOD` and `BigWorld.player()` so the reveal-edge read resolves to
    a REAL (non-fail-soft) value."""
    monkeypatch.setitem(sys.modules, "constants", types.ModuleType("constants"))
    sys.modules["constants"].ARENA_PERIOD = _ARENA_PERIOD
    monkeypatch.setattr(battle_bridge.BigWorld, "player", lambda: _FakePlayer(current_period))
    monkeypatch.setattr(battle_bridge, "refresh", lambda: None)


def test_arena_period_reaching_battle_discards_the_sentinel(monkeypatch):
    battle_bridge._open_overlays.add("onslaught_start")
    _install_arena_period(monkeypatch, current_period=_ARENA_PERIOD.BATTLE)
    battle_bridge._on_arena_period_changed()
    assert "onslaught_start" not in battle_bridge._open_overlays


def test_an_earlier_arena_period_does_not_discard_the_sentinel(monkeypatch):
    battle_bridge._open_overlays.add("onslaught_start")
    _install_arena_period(monkeypatch, current_period=_ARENA_PERIOD.PREBATTLE)
    battle_bridge._on_arena_period_changed()
    assert "onslaught_start" in battle_bridge._open_overlays


def test_arena_period_changed_is_a_noop_when_sentinel_absent(monkeypatch):
    # Guard against the handler adding the key back or raising when it was never set (a
    # non-Onslaught battle's every arena-period tick funnels through this same handler).
    calls = []
    monkeypatch.setattr(battle_bridge, "refresh", lambda: calls.append(1))
    battle_bridge._on_arena_period_changed()
    assert "onslaught_start" not in battle_bridge._open_overlays
    assert calls == [1]


# --- 4: independence from the comp7-ban key -----------------------------------

def test_comp7_ban_key_clearing_alone_leaves_widgets_hidden_while_onslaught_start_remains(
        monkeypatch):
    battle_bridge._open_overlays.add("onslaught_start")
    battle_bridge._open_overlays.add("comp7_vehicle_ban")
    # The ban-phase listener clears ONLY its own key (as it does on PICK/NONE).
    battle_bridge._open_overlays.discard("comp7_vehicle_ban")
    assert battle_bridge._open_overlays == {"onslaught_start"}
    assert _all_three_visible(monkeypatch) == (False, False, False)


# --- 5: teardown discards it ---------------------------------------------------

def test_teardown_discards_the_onslaught_start_sentinel(monkeypatch):
    battle_bridge._open_overlays.add("onslaught_start")
    monkeypatch.setattr(battle_bridge, "_disarm_comp7_ban_listener", lambda: None)
    monkeypatch.setattr(battle_bridge, "_flush_prediction", lambda: None)
    monkeypatch.setattr(battle_bridge.battle_view, "close_window", lambda: None)
    monkeypatch.setattr(battle_bridge.progress_view, "close_window", lambda: None)
    monkeypatch.setattr(battle_bridge.efficiency_view, "close_window", lambda: None)
    battle_bridge._on_teardown()
    assert "onslaught_start" not in battle_bridge._open_overlays
