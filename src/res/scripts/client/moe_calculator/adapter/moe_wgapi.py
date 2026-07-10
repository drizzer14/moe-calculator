# -*- coding: utf-8 -*-
"""Official Wargaming-API MoE-threshold provider -- the sole threshold source.

Wargaming's public API exposes the real Marks-of-Excellence damage distribution directly
(no scraping, no estimation), so this replaces the former tomato.gg-scrape / offline-estimator
build variants. Endpoint (EU cluster):

    GET https://api.worldoftanks.eu/wot/tanks/mastery/
        ?application_id=<APP_ID>&distribution=damage&percentile=65,85,95,100
        &tank_id=<up to 100 comma-separated intCDs>

    -> {"status":"ok","data":{"distribution":{
          "<tank_id>":{"65":D1,"85":D2,"95":D3,"100":D4}}, "updated_at":...}}

Percentiles 65/85/95/100 map straight onto our contract keys {1,2,3,100} (1/2/3 marks +
the right-edge goalpost). Missing/invalid tank_ids are simply absent from `distribution`.

Fetch behavior -- a persistent, capped (100) working set of OWNED tank ids ("the list"):
  * The list lives in its own file (moe_fetch_list.json), a {intCD: recency} map. It is
    membership + recency; the fetched thresholds live in the separate _table / cache below.
  * Session start, fast paint: fetch the SELECTED vehicle immediately.
  * Session start, list ready: if the list is empty, bootstrap it from the selected vehicle +
    the owned vehicles played in the last 7 days (domain/fetch_list.bootstrap_ids); otherwise
    drop ids no longer in the garage and purge tanks not played in the last 7 days. Then fetch
    the whole list in one batch (>=100 ids fit one request).
  * Buy adds a tank (stamped recency = now, so an unplayed purchase survives ~7 days); sell
    removes it; selecting adds it to a session-only TEMP set (fetched, not yet committed);
    playing a battle in it promotes it to the permanent list. Adds past the 100-cap evict the
    least-recently-played member.
  * On selection: get_thresholds() lazily fetches a single tank iff it's not already cached.
  * Results are cached in memory AND persisted, revalidated two ways: (a) a time backstop --
    the cache is served while now < the data's own `updated_at` + 7 days -- and (b) an
    updated_at-change trigger -- whenever any fetch returns an `updated_at` newer than the one
    held, the WG distribution has refreshed, so the whole cache is dropped and the entire list
    is refetched (fetch_list.data_changed + _poll). Within the window the per-id
    _table/_seen/_inflight dedup serves the cache: a still-fresh cache is adopted on load, and
    the batch enqueue then skips every id already held while still fetching any genuinely-missing
    one. Detection of (b) is opportunistic -- it rides whatever fetch naturally happens (a
    cache-miss on select, a buy/sell, a battle in a new tank); the 7-day backstop covers the
    case where nothing triggers a fetch.
  * If a request errors (or a tank has no WG data), needs_estimate() lets the caller fall back
    to the offline estimator (domain/moe_estimate) so the bar still shows extrapolated numbers.

Fetch discipline (mirrors the old tomato provider): helpers.http.openUrl is blocking, so each
request runs on a worker thread; parsed results are adopted on the MAIN thread via a
BigWorld.callback poll loop (the worker never touches game state or WG's logger). Fail-soft:
any network/parse failure leaves the table empty -> the bar shows ticks + the current readout
without per-mark damage labels. parse_response() / fresh_table() are pure (unit-tested); the
engine bits import BigWorld / helpers lazily so this module imports under pytest.
"""
import os
import json
import threading

from moe_calculator import build_config
from moe_calculator._compat import LOG_CURRENT_EXCEPTION, LOG_NOTE
from moe_calculator.adapter import garage_roster
from moe_calculator.domain import constants
from moe_calculator.domain import fetch_list

# --- source configuration ----------------------------------------------------
REGION = "eu"                                        # this client is EU 2.3.0.1
API_URL = "https://api.worldoftanks.%s/wot/tanks/mastery/" % REGION
# The WG API application_id is a SECRET injected at build time (see build_config.py + .env);
# it is empty in an unbuilt/source checkout, which just disables fetching (fail-soft).
APP_ID = build_config.WG_APPLICATION_ID
DISTRIBUTION = "damage"
PERCENTILES = "65,85,95,100"
# WG percentile (JSON string key) -> our threshold dict key. 65/85/95 = the 1/2/3-mark
# combined-damage thresholds; 100 = the bar's right-edge goalpost (the battle interpolator
# needs all four). A tank missing any of these is skipped (unusable).
_PCT_TO_KEY = {"65": 1, "85": 2, "95": 3, "100": 100}
_TIMEOUT = 15.0
_AGENT = ("Mozilla/5.0 (compatible; 14th_ua-MoE-Calculator; "
          "+https://github.com/drizzer14/moe-calculator)")
_POLL_INTERVAL = 0.25                                # seconds between worker-done checks
_MAX_IDS_PER_REQUEST = 100                           # WG API cap on tank_id per call
_STORE_VERSION = 2                                   # on-disk cache envelope version
_LIST_VERSION = 1                                    # on-disk fetch-list envelope version
# Cache-freshness time backstop: while now < updated_at + this, the cache is served without a
# time-driven refetch. The primary invalidation is the updated_at-change trigger in _poll; this
# is the fallback for sessions where no fetch happens to reveal the change. Single source
# (shared with domain/fetch_list.needs_refetch) lives in constants.
_REVALIDATE_SECONDS = constants.REVALIDATE_SECONDS

# --- module state (main-thread only) -----------------------------------------
_table = {}            # int_cd -> {1: dmg, 2: dmg, 3: dmg, 100: dmg}
_updated_at = 0        # WG data `updated_at` (epoch s) of the newest fetch/adopted cache
_loaded = False        # something is showable (a fetch completed, or the cache adopted)
_started = False       # start() has run (caches loaded + fast-paint enqueued)
_want = {}             # int_cd -> recency epoch: the persistent fetch list (owned tanks only)
_temp = set()          # int_cds selected-but-not-yet-played this session (in-memory only)
_owned = None          # last-known owned intCD set; None until first observed (buy/sell diff)
_list_ready = False    # the session-open bootstrap/purge of _want has run
_ready_listeners = []  # no-arg callbacks fired on the main thread after each fetch round
_queue = []            # pending jobs, each a list of <=100 int tank_ids
_inflight = set()      # tank_ids queued/fetching (dedup)
_seen = set()          # tank_ids a fetch has completed for (incl. no-data) -> don't refetch
_busy = False          # a fetch thread is currently running
_thread = None
_poll_cb = None


# --- pure helpers (unit-tested) ----------------------------------------------

def parse_response(text):
    """Parse a WG /tanks/mastery JSON body into (table, updated_at):
      table      = {int_cd: {1,2,3,100: dmg}} -- a tank included only if all four percentiles
                   are present;
      updated_at = the response's data.updated_at (epoch s), or None.
    Any error (non-ok status, bad JSON, missing fields) yields ({}, None). Pure -- safe on the
    worker thread."""
    table = {}
    if not text:
        return table, None
    try:
        blob = json.loads(text)
    except (ValueError, TypeError):
        return table, None
    if not isinstance(blob, dict) or blob.get("status") != "ok":
        return table, None
    data = blob.get("data")
    if not isinstance(data, dict):
        return table, None
    updated_at = data.get("updated_at")
    try:
        updated_at = int(updated_at) if updated_at is not None else None
    except (TypeError, ValueError):
        updated_at = None
    dist = data.get("distribution")
    if not isinstance(dist, dict):
        return table, updated_at
    for tid, pcts in dist.items():
        if not isinstance(pcts, dict):
            continue
        try:
            cd = int(tid)
        except (TypeError, ValueError):
            continue
        row = {}
        ok = True
        for pct_str, key in _PCT_TO_KEY.items():
            val = pcts.get(pct_str)
            if val is None:
                ok = False
                break
            try:
                row[key] = int(val)
            except (TypeError, ValueError):
                ok = False
                break
        if ok:
            table[cd] = row
    return table, updated_at


def fresh_table(blob, now_epoch, region):
    """Return the cached {int_cd: {1,2,3,100: dmg}} table from a persisted envelope iff it is
    the current store version, same region, and still within the revalidation window
    (now_epoch < updated_at + 7d); otherwise {} (stale -> refetch). Pure."""
    if not isinstance(blob, dict):
        return {}
    if blob.get("version") != _STORE_VERSION or blob.get("region") != region:
        return {}
    updated_at = blob.get("updated_at")
    try:
        if now_epoch >= int(updated_at) + _REVALIDATE_SECONDS:
            return {}
    except (TypeError, ValueError):
        return {}
    table = {}
    for tid, row in (blob.get("table") or {}).items():
        try:
            cd = int(tid)
            table[cd] = dict((int(k), int(v)) for k, v in row.items())
        except (TypeError, ValueError, AttributeError):
            continue
    return table


def valid_list(blob, region):
    """Return the persisted fetch list as {int_cd: recency_epoch} iff the envelope is the
    current list version and same region; otherwise {}. Coerces string keys/values to int,
    dropping junk rows. Mirrors fresh_table minus the time window -- membership has no freshness
    clock (it expires only via the 7-day purge, which needs live `now`). Pure."""
    if not isinstance(blob, dict):
        return {}
    if blob.get("version") != _LIST_VERSION or blob.get("region") != region:
        return {}
    out = {}
    for cd, rec in (blob.get("ids") or {}).items():
        try:
            out[int(cd)] = int(rec)
        except (TypeError, ValueError):
            continue
    return out


# --- public API (the moe_data router surface) --------------------------------

def get_thresholds(int_cd):
    """Return {1,2,3,100: dmg} for a vehicle, or {} if unknown / not fetched yet. Kicks off the
    one-time start() on first call; on a cache miss, enqueues a single-tank fetch (the ready
    listener re-pushes to reveal the labels when it lands)."""
    if not _started:
        start()
    else:
        _ensure_list_ready()    # retry the list bootstrap/purge once the items cache is synced
    try:
        cd = int(int_cd or 0)
    except (TypeError, ValueError):
        return {}
    if not cd:
        return {}
    row = _table.get(cd)
    if row:
        return row
    if cd not in _seen:
        _enqueue([cd])
    return {}


def start():
    """Load the threshold cache + the persistent fetch list, enqueue the selected vehicle for
    fast first paint, then ready the list (bootstrap-if-empty / purge). Idempotent + guarded;
    re-entrant so a later call retries the list-ready once the items cache has synced."""
    global _started, _loaded
    if _started:
        _ensure_list_ready()
        return
    _started = True
    try:
        _load_cache()
        _load_list()
        if _table:
            _loaded = True
        sel = garage_roster.selected_int_cd()
        if sel:
            _enqueue([sel])
        _ensure_list_ready()
        LOG_NOTE("[moe] wgapi start (selected=%r, cached=%d, list=%d)"
                 % (sel, len(_table), len(_want)))
    except Exception:
        LOG_CURRENT_EXCEPTION()


def add_ready_listener(cb):
    """Register a no-arg callback fired on the main thread after each fetch round (so the bridge
    re-pushes and the damage labels appear). Fires immediately if data is already showable, and
    stays registered so subsequent rounds (round 2, lazy single fetches) re-push too. Guarded."""
    if _loaded:
        try:
            cb()
        except Exception:
            LOG_CURRENT_EXCEPTION()
    if cb not in _ready_listeners:
        _ready_listeners.append(cb)


def is_loaded():
    return _loaded


def needs_estimate(int_cd):
    """True when a fetch for this tank has COMPLETED but yielded no thresholds -- i.e. the WG
    request errored or the API returned no data for it, so waiting won't help and the caller
    should fall back to the offline estimator. False while a fetch is still pending (the caller
    should wait) or when the tank is already cached."""
    try:
        cd = int(int_cd or 0)
    except (TypeError, ValueError):
        return False
    return bool(cd) and cd in _seen and cd not in _table


# --- fetch-list mutators (called by the bridge on buy/sell/select/battle) -----

def reconcile_ownership():
    """Detect buys/sells by diffing the current garage against the last-known owned set, and
    route each change through on_vehicle_bought / on_vehicle_sold. Called on every items-cache
    sync. This is deliberately payload-free: the resync `updateReason` + `invalidItems` are
    unreliable across client versions (a full-invalidate resync carries no per-item diff), but
    the owned-vehicle set is always authoritative. A sync that doesn't change ownership is a
    no-op (empty diffs), so the frequent stats/dossier resyncs after every battle cost nothing.
    The first observation only seeds the baseline (no diff), so entering the garage is not seen
    as a mass buy. Guarded."""
    global _owned
    try:
        new_owned = set(garage_roster.owned_int_cds())
        if not new_owned:
            return  # items cache not synced yet -> don't treat as a mass-sell
        if _owned is None:
            _owned = new_owned  # first observation: seed the baseline, no diff
            return
        bought = new_owned - _owned
        sold = _owned - new_owned
        _owned = new_owned
        for cd in sold:
            on_vehicle_sold(cd)
        for cd in bought:
            on_vehicle_bought(cd)
    except Exception:
        LOG_CURRENT_EXCEPTION()


def on_vehicle_bought(int_cd):
    """A vehicle entered the garage -> add it to the permanent list, stamped recency = now (so
    an unplayed purchase survives the 7-day purge for ~7 days). Evicts the least-recently-
    played member if the list is full. Guarded."""
    try:
        cd = int(int_cd or 0)
        if not cd:
            return
        evicted = _promote(cd)
        LOG_NOTE("[moe] bought %d (evicted=%r) -> list=%d" % (cd, evicted, len(_want)))
    except Exception:
        LOG_CURRENT_EXCEPTION()


def on_vehicle_sold(int_cd):
    """A vehicle left the garage -> drop it from the permanent list (and the temp set). Leaves
    any cached thresholds in _table/_seen alone (harmless, bounded by the 7-day envelope). Guarded."""
    global _want
    try:
        cd = int(int_cd or 0)
        if not cd:
            return
        if cd in _want:
            kept = fetch_list.remove_id(list(_want.keys()), cd)
            _want = dict((c, _want[c]) for c in kept)
            _save_list()
        _temp.discard(cd)
        LOG_NOTE("[moe] sold %d -> list=%d" % (cd, len(_want)))
    except Exception:
        LOG_CURRENT_EXCEPTION()


def on_vehicle_selected(int_cd):
    """A vehicle was selected in the garage -> track it in the session-only temp set (unless it
    is already permanent). The threshold fetch itself is covered by get_thresholds() on the
    push that follows selection, so this only records the not-yet-committed selection. Guarded."""
    try:
        cd = int(int_cd or 0)
        if cd and cd not in _want:
            _temp.add(cd)
    except Exception:
        LOG_CURRENT_EXCEPTION()


def on_battle_played(int_cd):
    """A battle finished in this vehicle -> promote it from the temp set to the permanent list
    (evicting the least-recently-played member if full), stamped recency = now. Guarded."""
    try:
        cd = int(int_cd or 0)
        if not cd:
            return
        evicted = _promote(cd)
        LOG_NOTE("[moe] battle played in %d (evicted=%r) -> list=%d" % (cd, evicted, len(_want)))
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _promote(cd):
    """Add `cd` to the permanent list (evicting the least-recently-played member when full),
    stamp its recency = now (buy/play time), drop it from the temp set, persist, and enqueue its
    fetch. Returns the evicted intCD or None. Shared by on_vehicle_bought / on_battle_played."""
    global _want
    now = _now_epoch()
    ids, evicted = fetch_list.add_with_eviction(
        list(_want.keys()), _want, cd, constants.FETCH_LIST_CAP)
    _want = dict((c, now if c == cd else _want.get(c, 0)) for c in ids)
    _temp.discard(cd)
    _save_list()
    _enqueue([cd])
    return evicted


# --- fetch machinery (main-thread only, except the worker's run()) -----------

def _ensure_list_ready():
    """Ready the persistent fetch list exactly once per session, as soon as the garage roster is
    readable (owned is empty until the items cache syncs -> retried on the next call, and we
    NEVER wipe a persisted list on a premature run).

    Empty list -> bootstrap from the selected vehicle + owned tanks played in the last 7 days.
    Non-empty -> drop ids no longer owned (garage-only membership) and purge tanks not played in
    the last 7 days. Either way, recency is the max of the stored (buy-time/last-seen) value and
    the live dossier last-battle time, so a played tank refreshes while a bought-unplayed tank
    keeps its protection. Then batch-fetch the whole list (the _table/_seen dedup skips what we
    already hold and fetches only the missing ids)."""
    global _want, _list_ready, _owned
    if _list_ready:
        return
    try:
        owned = set(garage_roster.owned_int_cds())
        if not owned:
            return  # items cache not synced yet -> retry (never wipe a persisted list)
        _owned = owned  # baseline for buy/sell reconciliation (see reconcile_ownership)
        now = _now_epoch()
        all_ids = owned | set(_want.keys())
        live = garage_roster.recency_map(all_ids)
        merged = dict((cd, max(int(_want.get(cd, 0)), int(live.get(cd, 0)))) for cd in all_ids)
        if not _want:
            sel = garage_roster.selected_int_cd()
            recent = garage_roster.recent_int_cds(constants.FETCH_LIST_CAP)
            ids = fetch_list.bootstrap_ids(sel, recent, merged, now, constants.FETCH_LIST_CAP)
        else:
            owned_want = [cd for cd in _want.keys() if cd in owned]
            ids, purged = fetch_list.purge_stale(owned_want, merged, now)
            if purged:
                LOG_NOTE("[moe] fetch list purged %d stale/sold tanks" % len(purged))
        _want = dict((cd, merged.get(cd, now)) for cd in ids)
        _list_ready = True
        _save_list()
        due = fetch_list.needs_refetch(_updated_at, now)
        LOG_NOTE("[moe] fetch list ready: %d tanks (data refresh due=%s)" % (len(_want), due))
        _enqueue(list(_want.keys()))
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _enqueue(tank_ids):
    """Queue fetch job(s) for tank_ids, skipping any already cached / in-flight / seen, chunked
    to the API's 100-id cap. Starts the pump."""
    ids = []
    for cd in tank_ids:
        if cd and cd not in _table and cd not in _inflight and cd not in _seen:
            ids.append(cd)
    if not ids:
        return
    for i in range(0, len(ids), _MAX_IDS_PER_REQUEST):
        chunk = ids[i:i + _MAX_IDS_PER_REQUEST]
        _inflight.update(chunk)
        _queue.append(chunk)
    _pump()


def _pump():
    """Start the next queued job if idle. Main-thread only."""
    global _busy, _thread
    if _busy or not _queue or _FetchThread is None:
        return
    try:
        chunk = _queue.pop(0)
        _busy = True
        _thread = _FetchThread(_build_url(chunk))
        _thread.chunk = chunk
        _thread.start()
        _schedule_poll()
    except Exception:
        _busy = False
        LOG_CURRENT_EXCEPTION()


def _poll():
    """Main-thread poll: when the current worker finishes, adopt its parsed rows, persist, fire
    ready listeners, and start the next queued job."""
    global _loaded, _busy, _thread, _poll_cb, _updated_at
    _poll_cb = None
    try:
        thread = _thread
        if thread is not None and thread.is_alive():
            _schedule_poll()
            return
        chunk = getattr(thread, "chunk", []) if thread is not None else []
        result = getattr(thread, "result", None) if thread is not None else None
        upd = getattr(thread, "updated_at", None) if thread is not None else None
        error = getattr(thread, "error", None) if thread is not None else None
        if error:
            LOG_NOTE("[moe] wgapi fetch worker failed:\n%s" % error)
        stale = False
        if result:
            # A fetch that reveals a NEW WG `updated_at` means the distribution refreshed and
            # every cached threshold is now stale -> drop the whole cache and refetch the list.
            stale = fetch_list.data_changed(_updated_at, upd)
            if stale:
                LOG_NOTE("[moe] wgapi updated_at changed %r -> %r; refetching whole list"
                         % (_updated_at, upd))
                _table.clear()
                _seen.clear()
            _table.update(result)  # the just-fetched rows are current under the new updated_at
            if upd:
                _updated_at = upd
            _save_cache()
        for cd in chunk:
            _inflight.discard(cd)
            _seen.add(cd)
        _loaded = True
        _busy = False
        _thread = None
        LOG_NOTE("[moe] wgapi fetch done: +%d tanks (%d cached)"
                 % (len(result or {}), len(_table)))
        _notify_ready()
        if stale:
            # _table/_seen were cleared above (the current chunk re-added), so this re-fetches
            # every OTHER list member fresh; the current chunk is skipped as already-current.
            _enqueue(list(_want.keys()))
        _pump()
    except Exception:
        _busy = False
        _thread = None
        _loaded = True
        LOG_CURRENT_EXCEPTION()


def _notify_ready():
    for cb in list(_ready_listeners):
        try:
            cb()
        except Exception:
            LOG_CURRENT_EXCEPTION()


def _schedule_poll():
    global _poll_cb
    try:
        import BigWorld
        _poll_cb = BigWorld.callback(_POLL_INTERVAL, _poll)
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _build_url(tank_ids):
    ids = ",".join(str(int(cd)) for cd in tank_ids)
    return ("%s?application_id=%s&distribution=%s&percentile=%s&tank_id=%s"
            % (API_URL, APP_ID, DISTRIBUTION, PERCENTILES, ids))


def _fetch_text(url):
    """Blocking fetch via the client's own HTTP helper (worker thread only)."""
    from helpers import http
    resp = http.openUrl(url, timeout=_TIMEOUT, agent=_AGENT)
    if resp is not None and resp.isValid() and resp.hasData():
        return resp.getData()
    return None


# --- threshold cache persistence ---------------------------------------------

def _now_epoch():
    """Current wall-clock as epoch seconds (compared against updated_at + 7d)."""
    import time
    return time.time()


def _store_path():
    """Absolute path to the persisted threshold cache, under the client's writable prefs dir.
    `helpers` is imported lazily so this module imports under pytest (tests monkeypatch)."""
    import helpers
    base = helpers.getPreferencesDirPath()
    return os.path.join(base, "mods_data", "14th_ua_moe", "moe_wgapi_cache.json")


def _load_cache():
    """Adopt a still-fresh cache from disk into _table (within updated_at + 7d). Guarded ->
    no-op on any error / stale envelope."""
    global _updated_at
    try:
        path = _store_path()
        if not os.path.isfile(path):
            return
        with open(path, "rb") as fh:
            blob = json.loads(fh.read().decode("utf-8"))
        table = fresh_table(blob, _now_epoch(), REGION)
        if table:
            _table.update(table)
            try:
                _updated_at = int(blob.get("updated_at") or 0)
            except (TypeError, ValueError):
                pass
            LOG_NOTE("[moe] wgapi cache adopted: %d tanks (fresh)" % len(table))
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _save_cache():
    """Persist _table to disk atomically, stamped with the data's updated_at + region. Guarded
    so a read-only/full disk degrades to in-memory-only rather than raising into a push."""
    try:
        path = _store_path()
        directory = os.path.dirname(path)
        if not os.path.isdir(directory):
            os.makedirs(directory)
        blob = {"version": _STORE_VERSION, "updated_at": _updated_at, "region": REGION,
                "table": dict((str(cd), dict((str(k), v) for k, v in row.items()))
                              for cd, row in _table.items())}
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


# --- persistent fetch list ---------------------------------------------------

def _list_store_path():
    """Absolute path to the persistent fetch list, a sibling of the threshold cache under the
    client's writable prefs dir. `helpers` imported lazily (imports under pytest)."""
    import helpers
    base = helpers.getPreferencesDirPath()
    return os.path.join(base, "mods_data", "14th_ua_moe", "moe_fetch_list.json")


def _load_list():
    """Adopt the persisted fetch list into _want. Guarded -> no-op on any error / wrong version
    or region (a fresh, empty list then bootstraps on _ensure_list_ready)."""
    global _want
    try:
        path = _list_store_path()
        if not os.path.isfile(path):
            return
        with open(path, "rb") as fh:
            blob = json.loads(fh.read().decode("utf-8"))
        ids = valid_list(blob, REGION)
        if ids:
            _want = dict(ids)
            LOG_NOTE("[moe] fetch list loaded: %d tanks" % len(_want))
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _save_list():
    """Persist _want to disk atomically (same tmp+rename idiom as _save_cache). Guarded so a
    read-only/full disk degrades to in-memory-only rather than raising into a mutator."""
    try:
        path = _list_store_path()
        directory = os.path.dirname(path)
        if not os.path.isdir(directory):
            os.makedirs(directory)
        blob = {"version": _LIST_VERSION, "region": REGION,
                "ids": dict((str(cd), int(rec)) for cd, rec in _want.items())}
        tmp = path + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(json.dumps(blob).encode("utf-8"))
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
        os.rename(tmp, path)
    except Exception:
        LOG_CURRENT_EXCEPTION()


# --- worker thread -----------------------------------------------------------

try:
    class _FetchThread(threading.Thread):
        """Downloads + parses one job (<=100 tank_ids) off the main thread. Stores the parsed
        dict on self.result (None on failure) and, on failure, the traceback on self.error.
        Never touches game state or WG's logger -- the main-thread poll adopts result + emits
        any stashed traceback."""

        def __init__(self, url):
            threading.Thread.__init__(self)
            self.url = url
            self.chunk = []
            self.result = None
            self.updated_at = None
            self.error = None
            self.name = "MoE wgapi downloader"
            self.daemon = True

        def run(self):
            try:
                text = _fetch_text(self.url)
                self.result, self.updated_at = parse_response(text)
            except Exception:
                import traceback
                self.error = traceback.format_exc()
                self.result = None
except Exception:  # pragma: no cover - threading always present; defensive only
    _FetchThread = None
