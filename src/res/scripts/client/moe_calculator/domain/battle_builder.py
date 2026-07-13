# -*- coding: utf-8 -*-
"""Turn a BattleSnapshot into a BattleMoEModel. Pure and engine-free.

The four in-battle readouts (see TASKS/in-battle-moe-panel.md):
  1. live combined damage  C = damage + max(track, spot, stun) - team_damage   (WG #15060: MAX)
  2. projected moving-average combined damage  avgWithCD = prevAvg + k*(C - prevAvg)  (EWMA)
  3. current percent  = the MoE percentile of avgWithCD, interpolated over the per-tank
     combined-damage stops [(0,0),(65,D1),(85,D2),(95,D3),(100,D100)]
  4. percent delta    = current percent - pre-battle standing percentile   (signed)

Metrics 2-4 ride on the EWMA coefficient k (community-reverse-engineered, not WG-confirmed).
The assist component of combined damage is the HIGHER of tracking / spotting / stun (see
counted_assistance) -- WG credits the greatest stream, not the sum; the server battle-events
summary supplies the track/spot split (adapter/battle_adapter._read_assist_split).
"""
from moe_calculator.domain import battle_types as bt
from moe_calculator.domain.constants import EWMA_K, MARK_PERCENTS
from moe_calculator.domain.rounding import iround_half_away


def _clamp(value, lo, hi):
    # NaN compares False against everything, so the bare comparisons below would pass it
    # through unclamped and propagate NaN to the widget. Treat NaN as the low bound.
    if value != value:
        return lo
    return lo if value < lo else hi if value > hi else value


def counted_assistance(track, spot, stun, merged_assist=0):
    """The single assist stream that counts toward MoE this battle, and which one it is.

    MoE credits the HIGHER of assisted damage vs stun (not their sum) -- and within assisted
    damage, the higher of tracking vs spotting (not their sum). So the counted value is
    max(track, spot, stun); `kind` is whichever wins, and selects the overlay row's icon.

    `merged_assist` is the personal-efficiency controller's spot+track MERGED total, used only
    as a fallback: before the server split summary is delivered (battle start), track and spot
    are both 0 while merged_assist may already be > 0. In that window we credit merged_assist as
    the assist component (kind 'assist', generic icon) so combined damage never under-counts.

    Returns (value, kind), kind in {'track', 'spot', 'stun', 'assist'}. kind is 'assist' when
    value is 0 (the row hides then). Tie-breaks: stun wins only when strictly greatest; between
    tracking and spotting, spotting wins a tie."""
    t = int(track or 0)
    s = int(spot or 0)
    st = int(stun or 0)
    m = int(merged_assist or 0)
    if t == 0 and s == 0 and m > 0:
        assist_val, assist_kind = m, "assist"
    else:
        assist_val = t if t > s else s
        assist_kind = "track" if t > s else "spot"
    if st > assist_val:
        return st, "stun"
    if assist_val <= 0:
        return 0, "assist"
    return assist_val, assist_kind


def combined_damage(damage, track, spot, stun, team_damage, merged_assist=0):
    """Live combined damage: direct + counted assistance - team damage, clamped >= 0.

    Counted assistance = max(track, spot, stun) -- WG credits the HIGHER assist stream, not the
    sum (support #15060) -- with `merged_assist` as the pre-split fallback (see
    counted_assistance)."""
    counted, _kind = counted_assistance(track, spot, stun, merged_assist)
    c = int(damage or 0) + int(counted or 0) - int(team_damage or 0)
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
    step: prev + k*(cd - prev). Rounded to an integer damage value.

    A 0-damage battle-so-far IS folded (proj = prev*(1-k)): the overlay honestly projects
    'where you'd stand if the battle ended now', opening ~1-2 pts below career and climbing
    as real damage accrues. `combined_damage()` clamps cd to >= 0 upstream, so the fold
    never drags below prev*(1-k)."""
    prev = float(prev_avg or 0.0)
    return iround_half_away(prev + k * (float(cd or 0) - prev))


def build_battle_model(snapshot):
    """Compose the four in-battle readouts from the snapshot. Always returns a model;
    visibility is decided separately by battle_bar_visible()."""
    thresholds = snapshot.thresholds or {}
    merged_assist = getattr(snapshot, "assist", 0)
    counted, assist_kind = counted_assistance(
        getattr(snapshot, "track_assist", 0), getattr(snapshot, "spot_assist", 0),
        snapshot.stun, merged_assist)
    cd = combined_damage(snapshot.damage, getattr(snapshot, "track_assist", 0),
                         getattr(snapshot, "spot_assist", 0), snapshot.stun,
                         snapshot.team_damage, merged_assist=merged_assist)
    proj = ewma_project(snapshot.pre_avg_damage, cd)

    # Whether we have a CAREER baseline to project from. A >0 pre_avg/pre_percentile is an
    # obvious yes; a GENUINE 0 baseline also counts when the garage read the tank this session
    # (snapshot.baseline_known) -- e.g. the first-ever battle in a freshly-bought tank, where 0
    # is the true career and the projection (proj = k*cd, cur_percent = interp(proj)) is well
    # defined. Only a FALSE 0 -- replay / relogin straight into battle, the garage dossier never
    # read (baseline_known False; see baseline_cache + BUG B) -- collapses the EWMA fold and
    # anchors cur_percent on a bogus 0, so the overlay dashes proj/percent/delta out there.
    has_baseline = ((snapshot.pre_percentile or 0) > 0
                    or (snapshot.pre_avg_damage or 0) > 0
                    or bool(getattr(snapshot, "baseline_known", False)))

    stops = _threshold_stops(thresholds)
    has_data = stops is not None
    if has_data:
        # Anchor the live percent to WG's REAL career standing (pre_percentile, from the
        # dossier's getDamageRating) and add ONLY this battle's interpolation increment.
        # Our interp curve and WG's damageRating are different functions of damage, so their
        # ABSOLUTE values disagree by a percent or two -- but that constant bias cancels in
        # the increment interp(proj) - interp(pre_avg). At battle start proj == prev*(1-k),
        # so the increment is slightly negative and we open just BELOW WG's number: the
        # honest projection of an uncommitted (0-damage) battle, climbing as damage accrues.
        inc = (_interp_percent(proj, stops)
               - _interp_percent(snapshot.pre_avg_damage, stops))
        cur_percent = _clamp(float(snapshot.pre_percentile or 0.0) + inc, 0.0, 100.0)
        pct_delta = inc
    else:
        cur_percent = 0.0
        pct_delta = 0.0

    return bt.BattleMoEModel(
        combined_damage=cd,
        counted_assist=counted,
        assist_kind=assist_kind,
        proj_avg_damage=proj,
        cur_percent=cur_percent,
        pct_delta=pct_delta,
        has_data=has_data,
        has_baseline=has_baseline)


def battle_bar_visible(in_battle, has_vehicle, is_spectating=False, overlay_open=False,
                       enabled=True, alt_mode=False, alt_held=False):
    """Whether the in-battle overlay should render. Pure/engine-free so it unit-tests on
    plain inputs: a player vehicle must be readable and combat must be active, and we must
    NOT be spectating another player. While spectating (postmortem free-look), the tank
    identity/thresholds follow the observed vehicle but the damage stats stay ours, so the
    percent/delta is meaningless -- hide it. `overlay_open` is a hard override: while WG's
    full-stats scoreboard family (Tab / personal missions / reserves) is up, hide the
    readout so it does not clutter the full-screen scoreboard.

    Two settings decide whether the overlay is "active" at all:
    - `enabled` is the "Battle Widget Enabled" setting -- always-on.
    - `alt_mode` is the "Battle Widget on Alt Key" peek setting -- shows the overlay only while
      `alt_held` (Alt currently down).
    They are combined with a SOFT-GATE: `enabled` wins, so the Alt-peek mode has no effect while
    the always-on widget is enabled (MSA can't grey the checkbox out, so we make its value inert
    here). Defaults keep prior callers unchanged."""
    base = (bool(has_vehicle) and bool(in_battle)
            and not bool(is_spectating) and not bool(overlay_open))
    active = bool(enabled) or (bool(alt_mode) and bool(alt_held))
    return base and active
