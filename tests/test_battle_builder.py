# -*- coding: utf-8 -*-
"""Tests for the engine-free in-battle domain layer. Like test_builder.py these run on
Python 3 (no game engine) because domain/battle_builder imports zero game symbols -- the
in-battle MoE math is pure and unit-testable with the client closed."""
import pytest

from moe_calculator.domain import battle_types as bt
from moe_calculator.domain.battle_builder import (
    combined_damage, counted_assistance, ewma_project,
    build_battle_model, battle_bar_visible, _fit_from_thresholds, _smooth_percent)
from moe_calculator.domain.constants import EWMA_K
from moe_calculator.domain import moe_estimate as me


# A clean threshold set (round numbers) so interpolation asserts stay exact.
_THR = {1: 1000, 2: 2000, 3: 3000, 100: 4000}


def _bsnap(**kw):
    base = dict(vehicle_int_cd=1073, nation="germany", damage=2000, assist=500,
                stun=300, team_damage=0, pre_avg_damage=1800, pre_percentile=70.0,
                thresholds=dict(_THR))
    base.update(kw)
    return bt.BattleSnapshot(**base)


# --- counted_assistance ------------------------------------------------------

def test_counted_assistance_picks_highest_stream():
    assert counted_assistance(700, 400, 300) == (700, "track")   # tracking leads
    assert counted_assistance(400, 700, 300) == (700, "spot")    # spotting leads
    assert counted_assistance(400, 300, 900) == (900, "stun")    # stun leads


def test_counted_assistance_tie_breaks():
    # track vs spot tie -> spotting wins.
    assert counted_assistance(500, 500, 0) == (500, "spot")
    # stun only wins when STRICTLY greater, so a tie keeps the assist stream.
    assert counted_assistance(0, 600, 600) == (600, "spot")
    assert counted_assistance(600, 0, 600) == (600, "track")


def test_counted_assistance_zero_is_generic():
    # Total 0 -> value 0 + generic kind (the row hides in this case).
    assert counted_assistance(0, 0, 0) == (0, "assist")


def test_counted_assistance_merged_fallback_before_split():
    # Split not delivered yet (track/spot 0) but merged assist known -> credit merged as the
    # assist component with the generic 'assist' kind, so combined damage never under-counts.
    assert counted_assistance(0, 0, 0, 800) == (800, "assist")
    # stun still wins when strictly greater than the merged assist.
    assert counted_assistance(0, 0, 900, 800) == (900, "stun")
    # once the real split arrives it takes over from the merged fallback.
    assert counted_assistance(700, 100, 0, 800) == (700, "track")


def test_counted_assistance_handles_none():
    assert counted_assistance(None, None, None) == (0, "assist")


# --- combined_damage ---------------------------------------------------------

def test_combined_damage_takes_max_not_sum():
    # tracking 500 dominates spotting 300 and stun 0 -> +500, NOT +800 (WG #15060: max).
    assert combined_damage(2000, 500, 300, 0, 0) == 2500
    # stun dominates the assist streams
    assert combined_damage(2000, 100, 200, 700, 0) == 2700


def test_combined_damage_subtracts_team_damage():
    assert combined_damage(2000, 500, 0, 0, 300) == 2200


def test_combined_damage_clamps_non_negative():
    assert combined_damage(0, 0, 0, 0, 500) == 0
    assert combined_damage(100, 0, 0, 0, 999) == 0


def test_combined_damage_handles_none():
    assert combined_damage(None, None, None, None, None) == 0


def test_combined_damage_merged_fallback():
    # track/spot 0 but the merged live assist is known -> counted as the assist component.
    assert combined_damage(2000, 0, 0, 0, 0, merged_assist=500) == 2500


# --- smooth curve (_fit_from_thresholds + _smooth_percent) -------------------

def _thr_from_normal(mu, sigma):
    """Build a {1,2,3,100} threshold table whose stops lie exactly on a normal(mu, sigma):
    D1@65th, D2@85th, D3@95th, D100@99th (the goalpost percentile the fit uses)."""
    return {
        1: int(round(mu + sigma * me.inv_norm_cdf(0.65))),
        2: int(round(mu + sigma * me.inv_norm_cdf(0.85))),
        3: int(round(mu + sigma * me.inv_norm_cdf(0.95))),
        100: int(round(mu + sigma * me.inv_norm_cdf(0.99))),
    }


def test_fit_from_thresholds_recovers_marks():
    # A table built from a known normal must map its own stops back to 65/85/95 (and the
    # goalpost to ~99) under the fitted curve.
    thr = _thr_from_normal(1500.0, 800.0)
    mu, sigma = _fit_from_thresholds(thr)
    assert _smooth_percent(thr[1], mu, sigma) == pytest.approx(65.0, abs=0.5)
    assert _smooth_percent(thr[2], mu, sigma) == pytest.approx(85.0, abs=0.5)
    assert _smooth_percent(thr[3], mu, sigma) == pytest.approx(95.0, abs=0.5)
    assert _smooth_percent(thr[100], mu, sigma) == pytest.approx(99.0, abs=0.5)


def test_smooth_curve_tracks_true_percentile_off_mark():
    # At an off-mark damage the fitted normal curve recovers the true percentile closely
    # (the smooth fit is the sole percent path).
    mu, sigma = 1500.0, 800.0
    thr = _thr_from_normal(mu, sigma)
    d75 = int(round(mu + sigma * me.inv_norm_cdf(0.75)))    # true 75th percentile damage
    fmu, fsigma = _fit_from_thresholds(thr)
    assert _smooth_percent(d75, fmu, fsigma) == pytest.approx(75.0, abs=1.0)


def test_fit_from_thresholds_none_for_unusable_tables():
    assert _fit_from_thresholds({}) is None
    assert _fit_from_thresholds(None) is None
    # Non-monotonic (decreasing) damage -> negative slope -> sigma <= 0 -> None.
    assert _fit_from_thresholds({1: 3000, 2: 2000, 3: 1000, 100: 500}) is None


def test_fit_from_thresholds_robust_to_missing_goalpost():
    # A table missing the D100 goalpost (0) still fits from the 3 mark points -- the smooth
    # path is MORE robust than the linear one, which bailed on the non-increasing stop.
    thr = _thr_from_normal(1500.0, 800.0)
    del thr[100]
    fit = _fit_from_thresholds(thr)
    assert fit is not None and fit[1] > 0.0


# --- ewma_project ------------------------------------------------------------

def test_ewma_project_folds_cd_toward_average():
    # prev + k*(cd-prev); k = 2/101. Above-average battle nudges the average up.
    assert ewma_project(2000, 3000) == int(round(2000 + EWMA_K * 1000))   # 2020
    # Below-average battle nudges it down.
    assert ewma_project(2000, 1000) == int(round(2000 + EWMA_K * -1000))  # 1980


def test_ewma_project_honors_explicit_k():
    # An explicit k overrides the community default: prev + k*(cd-prev) with k=0.04.
    assert ewma_project(2000, 3000, 0.04) == int(round(2000 + 0.04 * 1000))   # 2040


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
    # 3) current percent is ANCHORED: pre_percentile + this battle's SMOOTH-curve increment
    # (the primary path for a usable table; see _fit_from_thresholds).
    mu, sigma = _fit_from_thresholds(_THR)
    inc = _smooth_percent(m.proj_avg_damage, mu, sigma) - _smooth_percent(1800, mu, sigma)
    assert inc > 0                                                        # above-avg battle
    assert round(m.cur_percent, 2) == round(70.0 + inc, 2)
    assert m.cur_percent > 70.0
    # 4) delta IS the increment (self-consistent curve scale, not mixed vs WG rating)
    assert round(m.pct_delta, 2) == round(inc, 2)
    assert m.has_data is True


def test_build_battle_model_projects_with_baked_k():
    # The projection uses the baked community EWMA_K default.
    m = build_battle_model(_bsnap())
    assert m.proj_avg_damage == int(round(1800 + EWMA_K * (2500 - 1800)))      # 1814


def test_build_battle_model_anchor_holds_when_proj_equals_pre_avg():
    # If this battle's combined damage equals the career average, the EWMA fold is a no-op
    # (proj == pre_avg), so the increment is exactly 0 and cur_percent sits ON WG's real
    # standing -- the anchor guarantee, independent of the curve's absolute value.
    m = build_battle_model(_bsnap(damage=1800, assist=0, stun=0, team_damage=0,
                                  pre_avg_damage=1800, pre_percentile=73.5))
    assert m.combined_damage == 1800
    assert m.proj_avg_damage == 1800
    assert m.pct_delta == pytest.approx(0.0, abs=1e-9)
    assert m.cur_percent == pytest.approx(73.5, abs=1e-9)


def test_build_battle_model_non_monotone_thresholds_degrade():
    # A non-monotonic table is unusable by the smooth fit (sigma<=0) -> no-percent, never a crash.
    m = build_battle_model(_bsnap(thresholds={1: 3000, 2: 2000, 3: 1000, 100: 500}))
    assert m.has_data is False
    assert m.cur_percent == 0.0
    assert m.pct_delta == 0.0
    assert m.combined_damage == 2500        # raw damage metric still meaningful


def test_build_battle_model_counted_assist_from_split():
    # The split feeds both the counted-assist row and combined damage: max(track, spot, stun),
    # NOT the merged spot+track sum. Here track 900 leads.
    m = build_battle_model(_bsnap(track_assist=900, spot_assist=400, stun=300, assist=1300))
    assert m.counted_assist == 900
    assert m.assist_kind == "track"
    assert m.combined_damage == 2000 + 900       # split max, not the merged 1300


def test_build_battle_model_counted_assist_stun_leads():
    m = build_battle_model(_bsnap(track_assist=100, spot_assist=200, stun=800, assist=300))
    assert m.counted_assist == 800
    assert m.assist_kind == "stun"


def test_build_battle_model_counted_assist_merged_fallback():
    # Split not delivered yet -> value falls back to the merged live assist + generic kind.
    m = build_battle_model(_bsnap(track_assist=0, spot_assist=0, stun=0, assist=600))
    assert m.counted_assist == 600
    assert m.assist_kind == "assist"
    assert m.combined_damage == 2000 + 600


def test_build_battle_model_zero_damage_drags_below_career():
    # No damage yet (cd=0) -> proj = prev*(1-k) < pre_avg -> the folded 0-damage battle
    # drags the anchored percent just below WG's real number (honest 'if it ended now').
    m = build_battle_model(_bsnap(damage=0, assist=0, stun=0,
                                  pre_avg_damage=1800, pre_percentile=84.7))
    assert m.proj_avg_damage == int(round(1800 * (1 - EWMA_K)))           # 1764
    mu, sigma = _fit_from_thresholds(_THR)
    inc = _smooth_percent(m.proj_avg_damage, mu, sigma) - _smooth_percent(1800, mu, sigma)
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


# --- Alt-key visibility semantics (INVERTED) ---------------------------------
# New rule (base guards vehicle/combat/spectating/scoreboard held satisfied):
#   active == enabled and (alt_held if alt_mode else True)
#   - master off              -> never visible.
#   - master on, alt_mode on  -> visible ONLY while Alt held.
#   - master on, alt_mode off -> ALWAYS visible.
# The "Show on Alt Key" child no longer overrides the master; it now GATES an
# already-enabled overlay down to the Alt-held window.

@pytest.mark.parametrize("enabled,alt_mode,alt_held,expected", [
    # master off -> never visible, regardless of alt_mode / alt_held.
    (False, False, False, False),
    (False, False, True,  False),
    (False, True,  False, False),
    (False, True,  True,  False),
    # master on, alt_mode off -> ALWAYS visible (Alt irrelevant).
    (True,  False, False, True),
    (True,  False, True,  True),
    # master on, alt_mode on -> visible ONLY while Alt held.
    (True,  True,  False, False),
    (True,  True,  True,  True),
])
def test_battle_bar_visible_truth_table(enabled, alt_mode, alt_held, expected):
    # Base guards satisfied (in combat, own vehicle, not spectating, no scoreboard).
    assert battle_bar_visible(True, True, enabled=enabled, alt_mode=alt_mode,
                              alt_held=alt_held) is expected


def test_battle_bar_visible_alt_mode_follows_held():
    # Master on + Alt-peek on: the overlay tracks whether Alt is held (INVERTED semantics --
    # the Alt child now GATES the enabled overlay rather than overriding a disabled one).
    assert battle_bar_visible(True, True, enabled=True, alt_mode=True, alt_held=True) is True
    assert battle_bar_visible(True, True, enabled=True, alt_mode=True, alt_held=False) is False


def test_battle_bar_visible_master_off_never_shows_even_on_alt():
    # Master off is the hard gate: neither alt_mode nor a held Alt can reveal the overlay.
    assert battle_bar_visible(True, True, enabled=False, alt_mode=True, alt_held=True) is False
    assert battle_bar_visible(True, True, enabled=False, alt_mode=False, alt_held=True) is False


def test_battle_bar_visible_alt_mode_off_shows_at_all_times():
    # Master on + Alt-peek OFF -> shown at all times; a held Alt makes no difference.
    assert battle_bar_visible(True, True, enabled=True, alt_mode=False, alt_held=False) is True
    assert battle_bar_visible(True, True, enabled=True, alt_mode=False, alt_held=True) is True


def test_battle_bar_visible_alt_mode_still_respects_base_guards():
    # The base guards (vehicle/combat/spectating/scoreboard) override the Alt-held window too:
    # even with the overlay enabled + Alt held, a failing base guard keeps it hidden.
    assert battle_bar_visible(True, False, enabled=True, alt_mode=True, alt_held=True) is False
    assert battle_bar_visible(False, True, enabled=True, alt_mode=True, alt_held=True) is False
    assert battle_bar_visible(True, True, is_spectating=True,
                              enabled=True, alt_mode=True, alt_held=True) is False
    assert battle_bar_visible(True, True, overlay_open=True,
                              enabled=True, alt_mode=True, alt_held=True) is False
