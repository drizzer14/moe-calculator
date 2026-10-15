# -*- coding: utf-8 -*-
"""Engine-free tests for the battle bridge's prediction<->outcome recorder seam.

`_note_prediction` (called from push) picks the battle's prediction of record and
`_flush_prediction` (called from _on_teardown) coerces it to plain JSON scalars and hands it to
adapter/sample_log. Both are pure module-state logic, so -- mirroring test_gameface_bridge's
documented fake-game-symbol technique -- we install bare stub modules for the game imports
battle_bridge pulls in transitively (frameworks.wulf, gui.impl.pub, openwg_gameface; BigWorld
and CurrentVehicle come from conftest), then drive the two functions directly and spy on
sample_log.stash. The push/teardown WIRING itself needs the live client and is out of scope.
"""
import json
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


class _Permissive(object):
    """Stands in for a Wulf/WG base class: subclassable and constructible with anything."""
    def __init__(self, *a, **k):
        pass


_stub("frameworks.wulf", ViewModel=_Permissive, Array=_Permissive, ViewSettings=_Permissive,
      ViewFlags=object(), WindowFlags=object(), WindowLayer=object(), PositionAnchor=object())
_stub("gui.impl.pub", ViewImpl=_Permissive, WindowImpl=_Permissive)
_stub("openwg_gameface",
      gf_mod_inject=lambda *a, **k: None)

from moe_calculator.adapter import sample_log
from moe_calculator.bridge import battle_bridge
from moe_calculator.domain import battle_types as bt
from moe_calculator.domain.constants import EWMA_K


def setup_function(_):
    battle_bridge._last_prediction = None
    battle_bridge._last_final_push = None
    battle_bridge._died = False


teardown_function = setup_function


class _EngineNum(object):
    """A game-side numeric value object: int()/float()-able but NOT JSON-serializable. Any of
    these reaching the log would be a leak (json.dumps would raise inside the recorder)."""
    def __init__(self, value):
        self._value = value

    def __int__(self):
        return int(self._value)

    def __float__(self):
        return float(self._value)

    def __repr__(self):
        return "<engine %r>" % (self._value,)


class _EngineStr(object):
    def __init__(self, value):
        self._value = value

    def __str__(self):
        return str(self._value)


def _snap(**over):
    """A battle snapshot whose every numeric/string field is an ENGINE object, so the coercion
    in _flush_prediction is what makes the payload serializable."""
    kwargs = dict(
        vehicle_int_cd=1073, nation="germany",
        damage=_EngineNum(2400), assist=_EngineNum(400), stun=_EngineNum(0),
        track_assist=_EngineNum(300), spot_assist=_EngineNum(100),
        team_damage=_EngineNum(0),
        pre_avg_damage=_EngineNum(1850), pre_percentile=_EngineNum(73.67),
        thresholds={65: 2544, 85: 3634, 95: 4512, 100: 5229},
        has_vehicle=True, in_battle=True, is_spectating=False, baseline_known=True,
    )
    kwargs.update(over)
    return bt.BattleSnapshot(**kwargs)


def _model(**over):
    kwargs = dict(
        combined_damage=_EngineNum(2700), proj_avg_damage=_EngineNum(1867),
        cur_percent=_EngineNum(74.30), pct_delta=_EngineNum(0.63),
        has_data=True, has_baseline=True,
        counted_assist=_EngineNum(300), assist_kind=_EngineStr("track"),
    )
    kwargs.update(over)
    return bt.BattleMoEModel(**kwargs)


def _spy_stash(monkeypatch):
    """Replace sample_log.stash with a recorder and return the list of payloads it received."""
    payloads = []
    monkeypatch.setattr(battle_bridge.sample_log, "stash",
                        lambda pred: payloads.append(pred) or True)
    return payloads


# --- _note_prediction: which push becomes the prediction of record -----------

def test_last_valid_push_wins(monkeypatch):
    payloads = _spy_stash(monkeypatch)
    battle_bridge._note_prediction(_snap(), _model(combined_damage=_EngineNum(1000)))
    battle_bridge._note_prediction(_snap(), _model(combined_damage=_EngineNum(2700)))
    battle_bridge._flush_prediction()
    assert payloads[0]["combined_damage"] == 2700


def test_spectating_push_never_becomes_a_prediction(monkeypatch):
    payloads = _spy_stash(monkeypatch)
    battle_bridge._note_prediction(_snap(is_spectating=True), _model())
    battle_bridge._flush_prediction()
    assert payloads == []


def test_spectating_push_does_not_clobber_an_earlier_valid_one(monkeypatch):
    # Postmortem free-look follows another tank while the stats stay ours -> the readout is
    # bogus. The last push that was genuinely OURS is the one that must be graded.
    payloads = _spy_stash(monkeypatch)
    battle_bridge._note_prediction(_snap(), _model(cur_percent=_EngineNum(74.30)))
    battle_bridge._note_prediction(_snap(is_spectating=True), _model(cur_percent=_EngineNum(9.9)))
    battle_bridge._flush_prediction()
    assert payloads[0]["predicted_percent"] == 74.30


def test_no_vehicle_push_never_becomes_a_prediction(monkeypatch):
    payloads = _spy_stash(monkeypatch)
    battle_bridge._note_prediction(_snap(has_vehicle=False), _model())
    battle_bridge._flush_prediction()
    assert payloads == []


def test_unreadable_int_cd_push_never_becomes_a_prediction(monkeypatch):
    payloads = _spy_stash(monkeypatch)
    battle_bridge._note_prediction(_snap(vehicle_int_cd=0), _model())
    battle_bridge._flush_prediction()
    assert payloads == []


def test_note_prediction_never_raises_into_the_push(monkeypatch):
    _spy_stash(monkeypatch)
    battle_bridge._note_prediction(object(), None)   # no snapshot attributes at all
    assert battle_bridge._last_prediction is None
    assert battle_bridge._last_final_push is None


# --- the trailing push: instrumenting post-mortem credit ---------------------
# Dying mid-battle makes our state AT DEATH the prediction of record, but WG keeps crediting us
# afterwards (burn damage from our fires, stun from a landed shell) and the dossier ground truth
# includes it. So the payload also carries the battle's LAST push, spectating included: equal to
# the prediction => post-mortem credit is a non-issue, divergent => the death path under-predicts.

def test_final_columns_carry_the_post_death_spectating_push(monkeypatch):
    payloads = _spy_stash(monkeypatch)
    battle_bridge._note_prediction(_snap(), _model())                       # alive, at death
    battle_bridge._note_prediction(_snap(is_spectating=True),               # burn damage lands
                                   _model(combined_damage=_EngineNum(2900),
                                          cur_percent=_EngineNum(74.55)))
    battle_bridge._flush_prediction()
    payload = payloads[0]
    assert payload["combined_damage"] == 2700 and payload["predicted_percent"] == 74.30
    assert payload["final_combined_damage"] == 2900
    assert payload["final_percent"] == 74.55
    assert isinstance(payload["final_combined_damage"], int)
    assert isinstance(payload["final_percent"], float)


def test_final_columns_equal_the_prediction_when_nothing_followed(monkeypatch):
    # Survived to the end (or push simply stops at death): the two agree, which is itself the
    # answer we're collecting.
    payloads = _spy_stash(monkeypatch)
    battle_bridge._note_prediction(_snap(), _model())
    battle_bridge._flush_prediction()
    payload = payloads[0]
    assert payload["final_combined_damage"] == payload["combined_damage"]
    assert payload["final_percent"] == payload["predicted_percent"]


def test_final_columns_omitted_when_the_trailing_push_is_another_tank(monkeypatch):
    # A spectated ally's intCD would make the trailing readout meaningless -> drop the columns
    # rather than log a number from the wrong vehicle.
    payloads = _spy_stash(monkeypatch)
    battle_bridge._note_prediction(_snap(), _model())
    battle_bridge._note_prediction(_snap(vehicle_int_cd=2049, is_spectating=True),
                                   _model(combined_damage=_EngineNum(9999)))
    battle_bridge._flush_prediction()
    assert "final_combined_damage" not in payloads[0]
    assert "final_percent" not in payloads[0]
    # `died` is the one trailing column the bridge writes unconditionally, so it stays.
    assert set(payloads[0]) == set(sample_log._PRED_KEYS) | {"died"}


def test_the_trailing_push_never_becomes_the_prediction_of_record(monkeypatch):
    # The whole point: instrument the question, don't change which push is graded.
    payloads = _spy_stash(monkeypatch)
    battle_bridge._note_prediction(_snap(), _model(cur_percent=_EngineNum(74.30)))
    battle_bridge._note_prediction(_snap(is_spectating=True), _model(cur_percent=_EngineNum(9.9)))
    battle_bridge._flush_prediction()
    assert payloads[0]["predicted_percent"] == 74.30


def test_flush_resets_the_trailing_push_too(monkeypatch):
    # A stale trailing push must not leak into the NEXT battle's payload.
    _spy_stash(monkeypatch)
    battle_bridge._note_prediction(_snap(), _model())
    battle_bridge._flush_prediction()
    assert battle_bridge._last_final_push is None


def test_a_spectate_only_battle_stashes_nothing(monkeypatch):
    # A trailing push alone is not a prediction -- no prediction of record, no row.
    payloads = _spy_stash(monkeypatch)
    battle_bridge._note_prediction(_snap(is_spectating=True), _model())
    battle_bridge._flush_prediction()
    assert payloads == []
    assert battle_bridge._last_final_push is None


# --- the `died` column: which event marks a death, and its per-battle reset ---
# `died` splits the final_* shortfall into "the death path specifically" vs "end-of-battle server
# accounting in general", so it must mean exactly "WE died in THIS battle".

def _fire(event_attr):
    """Invoke whatever handler _LISTENERS wires to <event_attr>. Driving the registry (not the
    handler function) is what pins the WIRING -- which event marks a death. Engine-free: the
    handlers only re-push, and refresh() early-returns with no window open."""
    handler, = [h for _label, _holder, attr, h in battle_bridge._LISTENERS if attr == event_attr]
    handler()


def test_died_is_true_when_the_postmortem_event_fired(monkeypatch):
    payloads = _spy_stash(monkeypatch)
    battle_bridge._note_prediction(_snap(), _model())
    _fire("onPostMortemSwitched")
    battle_bridge._flush_prediction()
    assert payloads[0]["died"] is True


def test_died_is_false_when_the_postmortem_event_never_fired(monkeypatch):
    payloads = _spy_stash(monkeypatch)
    battle_bridge._note_prediction(_snap(), _model())
    battle_bridge._flush_prediction()
    assert payloads[0]["died"] is False


def test_taking_control_at_battle_start_is_not_a_death(monkeypatch):
    # onVehicleControlling also fires on a normal battle-start mount, so it must NOT mark the
    # flag -- wiring it there would log died=True for EVERY battle, survived ones included.
    payloads = _spy_stash(monkeypatch)
    _fire("onVehicleControlling")
    battle_bridge._note_prediction(_snap(), _model())
    battle_bridge._flush_prediction()
    assert payloads[0]["died"] is False


def test_a_death_cannot_mark_the_next_battle(monkeypatch):
    # THE leak guard. Battle N dies but leaves no prediction of record (spectate-only join, an
    # unreadable vehicle), so its flush hits the `pair is None` early return. Battle N+1 must
    # still log died=False -- i.e. the reset lives ABOVE that return, not below it.
    payloads = _spy_stash(monkeypatch)
    _fire("onPostMortemSwitched")
    battle_bridge._flush_prediction()                          # battle N: nothing to stash
    assert payloads == []
    battle_bridge._note_prediction(_snap(), _model())          # battle N+1, survived
    battle_bridge._flush_prediction()
    assert payloads[0]["died"] is False


# --- _flush_prediction: coercion + once-per-battle reset ---------------------

def test_payload_is_json_serializable_plain_scalars(monkeypatch):
    payloads = _spy_stash(monkeypatch)
    battle_bridge._note_prediction(_snap(), _model())
    battle_bridge._flush_prediction()
    payload = payloads[0]
    json.dumps(payload)                              # no game object survived the coercion
    for key, value in payload.items():
        assert isinstance(value, (bool, int, float, str, dict)), (key, value)
        if isinstance(value, dict):
            assert all(isinstance(v, (bool, int, float, str)) for v in value.values()), key


def test_payload_coerces_each_field_to_its_declared_type(monkeypatch):
    payloads = _spy_stash(monkeypatch)
    battle_bridge._note_prediction(_snap(), _model())
    battle_bridge._flush_prediction()
    payload = payloads[0]
    assert payload["int_cd"] == 1073 and isinstance(payload["int_cd"], int)
    assert payload["damage"] == 2400 and isinstance(payload["damage"], int)
    assert payload["track_assist"] == 300 and payload["spot_assist"] == 100
    assert payload["stun"] == 0 and payload["team_damage"] == 0
    assert payload["combined_damage"] == 2700 and payload["counted_assist"] == 300
    assert payload["proj_avg_damage"] == 1867
    assert payload["pre_avg_damage"] == 1850 and isinstance(payload["pre_avg_damage"], int)
    assert payload["pre_percentile"] == 73.67 and isinstance(payload["pre_percentile"], float)
    assert payload["predicted_percent"] == 74.30 and payload["pct_delta"] == 0.63
    assert payload["assist_kind"] == "track" and isinstance(payload["assist_kind"], str)
    assert payload["has_data"] is True and payload["has_baseline"] is True
    assert payload["baseline_known"] is True
    assert payload["ewma_k"] == float(EWMA_K)


def test_payload_keys_are_exactly_the_recorders_schema(monkeypatch):
    # The bridge is the recorder's only producer: any field added on one side without the other
    # would silently log a null column (or drop a field) -- pin them together.
    payloads = _spy_stash(monkeypatch)
    battle_bridge._note_prediction(_snap(), _model())
    battle_bridge._flush_prediction()
    assert set(payloads[0]) == set(sample_log._PRED_KEYS + sample_log._FINAL_KEYS)


def test_thresholds_are_copied_as_a_plain_dict(monkeypatch):
    payloads = _spy_stash(monkeypatch)
    snap = _snap()
    battle_bridge._note_prediction(snap, _model())
    battle_bridge._flush_prediction()
    assert payloads[0]["thresholds"] == {65: 2544, 85: 3634, 95: 4512, 100: 5229}
    assert payloads[0]["thresholds"] is not snap.thresholds     # a copy, not the live table


def test_flush_resets_so_a_second_teardown_writes_nothing(monkeypatch):
    payloads = _spy_stash(monkeypatch)
    battle_bridge._note_prediction(_snap(), _model())
    battle_bridge._flush_prediction()
    battle_bridge._flush_prediction()                          # e.g. a repeated teardown event
    assert len(payloads) == 1
    assert battle_bridge._last_prediction is None


def test_flush_without_a_prediction_is_a_noop(monkeypatch):
    payloads = _spy_stash(monkeypatch)
    battle_bridge._flush_prediction()                          # spectated / aborted battle
    assert payloads == []


def test_flush_never_raises_into_the_teardown(monkeypatch):
    def boom(_pred):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(battle_bridge.sample_log, "stash", boom)
    battle_bridge._note_prediction(_snap(), _model())
    battle_bridge._flush_prediction()                          # must not raise
    assert battle_bridge._last_prediction is None


def test_flush_clears_state_even_when_coercion_fails(monkeypatch):
    # A model field that can't be coerced must not leave the stale pair armed for the NEXT
    # battle's teardown (which would log the wrong battle's prediction).
    payloads = _spy_stash(monkeypatch)
    battle_bridge._note_prediction(_snap(), _model(combined_damage=object()))
    battle_bridge._flush_prediction()
    assert payloads == []
    assert battle_bridge._last_prediction is None
