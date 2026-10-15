# -*- coding: utf-8 -*-
"""Engine-free tests for the MOVING AVERAGE bar's push marshalling (`push_progress`).

The sibling test_efficiency_bridge covers the OTHER centre-screen bar; this file is the same seam
for ProgressVM, which had no pytest coverage of its own. `push_progress` is that model's only
producer, so a property declared on one side without the other leaves the JS reading a default
forever -- and, unlike a missing setter, nothing raises: the push wraps its whole transaction in
`except Exception: LOG_CURRENT_EXCEPTION()`, so a desync is SILENT in the client.

Technique is test_efficiency_bridge's: install bare stub modules for the game imports battle_bridge
pulls in transitively, then drive push_progress directly into a recording fake whose accepted setter
names are cross-checked against the real ProgressVM, so a typo'd setter cannot pass silently. The
window WIRING (does the engine actually open it) needs the live client and is out of scope.
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

import pytest

from moe_calculator.bridge import battle_bridge
from moe_calculator.bridge import mod_settings
from moe_calculator.bridge.view_models import ProgressVM
from moe_calculator.domain import battle_types as bt

THR = {65: 2450, 85: 3050, 95: 3620, 100: 4400}   # keyed by PERCENTILE, not by mark count

# The property names ProgressVM actually declares, derived from its OWN setters -- so this fake can
# never accept a set*() the shipped model does not have (nor miss one it does).
_VM_PROPS = frozenset(name[3].lower() + name[4:]
                      for name in dir(ProgressVM) if name.startswith("set"))


class _FakeVM(object):
    """Records what a push writes. Stands in for the Wulf-backed ProgressVM."""

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
        assert key in _VM_PROPS, "ProgressVM has no set%s" % name[3:]
        return lambda v: self.props.__setitem__(key, v)


def _snap(**over):
    kwargs = dict(vehicle_int_cd=1073, thresholds=dict(THR),
                  has_vehicle=True, in_battle=True, is_spectating=False, baseline_known=True,
                  pre_avg_damage=1850, pre_percentile=73.67)
    kwargs.update(over)
    return bt.BattleSnapshot(**kwargs)


def _model(**over):
    kwargs = dict(combined_damage=2000, proj_avg_damage=1867, cur_percent=74.3,
                  pct_delta=0.63, has_data=True, has_baseline=True,
                  counted_assist=0, assist_kind="")
    kwargs.update(over)
    return bt.BattleMoEModel(**kwargs)


@pytest.fixture(autouse=True)
def _fresh_battle(monkeypatch):
    """A fresh battle with the Moving Average bar enabled and no scoreboard up, and the settings
    cache restored afterwards (these tests SEED it rather than patching the getters, so the
    master-folding logic under test is the shipped one).

    `progress_view.has_placed()` defaults True here -- the real module-level BarHost has never
    placed a window under pytest (no live client), so leaving it unpatched would force `visible`
    False for every test in this file that isn't specifically exercising the has_placed() gate
    itself (see that gate's own tests below)."""
    monkeypatch.setattr(battle_bridge, "_open_overlays", set())
    monkeypatch.setattr(battle_bridge.progress_view, "has_placed", lambda: True)
    saved = dict(mod_settings._settings)
    mod_settings._apply({mod_settings.PROGRESS_BAR_KEY: True})
    yield
    mod_settings._seed(saved)


def _push(**settings_over):
    """push_progress's written props, with `settings_over` overlaid on the live settings cache."""
    if settings_over:
        mod_settings._apply(settings_over)
    vm = _FakeVM()
    battle_bridge.push_progress(vm, _snap(), _model())
    return vm.props


def test_push_writes_exactly_every_view_model_property():
    # ProgressVM's only producer, and the push swallows every exception -- so a prop declared on one
    # side only is invisible in the client. EIGHTEEN: the nine through barSize, then transEvents /
    # transManual, showEvents, holdMs, ctrlHeld, etaBattles, (Phase 1) `vertical` -- draw the
    # vertical composition instead of horizontal -- and `curPercent` (the "(73.84%)" caption), all
    # APPENDED after barSize so nothing above them is renumbered -- then `showDelta`.
    assert set(_push()) == _VM_PROPS
    assert "vertical" in _VM_PROPS
    assert "curPercent" in _VM_PROPS
    assert "showDelta" in _VM_PROPS
    assert len(_VM_PROPS) == 18


# --- push_progress's own has_placed() gate (the corner-flash fix) -----------------------------

def test_the_bar_is_hidden_while_the_host_has_never_placed(monkeypatch):
    # THE CORNER-FLASH FIX: bar_window.BarHost.has_placed() is False until this host's FIRST
    # window.move() has succeeded (see bar_window._place) -- while it is still False, the window
    # sits at the far-sentinel/minimap corner, so `visible` must stay forced False even though
    # every OTHER gate here (master on, has_baseline) says show.
    monkeypatch.setattr(battle_bridge.progress_view, "has_placed", lambda: False)
    assert _push()["visible"] is False


def test_the_bar_is_visible_once_the_host_has_placed(monkeypatch):
    # Transparent the moment the host HAS placed -- visible then follows the pre-existing gates'
    # own verdict exactly as before this gate existed.
    monkeypatch.setattr(battle_bridge.progress_view, "has_placed", lambda: True)
    assert _push()["visible"] is True


def test_push_writes_the_two_transition_flags_master_folded():
    # The widget never sees the Transitions MASTER: the getters AND it in, so the two pushed fields
    # are the EFFECTIVE values. Prove the fold reaches the wire, not just the getter -- patching the
    # getters here would prove only that the push calls them.
    props = _push(**{mod_settings.PROGRESS_TRANSITIONS_KEY: True,
                     mod_settings.PROGRESS_TRANS_EVENTS_KEY: True,
                     mod_settings.PROGRESS_TRANS_MANUAL_KEY: True})
    assert props["transEvents"] is True and props["transManual"] is True
    # Each child flips its OWN field and leaves the other alone.
    props = _push(**{mod_settings.PROGRESS_TRANS_EVENTS_KEY: False})
    assert props["transEvents"] is False and props["transManual"] is True
    props = _push(**{mod_settings.PROGRESS_TRANS_EVENTS_KEY: True,
                     mod_settings.PROGRESS_TRANS_MANUAL_KEY: False})
    assert props["transEvents"] is True and props["transManual"] is False
    # ...and the master forces BOTH off with the children left ON, which is the whole reason the
    # fold lives in Python: no JS-side AND to get wrong.
    props = _push(**{mod_settings.PROGRESS_TRANSITIONS_KEY: False,
                     mod_settings.PROGRESS_TRANS_EVENTS_KEY: True,
                     mod_settings.PROGRESS_TRANS_MANUAL_KEY: True})
    assert props["transEvents"] is False and props["transManual"] is False
    # The master is NEVER pushed under any name -- the widget must not be able to honour a child
    # while the master is off.
    assert mod_settings.PROGRESS_TRANSITIONS_KEY not in props
    assert "transitions" not in props and "transEnabled" not in props


def test_push_writes_the_visibility_switches_with_always_folded_in(monkeypatch):
    # The VISIBILITY trio -- WHEN the bar comes up, a different axis from the transitions pair
    # above (HOW it moves), which is why the two near-identical sets both exist. Only TWO fields
    # carry all three switches: `showEvents`, and `altHeld`, which absorbs both "Alt Press" and
    # "Always" because a permanently-held Alt is exactly how the shared JS transient pins the bar.
    def _show(events, alt_key, always, alt_down):
        monkeypatch.setattr(battle_bridge, "_alt_held", alt_down)
        props = _push(**{mod_settings.PROGRESS_SHOW_EVENTS_KEY: events,
                         mod_settings.PROGRESS_SHOW_ALT_KEY: alt_key,
                         mod_settings.PROGRESS_SHOW_ALWAYS_KEY: always})
        return props["showEvents"], props["altHeld"]

    # The shipped triggers: an event raises it, a held Alt peeks it.
    assert _show(True, True, False, False) == (True, False)
    assert _show(True, True, False, True) == (True, True)
    # Each switch mutes its OWN trigger and nothing else.
    assert _show(False, True, False, True) == (False, True)
    assert _show(True, False, False, True) == (True, False)
    assert _show(False, False, False, True) == (False, False)
    # "Always" pins the bar and re-enables the event field (so the pinned bar's numbers keep
    # updating) whatever the two greyed switches still store -- MSA pushes a greyed value anyway.
    assert _show(False, False, True, False) == (True, True)
    assert _show(False, False, True, True) == (True, True)
    # ...and neither raw key is pushed under its own name: the JS gets no third switch to misread.
    props = _push()
    for key in ("showAlways", "showAltKey", mod_settings.PROGRESS_SHOW_ALWAYS_KEY,
                mod_settings.PROGRESS_SHOW_ALT_KEY):
        assert key not in props


def test_push_writes_hold_ms_as_seconds_times_a_thousand_and_is_not_master_folded():
    # holdMs is progress_hold_seconds() * 1000, in MS for the JS clock -- and, unlike transEvents /
    # transManual above, it is DELIBERATELY NOT ANDed with the Transitions master: a duration ANDed
    # with a switch would push 0 (no hold at all), which is not what that checkbox means.
    props = _push(**{mod_settings.PROGRESS_HOLD_SECONDS_KEY: 17})
    assert props["holdMs"] == 17000
    # The default (5s) survives untouched end to end.
    props = _push(**{mod_settings.PROGRESS_HOLD_SECONDS_KEY: mod_settings.PROGRESS_HOLD_DEFAULT})
    assert props["holdMs"] == mod_settings.PROGRESS_HOLD_DEFAULT * 1000 == 5000
    # Turning the Transitions master OFF must not fold the duration to 0 -- only its own two
    # sibling switches (transEvents/transManual) fold; the hold is a duration, not a switch.
    props = _push(**{mod_settings.PROGRESS_TRANSITIONS_KEY: False,
                     mod_settings.PROGRESS_TRANS_EVENTS_KEY: False,
                     mod_settings.PROGRESS_TRANS_MANUAL_KEY: False,
                     mod_settings.PROGRESS_HOLD_SECONDS_KEY: 12})
    assert props["holdMs"] == 12000
    assert props["transEvents"] is False and props["transManual"] is False


def test_push_writes_eta_battles_from_the_domain_function(monkeypatch):
    # etaBattles must be the domain function's own verdict, not something push_progress
    # recomputes inline -- fake the function out and prove the pushed value came from it.
    calls = []

    def _fake_eta(proj_avg, cd, axis_hi):
        calls.append((proj_avg, cd, axis_hi))
        return 7

    monkeypatch.setattr(battle_bridge, "battles_to_axis_hi", _fake_eta)
    props = _push()
    assert props["etaBattles"] == 7
    assert len(calls) == 1
    # the pushed count came from this battle's combined damage, not just (proj_avg, axis_hi)
    assert calls[0][1] == _model().combined_damage


def test_push_gates_ctrl_held_on_free_alignment_regardless_of_which_visibility_switch_is_on(
        monkeypatch):
    # THE reported bug: pressing Ctrl revealed the bar even under Fixed alignment, because
    # MoEBarTransient.js's peek() ORs the pushed `ctrlHeld` into its show/hold decision
    # unconditionally -- bar_window.BarHost.drag() already refuses the WHOLE reposition gesture
    # unless alignment is Free, but that gate never reached the PUSHED ctrlHeld value, so it
    # stopped the drag but not the appearance. `ctrlHeld` must consult the SAME alignment gate
    # drag() does, and it must not care which show-trigger switch (Events/Alt Press/Always) is on
    # -- Ctrl is not Alt, and must not borrow Alt's show trigger from ANY of them.
    #
    # Matrix: alignment (Fixed/Free) x ctrl-down (True/False) x visibility config, including the
    # report's exact repro ("Alt-only": Events + Always off, Alt Press on) and its opposite
    # (Events on, Alt Press + Always off) -- ctrlHeld must land on the SAME value either way.
    cases = (
        (mod_settings.PROGRESS_ALIGN_FIXED, True, False),   # the reported repro
        (mod_settings.PROGRESS_ALIGN_FIXED, False, False),
        (mod_settings.PROGRESS_ALIGN_FREE, True, True),     # Free must keep working
        (mod_settings.PROGRESS_ALIGN_FREE, False, False),
    )
    visibility_configs = (
        {mod_settings.PROGRESS_SHOW_EVENTS_KEY: False, mod_settings.PROGRESS_SHOW_ALT_KEY: True,
         mod_settings.PROGRESS_SHOW_ALWAYS_KEY: False},   # "Alt-only"
        {mod_settings.PROGRESS_SHOW_EVENTS_KEY: True, mod_settings.PROGRESS_SHOW_ALT_KEY: False,
         mod_settings.PROGRESS_SHOW_ALWAYS_KEY: False},   # "Events-only"
    )
    for alignment, ctrl_down, expected in cases:
        monkeypatch.setattr(battle_bridge, "_ctrl_held", ctrl_down)
        for visibility in visibility_configs:
            settings_over = dict(visibility)
            settings_over[mod_settings.PROGRESS_ALIGNMENT_KEY] = alignment
            props = _push(**settings_over)
            assert props["ctrlHeld"] is expected, (alignment, ctrl_down, visibility)


def test_RECORDED_ctrl_gate_under_vertical_plus_fixed_the_minimap_anchor_case(monkeypatch):
    # RECORDED OBSERVATION, not an endorsed design -- raised by review, not chosen by us. The
    # maintainer owns any deliberate change to what Minimap-anchored placement should do; this
    # only pins what the code does TODAY so a future renumbering fails loudly instead of silently
    # changing behaviour.
    #
    # mod_settings.py:441-442 PROGRESS_ALIGN_FIXED = 0 / PROGRESS_ALIGN_FREE = 1 (the STORED
    # alignment setting) vs. mod_settings.py:452-453 PROGRESS_ALIGN_DAMAGE_LOG = 0 /
    # PROGRESS_ALIGN_MINIMAP = 1 (bar_window._resolve's INTERNAL anchor selector, picked purely by
    # Orientation when alignment is Fixed -- Vertical -> Minimap). Two vocabularies really do
    # share the value 1.
    #
    # It does NOT reach _ctrl_relevant(): that gate (like BarHost.drag()'s) reads
    # progress_bar_alignment() itself -- the STORED key, ceiling PROGRESS_ALIGN_FREE == 1 -- never
    # a locally-resolved "anchor" variable that could hold PROGRESS_ALIGN_MINIMAP. Fixed+Vertical
    # still stores PROGRESS_ALIGN_FIXED (0); "Minimap" only ever exists as _resolve's internal
    # choice of WHERE Fixed anchors, not as a value progress_bar_alignment() can return. So a
    # vertical bar under Fixed alignment -- the configuration that resolves to the Minimap anchor
    # -- gates Ctrl exactly like any other Fixed configuration: OFF.
    monkeypatch.setattr(battle_bridge, "_ctrl_held", True)
    props = _push(**{mod_settings.PROGRESS_ALIGNMENT_KEY: mod_settings.PROGRESS_ALIGN_FIXED,
                     mod_settings.PROGRESS_ORIENTATION_KEY: mod_settings.PROGRESS_ORIENT_VERTICAL})
    assert props["ctrlHeld"] is False


def test_ctrl_relevant_actually_consults_alignment_every_call(monkeypatch):
    # A gate that got short-circuited (e.g. cached the alignment once, or a fail-soft branch that
    # never calls through at all) would look identical to a working one on a single push's value
    # -- assert the CALL COUNT so a no-op mutation here cannot pass silently.
    calls = []
    real_alignment = mod_settings.progress_bar_alignment

    def _spy():
        calls.append(1)
        return real_alignment()

    monkeypatch.setattr(mod_settings, "progress_bar_alignment", _spy)
    monkeypatch.setattr(battle_bridge, "_ctrl_held", True)
    assert battle_bridge._ctrl_relevant() is False   # default settings: Fixed
    assert len(calls) == 1
    mod_settings._apply({mod_settings.PROGRESS_ALIGNMENT_KEY: mod_settings.PROGRESS_ALIGN_FREE})
    assert battle_bridge._ctrl_relevant() is True
    assert len(calls) == 2
    # Ctrl not down at all -- must short-circuit and never even read alignment.
    monkeypatch.setattr(battle_bridge, "_ctrl_held", False)
    assert battle_bridge._ctrl_relevant() is False
    assert len(calls) == 2


def test_push_derives_has_data_from_mark_axis_not_the_display_floor():
    # THE invariant: hasData is mark_axis's own verdict, computed BEFORE axisLo is overwritten
    # with the display floor (progress_axis_lo). A rewrite that instead compared the PUSHED
    # axisLo/axisHi would read this exact case as "no data", because the display floor can
    # legitimately land anywhere below axisHi -- including, in this crafted case, right at it.
    import moe_calculator.bridge.battle_bridge as _bb

    real_axis_lo = _bb.progress_axis_lo
    try:
        _bb.progress_axis_lo = lambda axis_hi, pre_avg: axis_hi
        props = _push()
    finally:
        _bb.progress_axis_lo = real_axis_lo
    assert props["hasData"] is True
    assert props["axisLo"] == props["axisHi"]


# --- the "(73.84%)" caption: curPercent, with the Show MoE % setting folded into the -1 sentinel ---

def _push_model(model, **settings_over):
    if settings_over:
        mod_settings._apply(settings_over)
    vm = _FakeVM()
    battle_bridge.push_progress(vm, _snap(), model)
    return vm.props


def test_cur_percent_is_the_models_live_percent_as_a_real():
    # The value the corner overlay shows, passed through untouched (a float: the slot is Real).
    assert _push()["curPercent"] == 74.3


def test_cur_percent_is_minus_one_without_data():
    assert _push_model(_model(has_data=False))["curPercent"] == -1.0


def test_cur_percent_is_minus_one_when_the_setting_is_off_even_with_data():
    props = _push_model(_model(), **{mod_settings.PROGRESS_SHOW_PERCENT_KEY: False})
    assert props["curPercent"] == -1.0


def test_cur_percent_zero_is_a_real_percentile_not_the_sentinel():
    assert _push_model(_model(cur_percent=0.0))["curPercent"] == 0.0


def test_the_show_percent_flag_is_never_pushed_under_its_own_name():
    props = _push()
    assert "showPercent" not in props and mod_settings.PROGRESS_SHOW_PERCENT_KEY not in props


def test_the_de_show_percent_key_does_not_gate_the_ma_percent():
    props = _push_model(_model(), **{mod_settings.PROGRESS_SHOW_PERCENT_KEY: True,
                                     mod_settings.EFFICIENCY_SHOW_PERCENT_KEY: False})
    assert props["curPercent"] == 74.3


def test_show_delta_is_the_progress_show_delta_setting_default_true():
    assert _push()["showDelta"] is True


def test_show_delta_pushes_false_when_the_setting_is_off():
    props = _push(**{mod_settings.PROGRESS_SHOW_DELTA_KEY: False,
                     mod_settings.EFFICIENCY_SHOW_DELTA_KEY: True})
    assert props["showDelta"] is False
