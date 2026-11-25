#!/usr/bin/env python3
"""DEV: diagnose the in-battle percent prediction's error from the mod's own sample log.

`adapter/sample_log.py` appends one JSON line per battle to
`%APPDATA%\\Wargaming.net\\WorldOfTanks\\mods_data\\14th_ua_moe\\battle_samples.jsonl`,
pairing what the overlay PREDICTED with what WG's dossier reported afterwards
(`residual = post_percentile - predicted_percent`, so NEGATIVE = the mod over-predicted).
This reads that file and prints the diagnosis. Read-only, host-side Python 3, stdlib only.

    python tools/dev/analyze_battle_samples.py                  # default prefs path
    python tools/dev/analyze_battle_samples.py <path.jsonl>      # explicit file
    python tools/dev/analyze_battle_samples.py --min-delta 0.5   # ignore near-zero gains
    python tools/dev/analyze_battle_samples.py --self-check      # assert-based self-test
    python tools/dev/analyze_battle_samples.py --backtest        # shipped-model back-test (below)

WHY the regression, not just the mean: the live percent is ANCHORED
(`cur_percent = pre_percentile + inc`), so a constant offset in the damage->percent
mapping CANCELS and is invisible. Only the mapping's DERIVATIVE is observable, and it
shows up as residual growing with the predicted gain -- hence OLS of `residual ~ pct_delta`.
A flat slope with a nonzero mean is a level/baseline problem instead (bad thresholds,
stale dossier), not a slope one. Read the verdict line, not the mean alone.

--backtest asks ONE question: does the SHIPPED damage->percent model still reproduce WG's own
percentile on the logged rows? The log carries WG's answer directly (`post_avg_damage` +
`post_percentile` are both read off the dossier, so `f(post_avg) - post_percentile` is a LEVEL
test that needs no prediction at all). The model is IMPORTED from domain/battle_builder, never
re-implemented, so the tool measures what actually ships; it is fed the EIGHT anchors WG stores
(percentiles 20/40/55/65/75/85/95/100, live fetch, --cache8 keeps re-runs offline) exactly as
the shipped adapter now fetches them. `lin_percent` below is kept as an INDEPENDENT oracle and
the self-check asserts the two agree.

The finding this bake-off banked (118 rows: level error mean +0.047, stdev 0.088, max 0.238)
is that WG's damageRating IS piecewise-linear interpolation over those 8 anchors plus a
(0 damage, 0 percent) origin -- Lebwa's `linierInterpretator`. That is now the shipped model,
so the superseded piecewise-normal arm is gone: it cannot be reproduced from shipped code and
its job is done.

# ponytail: OLS + a t-ratio on the slope, no weighting/robust fit. A handful of outlier
# battles (arty assist, a 100%-mark tank) can tilt the line -- cross-read the buckets and
# the worst-offenders list before believing a slope. Upgrade to a median/Theil-Sen fit only
# if the buckets and the OLS line ever disagree.
"""
import argparse
import json
import os
import statistics as st
import sys
import tempfile
import urllib.request
from datetime import datetime

DEFAULT_PATH = os.path.join(os.environ.get("APPDATA", ""), "Wargaming.net", "WorldOfTanks",
                            "mods_data", "14th_ua_moe", "battle_samples.jsonl")

BUCKETS = ((0.0, 1.0), (1.0, 2.0), (2.0, 4.0), (4.0, 8.0), (8.0, float("inf")))

# --- the SHIPPED damage->percent model ----------------------------------------
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# Imported, never copied, so the back-test measures what the mod actually does. domain/ is
# engine-free and py3-clean (same sys.path trick as tests/conftest.py); nothing here writes src/.
sys.path.insert(0, os.path.join(ROOT, "src", "res", "scripts", "client"))
from moe_calculator.domain import battle_builder as bb

# --- the 8-anchor WG distribution (--backtest only) ---------------------------
# WG stores exactly these 8 anchors for `distribution=damage` and linearly interpolates every
# other percentile (confirmed); the API caps a call at 10 percentiles / 100 tank_ids.
PCTS8 = (20, 40, 55, 65, 75, 85, 95, 100)
# Bands of pre_avg_damage / D65 -- the shipped error is band-localised (worst far below 1 mark).
RATIO_BANDS = ((0.0, 0.3), (0.3, 0.6), (0.6, 0.9), (0.9, 1.1), (1.1, float("inf")))
REGION = "eu"   # WG API host suffix; --region sets it (eu / com / asia)
DEFAULT_CACHE8 = os.path.join(tempfile.gettempdir(), "moe_thresholds8.json")


# --- loading -----------------------------------------------------------------

# The log spans the threshold re-key: rows written before it are keyed by MARK COUNT
# ({1,2,3,100} = D65/D85/D95/D100), rows after it by PERCENTILE ({20,...,100}). Left unmapped a
# legacy row reads D65/D85/D95 as the 1st/2nd/3rd percentile -- garbage the shipped fit accepts
# silently. The key sets are disjoint apart from 100, so `1 in keys` decides the shape.
LEGACY_TH_KEYS = {1: 65, 2: 85, 3: 95}                   # 100 is already a percentile


def _norm_thresholds(row):
    """(percentile-keyed thresholds, shape name) for either logged shape. {} on junk."""
    try:
        th = dict((int(k), int(v)) for k, v in (row.get("thresholds") or {}).items())
    except (TypeError, ValueError, AttributeError):
        return {}, "unreadable"
    if not th:
        return {}, "missing"
    if 1 in th:
        return dict((LEGACY_TH_KEYS.get(k, k), v) for k, v in th.items()), "legacy"
    return th, "percentile"


def load(path, min_delta=0.0):
    """Usable rows + an ordered {reason: count} skip tally. A bad line is skipped, never fatal."""
    rows, skipped, seen = [], {}, set()

    def skip(why):
        skipped[why] = skipped.get(why, 0) + 1

    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                skip("unparseable JSON")
                continue
            if not isinstance(row, dict):
                skip("unparseable JSON")
                continue
            if not row.get("has_data"):
                skip("has_data false")
                continue
            if not row.get("has_baseline"):
                # The overlay DASHED the percent out on these (no career baseline -- replay /
                # relogin straight into battle), so `predicted_percent` was never shown to
                # anyone and its residual is meaningless. Two such rows carry +79 / +70 and
                # wreck every statistic below, so they are not samples at all.
                skip("has_baseline false")
                continue
            if row.get("residual") is None:
                skip("residual missing")
                continue
            if abs(_f(row, "pct_delta")) < min_delta:
                skip("pct_delta below --min-delta")
                continue
            # `post_battles` is the dossier battle count AFTER the battle, so it strictly
            # increments per battle in a tank: a repeat of (int_cd, post_battles) is the SAME
            # battle logged twice (a replay watch), never a new sample. The re-log carries a
            # STALE pre-baseline -- the one in this log reads pre_percentile 50.0 against a real
            # 34.79 -- which alone contributes a -15pp residual and 10x the whole set's stdev.
            key = (row.get("int_cd"), row.get("post_battles"))
            if row.get("post_battles") and key in seen:
                skip("duplicate battle (same int_cd + post_battles)")
                continue
            seen.add(key)
            row["thresholds"], row["th_shape"] = _norm_thresholds(row)
            rows.append(row)
    return rows, skipped


def _f(row, key):
    """A float field, tolerating null/absent/garbage -> 0.0 (optional keys may be missing)."""
    try:
        return float(row.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


# --- stats -------------------------------------------------------------------

def fit(xs, ys):
    """(slope, intercept, r, se_slope) or None when there's no spread to fit.

    `statistics` already owns the OLS and Pearson r (3.10+); only the slope's standard
    error needs arithmetic: se = sd_y/sd_x * sqrt((1-r^2)/(n-2))."""
    n = len(xs)
    if n < 3 or len(set(xs)) < 2 or len(set(ys)) < 2:
        return None
    slope, intercept = st.linear_regression(xs, ys)
    r = st.correlation(xs, ys)
    se = (st.stdev(ys) / st.stdev(xs)) * (max(0.0, 1.0 - r * r) / (n - 2)) ** 0.5
    return slope, intercept, r, se


def describe(vals):
    """n / mean / median / stdev / min / max as one line."""
    if not vals:
        return "n=0"
    sd = st.stdev(vals) if len(vals) > 1 else 0.0
    return ("n=%d  mean=%+.3f  median=%+.3f  stdev=%.3f  min=%+.3f  max=%+.3f"
            % (len(vals), st.fmean(vals), st.median(vals), sd, min(vals), max(vals)))


# --- report ------------------------------------------------------------------

def report(rows):
    res = [_f(r, "residual") for r in rows]
    deltas = [_f(r, "pct_delta") for r in rows]
    dmg = [_f(r, "combined_damage") for r in rows]
    stamps = [int(r.get("ts") or 0) for r in rows if r.get("ts")]
    tanks = sorted({r.get("int_cd") for r in rows if r.get("int_cd")})
    ks = sorted({_f(r, "ewma_k") for r in rows})
    versions = sorted({str(r.get("mod_version")) for r in rows if r.get("mod_version")})

    print("samples=%d  tanks=%d  ewma_k=%s%s" % (
        len(rows), len(tanks), ", ".join("%g" % k for k in ks) or "-",
        "  mod=" + ",".join(versions) if versions else ""))
    if stamps:
        span = "%s .. %s" % (datetime.fromtimestamp(min(stamps)).strftime("%Y-%m-%d %H:%M"),
                             datetime.fromtimestamp(max(stamps)).strftime("%Y-%m-%d %H:%M"))
    else:
        span = "(no ts)"
    print("dates: " + span)
    shapes = {}
    for r in rows:
        shape = r.get("th_shape") or "missing"       # unstamped == never had a thresholds dict
        shapes[shape] = shapes.get(shape, 0) + 1
    print("thresholds: " + ", ".join("%d %s" % (n, s) for s, n in sorted(shapes.items()))
          + "  (legacy 1/2/3 re-keyed to percentiles 65/85/95 on read)")

    print("\n== overall residual (post - predicted; negative = OVER-predicted) ==")
    print("  " + describe(res))

    print("\n== level vs slope ==")
    verdict = "inconclusive"
    for label, xs in (("pct_delta", deltas), ("combined_damage", dmg)):
        f = fit(xs, res)
        if f is None:
            print("  residual ~ %-16s no spread to fit" % label)
            continue
        slope, intercept, r, se = f
        t = slope / se if se else float("inf")
        print("  residual ~ %-16s slope=%+.4f (se %.4f, t=%+.1f)  intercept=%+.3f  r=%+.3f"
              % (label, slope, se, t, intercept, r))
        if label == "pct_delta":
            mean = st.fmean(res)
            sem = (st.stdev(res) / len(res) ** 0.5) if len(res) > 1 else 0.0
            if abs(t) > 2.0:
                verdict = ("SLOPE error: residual moves %+.3f pp per 1 pp of predicted gain "
                           "-> the damage->percent mapping's derivative is %s"
                           % (slope, "too steep" if slope < 0 else "too shallow"))
            elif sem and abs(mean) > 2.0 * sem:
                verdict = ("LEVEL offset: slope is flat (t=%+.1f) but mean residual is %+.3f "
                           "(+-%.3f) -> baseline/threshold problem, not the mapping"
                           % (t, mean, sem))
            else:
                verdict = ("neither is significant yet (slope t=%+.1f, mean %+.3f +-%.3f) "
                           "-> collect more battles" % (t, mean, sem))
    print("  VERDICT: " + verdict)

    print("\n== residual by predicted gain (pct_delta) ==")
    print("  %-12s %4s  %8s  %8s" % ("bucket", "n", "mean", "median"))
    for lo, hi in BUCKETS:
        vals = [_f(r, "residual") for r in rows if lo <= abs(_f(r, "pct_delta")) < hi]
        name = "%g-%g" % (lo, hi) if hi != float("inf") else "%g+" % lo
        if vals:
            print("  %-12s %4d  %+8.3f  %+8.3f" % (name, len(vals), st.fmean(vals), st.median(vals)))
        else:
            print("  %-12s %4d         -         -" % (name, 0))

    print("\n== worst offenders (largest |residual|) ==")
    print("  %-10s %8s %8s %9s %8s %9s" % ("int_cd", "dmg", "delta", "predict", "actual", "residual"))
    for r in sorted(rows, key=lambda r: -abs(_f(r, "residual")))[:10]:
        print("  %-10s %8.0f %8.2f %9.2f %8.2f %+9.2f"
              % (r.get("int_cd"), _f(r, "combined_damage"), _f(r, "pct_delta"),
                 _f(r, "predicted_percent"), _f(r, "post_percentile"), _f(r, "residual")))

    per_tank = {}
    for r in rows:
        per_tank.setdefault(r.get("int_cd"), []).append(_f(r, "residual"))
    shown = [(cd, v) for cd, v in per_tank.items() if len(v) >= 3]
    print("\n== per-tank (>= 3 samples) ==")
    if not shown:
        print("  none yet (%d tanks, all under 3 samples)" % len(per_tank))
    else:
        print("  %-10s %4s  %8s" % ("int_cd", "n", "mean"))
        for cd, vals in sorted(shown, key=lambda kv: st.fmean(kv[1])):
            print("  %-10s %4d  %+8.3f" % (cd, len(vals), st.fmean(vals)))
        print("  (a single tank far off the others = ITS thresholds; all shifted alike = the mapping)")


# --- backtest: the shipped model against WG's own percentile -------------------

def shipped_percent(damage, stops):
    """`damage` -> percent through the SHIPPED model, over a {percentile: damage} anchor table."""
    fit = bb._fit_from_thresholds(stops)
    return None if fit is None else bb._smooth_percent(damage, fit)


def lin_percent(damage, stops):
    """The INDEPENDENT ORACLE for shipped_percent, not a second model: WG's damageRating as
    piecewise-LINEAR percentile over the (0,0) origin stop plus the 8 stored anchors
    {20: D20, ..., 100: D100}. Flat (100) above D100, 0 at/below 0.

    Kept because nothing else re-derives the banked hypothesis from scratch -- self_check()
    sweeps both over real anchor tables and asserts they agree, so a regression in the shipped
    fit shows up here rather than being silently measured against itself.

    Non-ascending / missing anchors are dropped so a junk row degrades resolution instead of
    dividing by zero."""
    pts = [(0.0, 0.0)]
    for p in PCTS8:
        try:
            d = float(stops[p])
        except (KeyError, TypeError, ValueError):
            continue
        if d > pts[-1][0]:
            pts.append((d, float(p)))
    d = float(damage or 0.0)
    if d <= 0.0:
        return 0.0
    for (d0, p0), (d1, p1) in zip(pts, pts[1:]):
        if d <= d1:
            return p0 + (p1 - p0) * (d - d0) / (d1 - d0)
    return pts[-1][1]


def _read_app_id():
    """WG_APPLICATION_ID out of the gitignored .env (same KEY=VALUE parse as
    build/build_wotmod.py._read_app_id). "" when absent -> the fetch is refused."""
    try:
        with open(os.path.join(ROOT, ".env"), "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() == "WG_APPLICATION_ID":
            return value.strip().strip('"').strip("'")
    return ""


def fetch_stops8(int_cds, cache_path):
    """{int_cd: {percentile: damage}} for the 8 anchors, one batched WG call, cached to JSON so
    re-runs are offline. Only the ids missing from the cache are fetched."""
    blob = {}
    if os.path.isfile(cache_path):
        with open(cache_path, "r", encoding="utf-8") as fh:
            blob = json.load(fh) or {}
    missing = [cd for cd in int_cds if str(cd) not in blob]
    if missing:
        app_id = _read_app_id()
        if not app_id:
            raise SystemExit("no WG_APPLICATION_ID in .env -- cannot fetch the 8-stop table")
        url = ("https://api.worldoftanks.%s/wot/tanks/mastery/?application_id=%s"
               "&distribution=damage&percentile=%s&tank_id=%s"
               % (REGION, app_id, ",".join(str(p) for p in PCTS8),
                  ",".join(str(int(cd)) for cd in missing)))
        print("fetching %d tanks x %d percentiles from WG ..." % (len(missing), len(PCTS8)))
        with urllib.request.urlopen(url, timeout=20) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        if body.get("status") != "ok":
            raise SystemExit("WG API error: %r" % (body.get("error"),))
        blob.update((body.get("data") or {}).get("distribution") or {})
        with open(cache_path, "w", encoding="utf-8") as fh:
            json.dump(blob, fh, indent=1, sort_keys=True)
        print("cached -> %s" % cache_path)
    out = {}
    for cd, row in blob.items():
        if isinstance(row, dict) and all(row.get(str(p)) for p in PCTS8):
            out[int(cd)] = dict((p, int(row[str(p)])) for p in PCTS8)
    return out


def _band(ratio):
    for i, (lo, hi) in enumerate(RATIO_BANDS):
        if lo <= ratio < hi:
            return i
    return len(RATIO_BANDS) - 1


def _band_name(i):
    lo, hi = RATIO_BANDS[i]
    return "%g+" % lo if hi == float("inf") else "%g-%g" % (lo, hi)


def enrich(rows, stops8):
    """One record per usable row carrying the shipped model's errors. Skips a row whose tank has
    no 8-anchor table, or whose own logged table has no D65 to band it by.

    The model is driven off the FRESH 8-anchor table (`stops8`), not the row's logged one: that is
    what the shipped adapter now fetches, and it is like-for-like with the banked finding. The
    row's own thresholds are used ONLY for the band split -- normalised to percentile keys on
    read (see _norm_thresholds), so D65 is `th[65]` for both logged shapes."""
    recs, dropped = [], 0
    for r in rows:
        cd = int(r.get("int_cd") or 0)
        s8 = stops8.get(cd)
        th = r.get("thresholds") or {}
        if not s8 or not th.get(65):
            dropped += 1
            continue
        fit = bb._fit_from_thresholds(s8)
        pre, proj, post = (_f(r, "pre_avg_damage"), _f(r, "proj_avg_damage"),
                           _f(r, "post_avg_damage"))
        pre_p, post_p = _f(r, "pre_percentile"), _f(r, "post_percentile")
        f = lambda d: bb._smooth_percent(d, fit)
        inc = f(proj) - f(pre)
        recs.append({
            "row": r, "cd": cd, "band": _band(pre / float(th[65])),
            "pre": pre, "post": post, "pre_p": pre_p, "post_p": post_p,
            "post_err": f(post) - post_p, "pre_err": f(pre) - pre_p,
            "inc": inc, "res": post_p - (pre_p + inc), "unanch": f(proj) - post_p,
        })
    return recs, dropped


def line(vals):
    """describe() plus the max ABSOLUTE error the level tests are judged on."""
    if not vals:
        return "n=0"
    return describe(vals) + "  max|e|=%.3f" % max(abs(v) for v in vals)


def _by_band(recs, key, fmt="%+8.3f"):
    """One row of per-band means for `key`."""
    cells = []
    for i in range(len(RATIO_BANDS)):
        vals = [r[key] for r in recs if r["band"] == i]
        cells.append((fmt % st.fmean(vals)) if vals else "%8s" % "-")
    return "  ".join(cells)


MISS_THRESHOLD = 200.0    # a miss this big is beyond the rounding noise below -- worth counting


def _miss(row):
    """The late credit WG applied that we never saw, in COMBINED DAMAGE. None without a k.

    post_avg is the dossier average AFTER the battle, and the average moves by EWMA, so
    `pre_avg + (post_avg - pre_avg)/k` is the combined damage WG itself booked for that battle;
    subtracting our own last-seen total (the trailing push when we have one) leaves the shortfall.
    post_avg_damage is an INTEGER, so this carries +-0.5/k (~+-25 damage at k=0.0198) of rounding
    noise -- which is why the split below reports the MEDIAN and a count over a threshold, never
    a mean alone."""
    k = _f(row, "ewma_k")
    if not k:
        return None
    implied = _f(row, "pre_avg_damage") + (_f(row, "post_avg_damage")
                                          - _f(row, "pre_avg_damage")) / k
    return implied - (_f(row, "final_combined_damage") or _f(row, "combined_damage"))


def _died_label(row):
    """"died" / "survived" / "unknown" -- a null `died` is a row written before the column existed,
    which is a THIRD state, never False (see adapter/sample_log._FINAL_KEYS)."""
    d = row.get("died")
    return "unknown" if d is None else ("died" if d else "survived")


def death_split(recs, threshold=MISS_THRESHOLD):
    """[(label, n, median miss, count(miss > threshold), mean residual, median residual)] in
    died / survived / unknown order. The question: is the ~20% late-credit tail the DEATH path,
    or end-of-battle server accounting in general?"""
    groups = {}
    for r in recs:
        groups.setdefault(_died_label(r["row"]), []).append(r)
    out = []
    for label in ("died", "survived", "unknown"):
        g = groups.get(label) or []
        misses = [m for m in (_miss(r["row"]) for r in g) if m is not None]
        res = [r["res"] for r in g]
        out.append((label, len(g), st.median(misses) if misses else None,
                    sum(1 for m in misses if m > threshold),
                    st.fmean(res) if res else None, st.median(res) if res else None))
    return out


def _slope(recs, xkey, ykey):
    f = fit([r[xkey] for r in recs], [r[ykey] for r in recs])
    if f is None:
        return "no spread"
    slope, _icpt, r, se = f
    return "slope=%+.4f (se %.4f, t=%+.2f, r=%+.3f)" % (slope, se, slope / se if se else 0.0, r)


def backtest(rows, stops8):
    recs, dropped = enrich(rows, stops8)
    print("\n== 8-stop WG table (percentile -> combined damage) ==")
    print("  %-8s" % "int_cd" + "".join("%7d" % p for p in PCTS8))
    for cd in sorted(stops8):
        print("  %-8d" % cd + "".join("%7d" % stops8[cd][p] for p in PCTS8))
    print("\nback-test rows: %d (%d dropped: no 8-stop table / no logged D65)"
          % (len(recs), dropped))
    if not recs:
        return

    print("\n== LEVEL test: f(avg_damage) - WG's own percentile (no prediction involved) ==")
    print("   f = the SHIPPED domain/battle_builder model over the 8 anchors")
    for what, key in (("post_avg", "post_err"), ("pre_avg", "pre_err")):
        print("    %-10s %s" % (what, line([r[key] for r in recs])))

    print("\n  5 worst rows (post_avg):")
    print("    %-8s %8s %9s %9s %9s" % ("int_cd", "post_avg", "f(post)", "WG post", "error"))
    for r in sorted(recs, key=lambda r: -abs(r["post_err"]))[:5]:
        print("    %-8d %8.0f %9.3f %9.2f %+9.3f"
              % (r["cd"], r["post"], r["post_p"] + r["post_err"], r["post_p"], r["post_err"]))

    print("\n== PREDICTION test: pred = pre_percentile + (f(proj) - f(pre_avg)) ==")
    print("  %s" % line([r["res"] for r in recs]))
    print("  residual ~ inc: %s" % _slope(recs, "inc", "res"))

    print("\n== late WG credit we never saw, split by `died` ==")
    print("   miss = pre_avg + (post_avg - pre_avg)/k  -  our last seen combined damage")
    print("   (post_avg is an INTEGER -> +-0.5/k ~ +-25 dmg of noise; read the median + the count)")
    print("  %-9s %4s %10s %8s %9s %9s"
          % ("group", "n", "med miss", ">%d" % MISS_THRESHOLD, "mean res", "med res"))
    for label, n, med, over, mres, medres in death_split(recs):
        cell = lambda v, f: (f % v) if v is not None else "%8s" % "-"
        print("  %-9s %4d %10s %8d %9s %9s"
              % (label, n, cell(med, "%10.0f"), over, cell(mres, "%+9.3f"),
                 cell(medres, "%+9.3f")))

    print("\n== UNANCHORED: f(proj) - post_percentile (drops the pre_percentile anchor) ==")
    print("  %s" % line([r["unanch"] for r in recs]))

    print("\n== by band of pre_avg_damage / D65 ==")
    print("  %-26s" % "metric (mean)" + "  ".join("%8s" % _band_name(i)
                                                  for i in range(len(RATIO_BANDS))))
    print("  %-26s" % "n" + "  ".join("%8d" % sum(1 for r in recs if r["band"] == i)
                                      for i in range(len(RATIO_BANDS))))
    for label, key in (("level f(post)-WG", "post_err"), ("level f(pre)-WG", "pre_err"),
                       ("residual (anchored)", "res"), ("unanchored", "unanch")):
        print("  %-26s" % label + _by_band(recs, key))


# --- self-check --------------------------------------------------------------

def self_check():
    """Inject a known slope + offset into synthetic rows and confirm OLS recovers them,
    then round-trip load() to confirm the skip tally, then render the report."""
    # The SHIPPED model against WG's OWN damageRating, read off the sample log: two tanks, one
    # deep below the D20 floor (the origin stop is the whole story there) and one mid-table.
    # Real WG anchors (fetched 2026-07-31); `want` is the model's value and `wg` the damageRating
    # WG itself reported for that exact average in battle_samples.jsonl. avg 30 / 70 sit far below
    # the D20 anchor, so they test the (0,0) ORIGIN segment -- the whole point of the hypothesis;
    # the 3192 / 3179 pair tests an interior segment (D75..D85). The 0.05 tolerance on `wg` covers
    # WG's own 2dp rounding plus the model's residual (whole-set max |e| is ~0.24).
    s = {54657: {20: 528, 40: 1163, 55: 1549, 65: 1799, 75: 2104, 85: 2494, 95: 3042, 100: 3482},
         69153: {20: 812, 40: 1598, 55: 2136, 65: 2561, 75: 3043, 85: 3661, 95: 4552, 100: 5261}}
    for cd, dmg, want, wg in ((54657, 30, 1.136, 1.14), (54657, 70, 2.65, 2.64),
                              (69153, 3192, 77.41, 77.37), (69153, 3179, 77.20, 77.16)):
        got = shipped_percent(dmg, s[cd])
        assert abs(got - want) < 0.005, (cd, dmg, got, want)      # the model's exact value
        assert abs(got - wg) < 0.05, (cd, dmg, got, wg)           # ... and WG's own number
    assert shipped_percent(0, s[54657]) == 0.0
    assert shipped_percent(99999, s[54657]) == 100.0                       # flat above D100
    assert abs(shipped_percent(1799, s[54657]) - 65.0) < 1e-9              # exact AT an anchor
    assert shipped_percent(2104, s[54657]) > shipped_percent(2103, s[54657])          # monotone
    assert shipped_percent(1000, {20: 500, 40: 500, 65: 900}) > 0.0  # dupe anchors dropped, no /0
    assert shipped_percent(1000, {}) is None                       # unusable table -> no percent

    # ORACLE: the shipped model must agree with the independent linear8+origin re-derivation
    # everywhere, or the level numbers below are being measured against themselves.
    for cd, stops in s.items():
        for dmg in range(0, int(stops[100] * 1.2), 17):
            assert abs(shipped_percent(dmg, stops) - lin_percent(dmg, stops)) < 1e-9, (cd, dmg)

    # BOTH logged threshold shapes normalise to percentile keys (a legacy row left unmapped would
    # read D65 as the 1st percentile and band-split on a missing th[65]).
    assert _norm_thresholds({"thresholds": {"1": 1799, "2": 2494, "3": 3042, "100": 3482}}) == (
        {65: 1799, 85: 2494, 95: 3042, 100: 3482}, "legacy")
    assert _norm_thresholds({"thresholds": {"20": 528, "65": 1799, "100": 3482}}) == (
        {20: 528, 65: 1799, 100: 3482}, "percentile")
    assert _norm_thresholds({}) == ({}, "missing")
    assert _norm_thresholds({"thresholds": {"x": 1}}) == ({}, "unreadable")

    # The `died` split, over all THREE states (True / False / absent = unknown). At k=0.02 a +4
    # move in the dossier average is 200 damage of WG credit, so pre 1800 -> post 1804 implies
    # 2000 combined and logging 1700 of it is a 300 miss; the trailing final_* total wins when set.
    d = [({"ewma_k": 0.02, "pre_avg_damage": 1800, "post_avg_damage": 1804,
           "combined_damage": 1700, "died": True}, -1.0),                            # miss 300
         ({"ewma_k": 0.02, "pre_avg_damage": 1800, "post_avg_damage": 1804,
           "combined_damage": 1700, "final_combined_damage": 1950, "died": True}, -3.0),  # miss 50
         ({"ewma_k": 0.02, "pre_avg_damage": 1800, "post_avg_damage": 1810,
           "combined_damage": 2300, "died": False}, 0.5),                            # miss 0
         ({"ewma_k": 0.02, "pre_avg_damage": 1800, "post_avg_damage": 1804,
           "combined_damage": 2000}, 0.5)]                                  # no column -> unknown
    assert abs(_miss(d[0][0]) - 300.0) < 1e-9, _miss(d[0][0])
    assert abs(_miss(d[1][0]) - 50.0) < 1e-9, _miss(d[1][0])   # final_* preferred over combined
    assert _miss({}) is None                                   # no k logged -> not measurable
    split = death_split([{"row": row, "res": res} for row, res in d])
    assert [(g[0], g[1], g[3]) for g in split] == [("died", 2, 1), ("survived", 1, 0),
                                                   ("unknown", 1, 0)], split
    assert abs(split[0][2] - 175.0) < 1e-9, split[0]           # median of the 300 / 50 misses
    assert split[1][2] == 0.0 and split[2][2] == 0.0, split    # both non-death groups: no miss
    assert abs(split[1][4] - 0.5) < 1e-9, split[1]             # residual carried per group
    assert abs(split[0][4] - -2.0) < 1e-9, split[0]

    rows = [{"has_data": True, "has_baseline": True, "int_cd": 100 + i % 3, "ts": 1750000000 + i * 3600,
             "ewma_k": 0.12, "pct_delta": 0.25 * i, "combined_damage": 300 + 90 * i,
             "predicted_percent": 50.0 + 0.25 * i,
             "post_percentile": 50.0 + 0.25 * i + (1.0 - 0.4 * (0.25 * i)),
             "residual": 1.0 - 0.4 * (0.25 * i),
             # a MIXED log: one third legacy-keyed, one third percentile-keyed, one third none
             "thresholds": ({"1": 1799, "2": 2494, "3": 3042, "100": 3482} if i % 3 == 1
                            else {"20": 528, "65": 1799, "100": 3482} if i % 3 == 2
                            else {})} for i in range(1, 41)]
    slope, intercept, r, se = fit([r["pct_delta"] for r in rows], [r["residual"] for r in rows])
    assert abs(slope - -0.4) < 1e-9, slope
    assert abs(intercept - 1.0) < 1e-9, intercept
    assert abs(r - -1.0) < 1e-9, r
    assert se < 1e-9, se  # perfect fit -> zero residual variance

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "battle_samples.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")
            fh.write('{"has_data": false, "residual": 1.0, "pct_delta": 3.0}\n')
            fh.write('{"has_data": true, "has_baseline": true, "pct_delta": 3.0}\n')  # residual missing
            fh.write('{"has_data": true, "has_baseline": false, "residual": 79.0, "pct_delta": 3.0}\n')
            # rows[0] and rows[3] are the same int_cd (101), so the second post_battles=7 is a dup
            fh.write(json.dumps(dict(rows[0], post_battles=7)) + "\n")   # unique -> kept
            fh.write(json.dumps(dict(rows[3], post_battles=7)) + "\n")   # same count -> dup
            fh.write("not json\n\n")
        loaded, skipped = load(path)
        assert len(loaded) == len(rows) + 1, len(loaded)
        assert skipped == {"has_data false": 1, "has_baseline false": 1, "residual missing": 1,
                           "duplicate battle (same int_cd + post_battles)": 1,
                           "unparseable JSON": 1}, skipped
        # every kept row's thresholds are percentile-keyed downstream, whatever it was written as
        shapes = {}
        for row in loaded:
            shapes[row["th_shape"]] = shapes.get(row["th_shape"], 0) + 1
        assert shapes == {"legacy": 15, "percentile": 13, "missing": 13}, shapes
        assert loaded[0]["thresholds"] == {65: 1799, 85: 2494, 95: 3042, 100: 3482}
        assert all(row["thresholds"].get(65) for row in loaded if row["th_shape"] != "missing")
        low, skipped = load(path, min_delta=5.0)
        assert len(low) == len([r for r in rows if r["pct_delta"] >= 5.0]) == 21, len(low)
        assert skipped["pct_delta below --min-delta"] == 21, skipped  # +2 low-delta extras

    print("self-check OK (recovered slope %.4f, intercept %.4f, r %.4f)\n" % (slope, intercept, r))
    report(loaded)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("path", nargs="?", default=DEFAULT_PATH, help="battle_samples.jsonl (default: prefs dir)")
    ap.add_argument("--min-delta", type=float, default=0.0,
                    help="skip rows whose |pct_delta| is below this (default 0)")
    ap.add_argument("--region", choices=("eu", "com", "asia"), default="eu", help="WG API host suffix (default eu)")
    ap.add_argument("--self-check", action="store_true", help="run the assert-based self-test and exit")
    ap.add_argument("--backtest", action="store_true",
                    help="back-test the SHIPPED damage->percent model against WG's own percentile")
    ap.add_argument("--cache8", default=DEFAULT_CACHE8,
                    help="JSON cache of the 8-stop WG table (default: %s)" % DEFAULT_CACHE8)
    args = ap.parse_args()
    global REGION
    REGION = args.region

    if args.self_check:
        self_check()
        return 0

    if not os.path.isfile(args.path):
        print("no sample log at %s" % args.path)
        print("Play a few battles with the mod installed (the recorder is always on), or pass a path.")
        return 1

    rows, skipped = load(args.path, args.min_delta)
    print("file: %s" % args.path)
    if skipped:
        print("skipped: " + ", ".join("%d %s" % (n, why) for why, n in sorted(skipped.items())))
    if not rows:
        print("no usable samples yet (0 rows with has_data and a residual).")
        return 1
    report(rows)
    if args.backtest:
        backtest(rows, fetch_stops8(sorted({int(r["int_cd"]) for r in rows if r.get("int_cd")}),
                                    args.cache8))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
