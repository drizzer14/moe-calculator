# -*- coding: utf-8 -*-
"""Offline MoE-threshold provider (the WGMods-release data source): NO external API.

Selected by the `moe_data` router when build_config.MOE_DATA_SOURCE == "offline". Instead of
fetching a crowd-sourced table, it ESTIMATES each tank's 1/2/3-mark combined-damage thresholds
from official client data: every garage read hands us the player's own (movingAvgDamage,
damageRating) for the selected tank -- one point on that tank's combined-damage -> percentile
curve. We accumulate these samples per tank (persisted to disk so they survive across sessions
-- the dossier only changes after a battle sync), and hand them to the pure domain estimator
(domain/moe_estimate) which fits the curve and reads off the thresholds. See that module for
the math and the honest accuracy caveats.

The thresholds are therefore ESTIMATES. An estimate appears from the very first sample (via the
estimator's universal prior) and sharpens as more percentile-spread samples land. Everything
engine-facing here is guarded and fail-soft: a bad prefs dir just degrades to in-memory-only
samples, never a crash.
"""
import os
import json

from moe_calculator._compat import LOG_CURRENT_EXCEPTION, LOG_NOTE
from moe_calculator.domain import moe_estimate

# --- tuning ------------------------------------------------------------------
_MAX_SAMPLES = 20            # newest-kept cap per tank (lets the fit track slow meta drift)
_STORE_VERSION = 1           # on-disk envelope version (a bump/mismatch is discarded on load)
# Dedup thresholds: a new read that barely differs from the last stored one is a redundant
# garage refresh (vehicle re-select, overlay toggle), not a real stat change -- collapse it.
_DEDUP_DMG = 1.0
_DEDUP_PCT = 0.05

# --- module state (main-thread only) -----------------------------------------
_samples = {}                # int_cd -> [(damage, percentile 0..100), ...]
_cache = {}                  # int_cd -> {1,2,3,100: dmg} (memoized; invalidated on new sample)
_loaded = False              # the on-disk store has been read this session


# --- persistence -------------------------------------------------------------

def _store_path():
    """Absolute path to the per-user sample store. Under the client's writable preferences
    dir (the same place the client's own local caches live). `helpers` is imported lazily so
    this module imports under pytest; tests monkeypatch this function to a temp file."""
    import helpers
    base = helpers.getPreferencesDirPath()
    return os.path.join(base, "mods_data", "14th_ua_moe", "moe_samples.json")


def _load():
    """Read the sample store from disk into _samples. Guarded -> leaves _samples empty on any
    error (missing file, bad JSON, version mismatch)."""
    global _loaded
    _loaded = True
    try:
        path = _store_path()
        if not os.path.isfile(path):
            return
        with open(path, "rb") as fh:
            blob = json.loads(fh.read().decode("utf-8"))
        if not isinstance(blob, dict) or blob.get("v") != _STORE_VERSION:
            LOG_NOTE("[moe] sample store version mismatch -> ignored")
            return
        raw = blob.get("samples", {})
        for key, rows in raw.items():
            try:
                cd = int(key)
            except (TypeError, ValueError):
                continue
            pairs = []
            for row in rows or ():
                try:
                    pairs.append((float(row[0]), float(row[1])))
                except (TypeError, ValueError, IndexError):
                    continue
            if pairs:
                _samples[cd] = pairs[-_MAX_SAMPLES:]
        LOG_NOTE("[moe] sample store loaded: %d tanks" % len(_samples))
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _save():
    """Persist _samples to disk atomically (write .tmp, then replace). Whole body guarded so a
    read-only/full disk degrades to in-memory-only samples rather than raising into a push."""
    try:
        path = _store_path()
        directory = os.path.dirname(path)
        if not os.path.isdir(directory):
            os.makedirs(directory)
        blob = {"v": _STORE_VERSION,
                "samples": {str(cd): [[d, p] for d, p in rows]
                            for cd, rows in _samples.items()}}
        tmp = path + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(json.dumps(blob).encode("utf-8"))
        # os.rename won't overwrite on Windows/py2.7 -- remove first (small window; this cache
        # is non-critical and the whole body is guarded).
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
        os.rename(tmp, path)
    except Exception:
        LOG_CURRENT_EXCEPTION()


# --- public API (mirrors the router surface) ---------------------------------

def start():
    """Load the on-disk sample store once. Idempotent + guarded (matches the tomato provider's
    start() contract; here it's synchronous -- there is no background work)."""
    if not _loaded:
        _load()


def is_loaded():
    return _loaded


def add_ready_listener(cb):
    """Data is synchronous (no fetch), so fire the ready callback immediately -- mirrors the
    tomato provider's fire-if-already-loaded path so the bridges' one-time re-push still works.
    Guarded so a raising callback can't propagate into the caller."""
    try:
        cb()
    except Exception:
        LOG_CURRENT_EXCEPTION()


def record_sample(int_cd, percentile, avg_damage):
    """Record one (avg_damage, percentile) observation for a tank, from a garage dossier read.
    Guards drop degenerate reads (no vehicle / never-played / impossible percentile); dedup
    collapses the many redundant garage refreshes to ~one sample per real stat change. Appends,
    caps to the newest _MAX_SAMPLES, invalidates the memoized thresholds, and persists."""
    try:
        cd = int(int_cd or 0)
    except (TypeError, ValueError):
        return
    if not cd:
        return
    try:
        d = float(avg_damage or 0)
        p = float(percentile or 0.0)
    except (TypeError, ValueError):
        return
    if d <= 0.0 or p <= 0.0 or p >= 100.0:
        return

    if not _loaded:
        _load()
    rows = _samples.setdefault(cd, [])
    if rows:
        last_d, last_p = rows[-1]
        if abs(d - last_d) < _DEDUP_DMG and abs(p - last_p) < _DEDUP_PCT:
            return  # redundant read (no real stat change) -- don't grow the store
    rows.append((d, p))
    if len(rows) > _MAX_SAMPLES:
        del rows[:-_MAX_SAMPLES]
    _cache.pop(cd, None)
    _save()


def get_thresholds(int_cd):
    """Return the estimated {1,2,3,100: dmg} for a vehicle, or {} when there's nothing usable
    yet (never-played tank). Loads the store on first use; memoizes per tank."""
    start()
    try:
        cd = int(int_cd or 0)
    except (TypeError, ValueError):
        return {}
    if cd in _cache:
        return _cache[cd]
    rows = _samples.get(cd, ())
    thresholds = moe_estimate.thresholds_from_samples([(d, p / 100.0) for d, p in rows])
    _cache[cd] = thresholds
    return thresholds
