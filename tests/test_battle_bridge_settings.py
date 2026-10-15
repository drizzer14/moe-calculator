# -*- coding: utf-8 -*-
"""Engine-free tests for battle_bridge._on_settings_changed -- the ONE settingsCore listener that
routes TWO unrelated keys: the "Summarized damage" DAMAGE_LOG group (re-places the overlay) and
GAME.MINIMAP_SIZE (re-places the two bars). Both keys ride the SAME onSettingsChanged(diff) event,
so the routing itself -- not just each individual re-place -- is what a mutation could silently
break: an over-broad filter would re-place everything on every settings change, and an
under-broad one would miss a genuine minimap resize or damage-log toggle.

conftest.py stubs account_helpers.settings_core.settings_constants (DAMAGE_LOG / GAME) so this
drives the REAL routing branches, not the function's own except-branch fail-open fallback. Mirrors
test_battle_bridge_prediction.py's fake-game-symbol technique for importing battle_bridge under
pytest.
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
from account_helpers.settings_core.settings_constants import DAMAGE_LOG, GAME


def _calls(monkeypatch):
    """Spy on all three windows' apply_position(), returning the set of labels that fired."""
    fired = set()
    monkeypatch.setattr(battle_bridge.battle_view, "apply_position",
                        lambda: fired.add("overlay"))
    monkeypatch.setattr(battle_bridge.progress_view, "apply_position",
                        lambda: fired.add("progress"))
    monkeypatch.setattr(battle_bridge.efficiency_view, "apply_position",
                        lambda: fired.add("efficiency"))
    return fired


def test_a_damage_log_diff_reroutes_only_the_overlay(monkeypatch):
    fired = _calls(monkeypatch)
    battle_bridge._on_settings_changed({DAMAGE_LOG.TOTAL_DAMAGE: True})
    assert fired == {"overlay"}


def test_each_of_the_four_damage_log_keys_reroutes_the_overlay(monkeypatch):
    for key in (DAMAGE_LOG.TOTAL_DAMAGE, DAMAGE_LOG.BLOCKED_DAMAGE, DAMAGE_LOG.ASSIST_DAMAGE,
                DAMAGE_LOG.ASSIST_STUN):
        fired = _calls(monkeypatch)
        battle_bridge._on_settings_changed({key: False})
        assert fired == {"overlay"}, "key %s did not reroute the overlay" % key


def test_a_minimap_size_diff_reroutes_only_the_two_bars(monkeypatch):
    fired = _calls(monkeypatch)
    battle_bridge._on_settings_changed({GAME.MINIMAP_SIZE: 3})
    assert fired == {"progress", "efficiency"}


def test_a_damage_log_only_diff_does_not_reroute_the_bars(monkeypatch):
    # THE NEGATIVE CASE: catches an over-broad filter that would re-place the bars on every
    # unrelated settings change (the routing lives on ONE shared event; a too-loose key check would
    # never be seen by anything except a diff-content assertion like this one).
    fired = _calls(monkeypatch)
    battle_bridge._on_settings_changed({DAMAGE_LOG.TOTAL_DAMAGE: True})
    assert "progress" not in fired and "efficiency" not in fired


def test_a_minimap_size_only_diff_does_not_reroute_the_overlay(monkeypatch):
    # The mirror negative case: a minimap resize must not needlessly re-place the corner overlay.
    fired = _calls(monkeypatch)
    battle_bridge._on_settings_changed({GAME.MINIMAP_SIZE: 3})
    assert "overlay" not in fired


def test_an_unrelated_key_reroutes_nothing(monkeypatch):
    fired = _calls(monkeypatch)
    battle_bridge._on_settings_changed({"someOtherModsSetting": True})
    assert fired == set()


def test_both_keys_present_reroute_everything(monkeypatch):
    fired = _calls(monkeypatch)
    battle_bridge._on_settings_changed({DAMAGE_LOG.TOTAL_DAMAGE: True, GAME.MINIMAP_SIZE: 2})
    assert fired == {"overlay", "progress", "efficiency"}


def test_a_none_diff_fails_open_and_reroutes_everything(monkeypatch):
    # diff=None is the "can't tell what changed" case (e.g. a full settings reload) -- fail OPEN
    # (re-place everything) rather than miss a real change; a spurious re-place is harmless.
    fired = _calls(monkeypatch)
    battle_bridge._on_settings_changed(None)
    assert fired == {"overlay", "progress", "efficiency"}


def test_a_broken_constants_import_fails_open_and_reroutes_everything(monkeypatch):
    # If account_helpers.settings_core.settings_constants itself becomes unreadable (or its
    # attributes change shape), the whole routed branch raises into the outer except, which
    # re-places every window rather than silently going dark.
    fired = _calls(monkeypatch)
    monkeypatch.delitem(sys.modules, "account_helpers.settings_core.settings_constants")
    battle_bridge._on_settings_changed({"anything": True})
    assert fired == {"overlay", "progress", "efficiency"}


# --- a Show MoE % flip + apply_settings() re-pushes the -1 sentinel ------------------------------

def test_flipping_each_bars_show_percent_then_apply_settings_repushes_minus_one_on_that_bar(monkeypatch):
    from moe_calculator.bridge import mod_settings
    from moe_calculator.bridge.view_models import EfficiencyVM, ProgressVM
    from moe_calculator.domain import battle_types as bt

    class _VM(object):
        def __init__(self, vm_cls):
            self.props = {}
            self._known = frozenset(n[3].lower() + n[4:] for n in dir(vm_cls) if n.startswith("set"))

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
            assert key in self._known, "no VM property %s" % key
            return lambda v: self.props.__setitem__(key, v)

    ma_vm, de_vm = _VM(ProgressVM), _VM(EfficiencyVM)
    snap = bt.BattleSnapshot(vehicle_int_cd=1073, thresholds={65: 2450, 85: 3050, 95: 3620, 100: 4400},
                             has_vehicle=True, in_battle=True, is_spectating=False,
                             baseline_known=True, pre_avg_damage=1850, pre_percentile=73.67)
    monkeypatch.setattr(battle_bridge, "_in_battle", False)          # open/close loop stays inert
    monkeypatch.setattr(battle_bridge, "_open_overlays", set())
    monkeypatch.setattr(battle_bridge.battle_view, "active_view", lambda: None)
    monkeypatch.setattr(battle_bridge.progress_view, "active_view",
                        lambda: types.SimpleNamespace(viewModel=ma_vm))
    monkeypatch.setattr(battle_bridge.efficiency_view, "active_view",
                        lambda: types.SimpleNamespace(viewModel=de_vm))
    monkeypatch.setattr(battle_bridge.progress_view, "has_placed", lambda: True)
    monkeypatch.setattr(battle_bridge.efficiency_view, "has_placed", lambda: True)
    monkeypatch.setattr(battle_bridge.progress_view, "apply_position", lambda: None)
    monkeypatch.setattr(battle_bridge.efficiency_view, "apply_position", lambda: None)
    monkeypatch.setattr(battle_bridge.battle_adapter, "build_battle_snapshot", lambda: snap)
    monkeypatch.setattr(battle_bridge, "_record_played_tank", lambda s: None)
    monkeypatch.setattr(battle_bridge, "_note_prediction", lambda s, m: None)
    monkeypatch.setattr(battle_bridge.battle_input, "set_hotkey", lambda *a, **k: None)
    monkeypatch.setattr(mod_settings, "progress_bar_enabled", lambda: True)
    saved = dict(mod_settings._settings)
    try:
        P, E = mod_settings.PROGRESS_SHOW_PERCENT_KEY, mod_settings.EFFICIENCY_SHOW_PERCENT_KEY
        mod_settings._apply({P: True, E: True})
        battle_bridge.apply_settings()
        assert ma_vm.props["curPercent"] >= 0.0 and de_vm.props["damagePercent"] >= 0.0

        mod_settings._apply({P: False, E: True})          # MA key gates ONLY the MA bar
        battle_bridge.apply_settings()
        assert ma_vm.props["curPercent"] == -1.0
        assert de_vm.props["damagePercent"] >= 0.0

        mod_settings._apply({P: True, E: False})          # DE key gates ONLY the DE bar
        battle_bridge.apply_settings()
        assert ma_vm.props["curPercent"] >= 0.0
        assert de_vm.props["damagePercent"] == -1.0

        mod_settings._apply({P: False, E: False})
        battle_bridge.apply_settings()
        assert ma_vm.props["curPercent"] == -1.0 and de_vm.props["damagePercent"] == -1.0

        mod_settings._apply({P: True, E: True})           # and back
        battle_bridge.apply_settings()
        assert ma_vm.props["curPercent"] >= 0.0 and de_vm.props["damagePercent"] >= 0.0
    finally:
        mod_settings._seed(saved)
