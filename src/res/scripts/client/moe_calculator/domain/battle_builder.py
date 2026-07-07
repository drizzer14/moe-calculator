# -*- coding: utf-8 -*-
"""Turn a BattleSnapshot into a BattleMoEModel. Pure and engine-free.

The four in-battle readouts (see TASKS/in-battle-moe-panel.md):
  1. live combined damage  C = damage + max(assist, stun) - team_damage   (WG #15060: MAX)
  2. projected moving-average combined damage  avgWithCD = prevAvg + k*(C - prevAvg)  (EWMA)
  3. current percent  = the MoE percentile of avgWithCD, interpolated over the per-tank
     combined-damage stops [(0,0),(65,D1),(85,D2),(95,D3),(100,D100)]
  4. percent delta    = current percent - pre-battle standing percentile   (signed)

Metrics 2-4 ride on the EWMA coefficient k (community-reverse-engineered, not WG-confirmed);
metric 1 can over-count when a tank earns both spot AND track assist (merged live).
"""
from moe_calculator.domain import battle_types as bt
from moe_calculator.domain.constants import EWMA_K, MARK_PERCENTS


def _clamp(value, lo, hi):
    return lo if value < lo else hi if value > hi else value


def combined_damage(damage, assist, stun, team_damage):
    """Live combined damage: direct + MAX(assist, stun) - team damage, clamped >= 0.

    MAX (not sum) of the assist streams per WG support #15060."""
    c = (int(damage or 0)
         + max(int(assist or 0), int(stun or 0))
         - int(team_damage or 0))
    return c if c > 0 else 0


def _threshold_stops(thresholds):
    """Build the (combined_damage, percent) interpolation stops from the per-tank table,
    or return None when the table is unusable (missing keys / non-increasing damage), so
    the caller degrades to 'no percent' instead of dividing by zero.

    Stops: (0, 0), (D1, 65), (D2, 85), (D3, 95), (D100, 100)."""
    if not thresholds:
        return None
    try:
        d1 = int(thresholds.get(1, 0) or 0)
        d2 = int(thresholds.get(2, 0) or 0)
        d3 = int(thresholds.get(3, 0) or 0)
        d100 = int(thresholds.get(100, 0) or 0)
    except (TypeError, ValueError, AttributeError):
        return None
    p1, p2, p3 = MARK_PERCENTS  # 65, 85, 95
    stops = [(0, 0.0), (d1, float(p1)), (d2, float(p2)), (d3, float(p3)), (d100, 100.0)]
    # Damage must be strictly increasing across the stops for a well-defined interpolation.
    prev = -1
    for dmg, _pct in stops:
        if dmg <= prev:
            return None
        prev = dmg
    return stops


def _interp_percent(damage, stops):
    """Piecewise-linear map of combined `damage` to percent over the given stops. Assumes
    `stops` is the strictly-increasing list from _threshold_stops. Clamped 0..100."""
    d = float(damage or 0.0)
    if d <= 0:
        return 0.0
    if d >= stops[-1][0]:
        return 100.0
    for i in range(1, len(stops)):
        d_lo, p_lo = stops[i - 1]
        d_hi, p_hi = stops[i]
        if d <= d_hi:
            frac = (d - d_lo) / float(d_hi - d_lo)
            return _clamp(p_lo + frac * (p_hi - p_lo), 0.0, 100.0)
    return 100.0


def damage_to_percent(damage, thresholds):
    """Combined damage -> MoE percentile via the per-tank distribution stops. Returns 0.0
    when the threshold table is missing/unusable (no data source for the percentile)."""
    stops = _threshold_stops(thresholds)
    if stops is None:
        return 0.0
    return _interp_percent(damage, stops)


def ewma_project(prev_avg, cd, k=EWMA_K):
    """Fold this battle's combined damage `cd` into the moving average `prev_avg` one EWMA
    step: prev + k*(cd - prev). Rounded to an integer damage value."""
    prev = float(prev_avg or 0.0)
    return int(round(prev + k * (float(cd or 0) - prev)))


def build_battle_model(snapshot):
    """Compose the four in-battle readouts from the snapshot. Always returns a model;
    visibility is decided separately by battle_bar_visible()."""
    thresholds = snapshot.thresholds or {}
    cd = combined_damage(snapshot.damage, snapshot.assist, snapshot.stun,
                         snapshot.team_damage)
    proj = ewma_project(snapshot.pre_avg_damage, cd)

    stops = _threshold_stops(thresholds)
    has_data = stops is not None
    if has_data:
        cur_percent = _interp_percent(proj, stops)
        pct_delta = cur_percent - float(snapshot.pre_percentile or 0.0)
    else:
        cur_percent = 0.0
        pct_delta = 0.0

    return bt.BattleMoEModel(
        combined_damage=cd,
        proj_avg_damage=proj,
        cur_percent=cur_percent,
        pct_delta=pct_delta,
        has_data=has_data)


def battle_bar_visible(in_battle, has_vehicle):
    """Whether the in-battle overlay should render. Pure/engine-free so it unit-tests on
    plain inputs: a player vehicle must be readable and combat must be active."""
    return bool(has_vehicle) and bool(in_battle)
