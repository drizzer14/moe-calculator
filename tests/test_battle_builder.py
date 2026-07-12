# -*- coding: utf-8 -*-
"""Tests for the engine-free in-battle domain layer. Like test_builder.py these run on
Python 3 (no game engine) because domain/battle_builder imports zero game symbols -- the
in-battle MoE math is pure and unit-testable with the client closed."""
from moe_calculator.domain import battle_types as bt
from moe_calculator.domain.battle_builder import (
    combined_damage, damage_to_percent, ewma_project, build_battle_model,
    battle_bar_visible)
from moe_calculator.domain.constants import EWMA_K


# A clean threshold set (round numbers) so interpolation asserts stay exact.
_THR = {1: 1000, 2: 2000, 3: 3000, 100: 4000}


def _bsnap(**kw):
    base = dict(vehicle_int_cd=1073, nation="germany", damage=2000, assist=500,
                stun=300, team_damage=0, pre_avg_damage=1800, pre_percentile=70.0,
                thresholds=dict(_THR))
    base.update(kw)
    return bt.BattleSnapshot(**base)


# --- combined_damage ---------------------------------------------------------

def test_combined_damage_takes_max_not_sum():
    # assist 500 dominates stun 300 -> +500, NOT +800 (WG #15060: max of streams).
    assert combined_damage(2000, 500, 300, 0) == 2500
    # stun dominates
    assert combined_damage(2000, 100, 700, 0) == 2700


def test_combined_damage_subtracts_team_damage():
    assert combined_damage(2000, 500, 0, 300) == 2200


def test_combined_damage_clamps_non_negative():
    assert combined_damage(0, 0, 0, 500) == 0
    assert combined_damage(100, 0, 0, 999) == 0


def test_combined_damage_handles_none():
    assert combined_damage(None, None, None, None) == 0


# --- damage_to_percent -------------------------------------------------------

def test_damage_to_percent_exact_at_stops():
    assert damage_to_percent(1000, _THR) == 65.0
    assert damage_to_percent(2000, _THR) == 85.0
    assert damage_to_percent(3000, _THR) == 95.0
    assert damage_to_percent(4000, _THR) == 100.0


def test_damage_to_percent_interpolates_midpoints():
    assert damage_to_percent(500, _THR) == 32.5     # halfway 0..D1 -> 0..65
    assert damage_to_percent(1500, _THR) == 75.0    # halfway D1..D2 -> 65..85
    assert damage_to_percent(3500, _THR) == 97.5    # halfway D3..D100 -> 95..100


def test_damage_to_percent_clamps():
    assert damage_to_percent(0, _THR) == 0.0
    assert damage_to_percent(-100, _THR) == 0.0
    assert damage_to_percent(9999, _THR) == 100.0   # at/above D100


def test_damage_to_percent_no_thresholds():
    assert damage_to_percent(2000, {}) == 0.0
    assert damage_to_percent(2000, None) == 0.0


def test_damage_to_percent_partial_or_degenerate_thresholds():
    # Missing stops (would break monotonicity) -> unusable -> 0.0, never a div-by-zero.
    assert damage_to_percent(2000, {1: 1000}) == 0.0
    # Non-monotonic damage -> unusable -> 0.0
    assert damage_to_percent(2000, {1: 2000, 2: 1000, 3: 3000, 100: 4000}) == 0.0


# --- ewma_project ------------------------------------------------------------

def test_ewma_project_folds_cd_toward_average():
    # prev + k*(cd-prev); k = 2/101. Above-average battle nudges the average up.
    assert ewma_project(2000, 3000) == int(round(2000 + EWMA_K * 1000))   # 2020
    # Below-average battle nudges it down.
    assert ewma_project(2000, 1000) == int(round(2000 + EWMA_K * -1000))  # 1980


def test_ewma_project_new_tank_zero_baseline():
    assert ewma_project(0, 3000) == int(round(EWMA_K * 3000))             # 59


def test_ewma_project_zero_cd_folds_below_baseline():
    # A 0-damage battle-so-far IS folded: proj = prev*(1-k), the honest 'if it ended now'
    # projection that opens just below career and climbs as damage accrues.
    assert ewma_project(1800, 0) == int(round(1800 * (1 - EWMA_K)))       # 1764
    assert ewma_project(2000, 0) == int(round(2000 * (1 - EWMA_K)))       # 1960
    assert ewma_project(0, 0) == 0


# --- build_battle_model ------------------------------------------------------

def test_build_battle_model_four_metrics():
    m = build_battle_model(_bsnap())
    # 1) live combined damage: 2000 + max(500,300) - 0
    assert m.combined_damage == 2500
    # 2) projected average: 1800 + k*(2500-1800)
    assert m.proj_avg_damage == int(round(1800 + EWMA_K * 700))           # 1814
    # 3) current percent is ANCHORED: pre_percentile + this battle's interp increment.
    inc = damage_to_percent(m.proj_avg_damage, _THR) - damage_to_percent(1800, _THR)
    assert inc > 0                                                        # above-avg battle
    assert round(m.cur_percent, 2) == round(70.0 + inc, 2)
    assert m.cur_percent > 70.0
    # 4) delta IS the increment (self-consistent interp scale, not mixed vs WG rating)
    assert round(m.pct_delta, 2) == round(inc, 2)
    assert m.has_data is True


def test_build_battle_model_zero_damage_drags_below_career():
    # No damage yet (cd=0) -> proj = prev*(1-k) < pre_avg -> the folded 0-damage battle
    # drags the anchored percent just below WG's real number (honest 'if it ended now').
    m = build_battle_model(_bsnap(damage=0, assist=0, stun=0,
                                  pre_avg_damage=1800, pre_percentile=84.7))
    assert m.proj_avg_damage == int(round(1800 * (1 - EWMA_K)))           # 1764
    inc = damage_to_percent(m.proj_avg_damage, _THR) - damage_to_percent(1800, _THR)
    assert inc < 0                                                        # 0-damage drags down
    assert round(m.cur_percent, 2) == round(84.7 + inc, 2)
    assert m.cur_percent < 84.7
    assert round(m.pct_delta, 2) == round(inc, 2)


def test_build_battle_model_clamps_cur_percent_to_100():
    # High standing + a monster battle would push pre_percentile + increment over 100.
    m = build_battle_model(_bsnap(damage=99999, assist=0, stun=0,
                                  pre_avg_damage=1800, pre_percentile=99.0))
    assert m.cur_percent == 100.0


def test_build_battle_model_nan_pre_percentile_clamps():
    # A NaN pre_percentile must be clamped to the low bound, not passed through: NaN compares
    # False against the clamp bounds, so the naive clamp would leak NaN into cur_percent.
    m = build_battle_model(_bsnap(pre_percentile=float("nan")))
    assert m.cur_percent == m.cur_percent  # not NaN
    assert 0.0 <= m.cur_percent <= 100.0


def test_build_battle_model_no_thresholds_degrades():
    m = build_battle_model(_bsnap(thresholds={}))
    assert m.has_data is False
    assert m.cur_percent == 0.0
    assert m.pct_delta == 0.0
    # the raw damage metrics are still meaningful without the percentile table
    assert m.combined_damage == 2500


def test_build_battle_model_has_baseline_true_with_career_standing():
    # Normal garage->battle flow: a real baseline is present -> the projected metrics are valid.
    assert build_battle_model(_bsnap()).has_baseline is True
    # Either half of the baseline alone is enough.
    assert build_battle_model(_bsnap(pre_avg_damage=1800, pre_percentile=0.0)).has_baseline is True
    assert build_battle_model(_bsnap(pre_avg_damage=0, pre_percentile=70.0)).has_baseline is True


def test_build_battle_model_no_baseline_flags_empty_replay():
    # BUG B: replay / relogin straight into battle -> the garage dossier was never read, so
    # the baseline comes back empty AND the tank was never marked seen (baseline_known False).
    # The model must FLAG this (has_baseline False) so the overlay dashes out the collapsed
    # proj/percent/delta instead of showing garbage. The live combined damage stays meaningful.
    m = build_battle_model(_bsnap(pre_avg_damage=0, pre_percentile=0.0, baseline_known=False,
                                  damage=2000, assist=0, stun=0))
    assert m.has_baseline is False
    assert m.combined_damage == 2000            # live CD still correct + shown
    assert m.has_data is True                   # thresholds are fine; only the baseline is missing


def test_build_battle_model_has_baseline_when_first_battle_zero_career():
    # First-ever battle in a freshly-bought tank: pre_avg/pre_percentile are a GENUINE 0
    # (the garage read the tank this session -> baseline_known True). 0 is the true baseline,
    # so the projection is well-defined and must NOT dash: has_baseline True, and the live
    # percent climbs from ~0 as damage accrues.
    m = build_battle_model(_bsnap(pre_avg_damage=0, pre_percentile=0.0, baseline_known=True,
                                  damage=2000, assist=0, stun=0))
    assert m.has_baseline is True
    assert m.has_data is True
    # proj = ewma_project(0, cd) = k*cd > 0; cur_percent anchors on 0 and climbs.
    assert m.proj_avg_damage > 0
    assert m.cur_percent > 0.0
    assert m.pct_delta > 0.0


def test_build_battle_model_baseline_known_alone_is_enough():
    # Even with no live damage yet, a known-genuine-0 baseline still counts as a baseline
    # (the overlay shows a real 0.x% opening, not a dash).
    m = build_battle_model(_bsnap(pre_avg_damage=0, pre_percentile=0.0, baseline_known=True,
                                  damage=0, assist=0, stun=0))
    assert m.has_baseline is True


def test_build_battle_model_negative_delta():
    # a weak battle projects below standing -> negative increment -> cur_percent dips below
    # the anchored pre_percentile
    m = build_battle_model(_bsnap(damage=100, assist=0, stun=0, pre_percentile=90.0))
    assert m.pct_delta < 0
    assert m.cur_percent < 90.0


# --- battle_bar_visible ------------------------------------------------------

def test_battle_bar_visible_gates():
    assert battle_bar_visible(True, True) is True
    assert battle_bar_visible(False, True) is False    # not in combat yet
    assert battle_bar_visible(True, False) is False     # no player vehicle


def test_battle_bar_visible_hidden_while_spectating():
    # After death, spectating a teammate: identity/thresholds follow the observed vehicle
    # while the damage stats stay ours -> a nonsense readout. Hide it.
    assert battle_bar_visible(True, True, is_spectating=True) is False
    # Alive (controlling own vehicle) -> visible.
    assert battle_bar_visible(True, True, is_spectating=False) is True
    # Default arg preserves prior behavior (never wrongly hides when the flag is absent).
    assert battle_bar_visible(True, True) is True


def test_battle_bar_visible_hidden_while_scoreboard_open():
    # Any full-stats scoreboard overlay (Tab / personal missions / reserves) is open ->
    # hide the readout so it doesn't clutter the full-screen scoreboard. Hard override:
    # hides even an otherwise-visible, alive, in-combat readout.
    assert battle_bar_visible(True, True, overlay_open=True) is False
    # Closed (default) preserves prior behavior.
    assert battle_bar_visible(True, True, overlay_open=False) is True
    assert battle_bar_visible(True, True) is True


def test_battle_bar_visible_overlay_never_reveals_hidden_case():
    # A closed scoreboard must not flip an already-hidden case visible: no vehicle / not in
    # combat / spectating all stay hidden regardless of the overlay flag.
    assert battle_bar_visible(True, False, overlay_open=False) is False   # no vehicle
    assert battle_bar_visible(False, True, overlay_open=False) is False   # not in combat
    assert battle_bar_visible(True, True, is_spectating=True, overlay_open=False) is False


def test_battle_bar_visible_disabled_setting_hides():
    # "Battle Widget Enabled" off is a hard override: hides an otherwise-visible overlay.
    assert battle_bar_visible(True, True, enabled=False) is False
    # Default (enabled) preserves prior behavior.
    assert battle_bar_visible(True, True, enabled=True) is True
    assert battle_bar_visible(True, True) is True
