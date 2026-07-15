# -*- coding: utf-8 -*-
"""Persistent per-account capture of WG's realized EWMA step (engine-free, unit-testable).

domain/k_estimator turns a stream of (avg_before, cd, avg_after) samples into a robust k; this
module is where those samples come FROM and where the running estimate is PERSISTED across
sessions. Capture is two-phase because the two halves of a sample live in different places at
different times:

  1. Battle end: the overlay knows this battle's pre-battle average (avg_before) and the
     combined damage it computed (cd) -- but the post-battle movingAvgDamage isn't readable
     until the garage dossier resyncs. So we STASH the pair keyed by the vehicle's intCD
     (remember_pending) and persist immediately (a battle-end crash/relog must not lose it).
  2. Next garage read: the dossier now exposes avg_after for that vehicle. complete() looks up
     the stashed pair and finishes the sample: k = k_estimator.observed_k(avg_before, cd,
     avg_after).

The garage dossier resync is not instant, so the very first post-battle read can still report
the OLD average (avg_after == avg_before) -- that means "not synced yet", not "the average
didn't move", so the pending record is deliberately KEPT for a later, real read rather than
being consumed with a spurious zero-numerator sample.

k_real is derived from OUR OWN computed cd, so a per-account median also absorbs how THIS
player's cd is biased (max-assist approximation, team_damage=0 live) -- something a single
baked constant could not. current_k() is the read side the projector calls every push: the
caller's EWMA_K default until enough evidence accrues, then the robust median.
"""
import os
import json

from moe_calculator._compat import LOG_CURRENT_EXCEPTION, LOG_DEBUG
from moe_calculator.domain import k_estimator
from moe_calculator.domain.constants import EWMA_K

_STORE_VERSION = 1

# --- module state (main-thread only) -----------------------------------------
_pending = {}   # int_cd -> (avg_before(float), cd(int)) -- awaiting the next garage dossier read
_samples = []   # ring buffer of accepted k floats, capped at k_estimator.SAMPLE_CAP
_loaded = False  # lazy-load-once guard


# --- pure envelope parser (unit-tested directly) ------------------------------

def valid_blob(blob):
    """Return (pending, samples) parsed out of a persisted envelope iff it is the current store
    version; otherwise ({}, []). `pending` coerces to {int(cd): (float(avg_before), int(cd_val))},
    dropping any row that doesn't parse. `samples` passes every entry through k_estimator.clamp_k
    (dropping junk / out-of-band values) and keeps only the last SAMPLE_CAP. Pure -- no I/O, so
    this is the function unit tests target directly. Mirrors moe_wgapi.valid_list."""
    if not isinstance(blob, dict):
        return {}, []
    if blob.get("version") != _STORE_VERSION:
        return {}, []
    pending = {}
    raw_pending = blob.get("pending") or {}
    if isinstance(raw_pending, dict):
        for cd, row in raw_pending.items():
            try:
                avg_before, cd_val = row
                pending[int(cd)] = (float(avg_before), int(cd_val))
            except (TypeError, ValueError):
                continue
    samples = []
    raw_samples = blob.get("samples") or []
    if isinstance(raw_samples, list):
        for raw in raw_samples:
            k = k_estimator.clamp_k(raw)
            if k is not None:
                samples.append(k)
    if len(samples) > k_estimator.SAMPLE_CAP:
        samples = samples[-k_estimator.SAMPLE_CAP:]
    return pending, samples


# --- public API ---------------------------------------------------------------

def remember_pending(int_cd, avg_before, cd):
    """Battle end: stash this vehicle's (avg_before, cd) pair, overwriting any prior pending
    record for the same vehicle (only the latest battle's pair matters), then persist. Guarded
    -- never raises into the caller."""
    try:
        load()
        icd = int(int_cd or 0)
        if not icd:
            return
        _pending[icd] = (float(avg_before), int(cd))
        save()
    except Exception:
        LOG_CURRENT_EXCEPTION()


def complete(int_cd, avg_after):
    """Next garage read: finish the pending sample for this vehicle, if any.

    avg_after == avg_before means the dossier has NOT synced the new average yet -- keep the
    pending record for a later, real read rather than consuming it with a spurious
    zero-numerator sample. Otherwise the pending record retires REGARDLESS of whether
    k_estimator.observed_k accepts the result (a bad sample is still a used-up sample -- it must
    not be replayed against a later, unrelated battle). Guarded -- never raises into the caller."""
    try:
        load()
        icd = int(int_cd or 0)
        if not icd:
            return
        pending = _pending.get(icd)
        if pending is None:
            return
        avg_before, cd = pending
        after = float(avg_after)
        if after == avg_before:
            return  # dossier not synced yet -- keep pending, no sample, no save
        del _pending[icd]
        k = k_estimator.observed_k(avg_before, cd, after)
        if k is not None:
            _samples.append(k)
            if len(_samples) > k_estimator.SAMPLE_CAP:
                del _samples[0]
            LOG_DEBUG("[moe-calib] sample (avg_before=%r, cd=%r, avg_after=%r) -> k=%r"
                     % (avg_before, cd, after, k))
        save()
    except Exception:
        LOG_CURRENT_EXCEPTION()


def current_k():
    """The robust running k estimate: the caller's EWMA_K default until MIN_SAMPLES accepted
    samples accumulate, then the clamped median. Fail-soft to EWMA_K on any exception."""
    try:
        load()
        return k_estimator.aggregate_k(_samples, EWMA_K)
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return EWMA_K


def load():
    """Adopt the persisted cache into _pending/_samples. Lazy-once (guarded on _loaded, set
    BEFORE the body runs so a failing load doesn't retry every call). No-op if the file is
    missing. Guarded -- no-op on any error / malformed envelope."""
    global _loaded, _pending, _samples
    if _loaded:
        return
    _loaded = True
    try:
        path = _store_path()
        if not os.path.isfile(path):
            return
        with open(path, "rb") as fh:
            blob = json.loads(fh.read().decode("utf-8"))
        pending, samples = valid_blob(blob)
        _pending = pending
        _samples = samples
        LOG_DEBUG("[moe-calib] cache loaded: pending=%d samples=%d" % (len(_pending), len(_samples)))
    except Exception:
        LOG_CURRENT_EXCEPTION()


def save():
    """Persist _pending/_samples to disk atomically (tmp+rename, same idiom as
    moe_wgapi._save_cache). Guarded so a read-only/full disk degrades to in-memory-only rather
    than raising into a mutator."""
    try:
        path = _store_path()
        directory = os.path.dirname(path)
        if not os.path.isdir(directory):
            os.makedirs(directory)
        blob = {"version": _STORE_VERSION,
                "pending": dict((str(cd), [avg_before, cd_val])
                                for cd, (avg_before, cd_val) in _pending.items()),
                "samples": list(_samples)}
        tmp = path + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(json.dumps(blob).encode("utf-8"))
        # os.rename won't overwrite on Windows/py2.7 -- remove first (small window; guarded).
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
        os.rename(tmp, path)
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _store_path():
    """Absolute path to the persisted calibration cache, under the client's writable prefs dir.
    `helpers` is imported lazily so this module imports under pytest (tests monkeypatch)."""
    import helpers
    base = helpers.getPreferencesDirPath()
    return os.path.join(base, "mods_data", "14th_ua_moe", "moe_calibration.json")


def clear():
    """Test helper: drop all pending/sample state and the lazy-load guard."""
    global _pending, _samples, _loaded
    _pending = {}
    _samples = []
    _loaded = False
