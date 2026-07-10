# -*- coding: utf-8 -*-
"""tomato.gg MoE-threshold provider (the GitHub-release data source).

Fetch + cache the external Marks-of-Excellence damage-threshold table. Selected by the
`moe_data` router when build_config.MOE_DATA_SOURCE == "tomato" (the default / GitHub build);
the WGMods build uses the offline estimator (moe_offline) instead. This module is unchanged
from the original single-source implementation.

The combined-damage required for 65/85/95% (1/2/3 marks) is computed server-side and never
sent to the client, so we fetch it from tomato.gg's public MoE page. That page is App-Router
SSR: the full per-tank table (~768 tanks) is embedded in the HTML as JSON records of the shape
{"65":D1,"85":D2,"95":D3,"100":D4,"id":<WG tank id>,...}. We fetch it ONCE per client session
and cache in memory, keyed by WG tank id (== the client vehicle intCD).

Fetch discipline (mirrors the client's RSSDownloader): helpers.http.openUrl is blocking, so it
runs on a worker thread; the parsed table is handed back to the MAIN thread via a
BigWorld.callback poll loop (never touch game state from the thread). Fail-soft: any
network/parse failure just leaves the table empty -- the bar then shows ticks + the current
readout without per-mark damage labels.

parse_table() is pure (no game imports) and unit-tested; the fetch/poll code imports BigWorld +
helpers.http lazily so this module still imports under pytest.
"""
import re

from moe_calculator._compat import LOG_CURRENT_EXCEPTION, LOG_NOTE

# --- source configuration ----------------------------------------------------
SERVER = "EU"                                   # this client is EU 2.3.0.1
URL = "https://tomato.gg/moe/%s" % SERVER
_TIMEOUT = 15.0
_AGENT = ("Mozilla/5.0 (compatible; 14th_ua-MoE-Calculator/0.1.0; "
          "+https://github.com/drizzer14/moe-calculator)")
_POLL_INTERVAL = 0.25                           # seconds between worker-done checks

# Each embedded record: the three mark thresholds + 100% + the tank id, in that order.
# We capture the "100" value too (the combined damage for the 100th percentile -- the
# bar's right-edge goalpost), pinned to the field names/order tomato.gg emits; a markup
# change makes this yield nothing -> graceful degrade (no labels), not a crash.
_RECORD_RX = re.compile(r'"65":(\d+),"85":(\d+),"95":(\d+),"100":(\d+),"id":(\d+)')

# --- module state (main-thread only) -----------------------------------------
_table = {}            # int_cd -> {1: dmg, 2: dmg, 3: dmg, 100: dmg}
_loaded = False        # a fetch has completed (successfully or not)
_loading = False       # a fetch is in flight
_thread = None
_poll_cb = None
_ready_listeners = []   # called (no args) on the main thread when a fetch completes


def parse_table(text):
    """Extract {tank_id: {1: dmg, 2: dmg, 3: dmg, 100: dmg}} from the tomato.gg MoE page
    HTML. Key 100 is the 100th-percentile combined damage (the bar's right-edge goalpost);
    keys 1/2/3 are the mark thresholds. Pure -- safe on the worker thread / in unit tests."""
    table = {}
    if not text:
        return table
    for m in _RECORD_RX.finditer(text):
        d1, d2, d3, d4, tid = (m.group(1), m.group(2), m.group(3), m.group(4), m.group(5))
        try:
            table[int(tid)] = {1: int(d1), 2: int(d2), 3: int(d3), 100: int(d4)}
        except (TypeError, ValueError):
            continue
    return table


def get_thresholds(int_cd):
    """Return {1: dmg, 2: dmg, 3: dmg, 100: dmg} for a vehicle, or {} if unknown / not
    loaded yet. Lazily kicks off the one-time fetch on first call."""
    if not _loaded and not _loading:
        start()
    try:
        return _table.get(int(int_cd or 0), {})
    except (TypeError, ValueError):
        return {}


def add_ready_listener(cb):
    """Register a no-arg callback fired (once per fetch) on the main thread when the table
    finishes loading, so the bridge can re-push and reveal the damage labels. If the fetch
    already completed before this call, fire the callback immediately -- otherwise a late
    subscriber (armed after load) would silently never fire (`_poll` fires listeners exactly
    once). Guarded so a raising callback can't propagate into the caller."""
    if _loaded:
        try:
            cb()
        except Exception:
            LOG_CURRENT_EXCEPTION()
        return
    if cb not in _ready_listeners:
        _ready_listeners.append(cb)


def is_loaded():
    return _loaded


def start():
    """Begin the one-time background fetch if not already loading/loaded. Safe to call
    repeatedly (idempotent) and guarded so a missing engine can't raise into a mount."""
    global _loading, _thread, _poll_cb
    if _loaded or _loading:
        return
    try:
        import threading
        _loading = True
        _thread = _FetchThread(URL)
        _thread.start()
        _schedule_poll()
        LOG_NOTE("[moe] fetch started: %s" % URL)
    except Exception:
        _loading = False
        LOG_CURRENT_EXCEPTION()


def _schedule_poll():
    global _poll_cb
    try:
        import BigWorld
        _poll_cb = BigWorld.callback(_POLL_INTERVAL, _poll)
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _poll():
    """Main-thread poll: when the worker finishes, adopt its parsed table and notify."""
    global _loaded, _loading, _thread, _poll_cb
    _poll_cb = None
    try:
        thread = _thread
        if thread is not None and thread.is_alive():
            _schedule_poll()
            return
        result = getattr(thread, "result", None) if thread is not None else None
        # Emit any traceback the worker stashed -- on the MAIN thread, so the worker never
        # has to touch WG's logger itself (see _FetchThread's invariant).
        error = getattr(thread, "error", None) if thread is not None else None
        if error:
            LOG_NOTE("[moe] fetch worker failed:\n%s" % error)
        if result:
            _table.update(result)
        _loaded = True
        _loading = False
        _thread = None
        LOG_NOTE("[moe] fetch done: %d tanks" % len(_table))
        for cb in list(_ready_listeners):
            try:
                cb()
            except Exception:
                LOG_CURRENT_EXCEPTION()
    except Exception:
        _loaded = True
        _loading = False
        _thread = None
        LOG_CURRENT_EXCEPTION()


def _fetch_text(url):
    """Blocking fetch via the client's own HTTP helper (worker thread only)."""
    from helpers import http
    resp = http.openUrl(url, timeout=_TIMEOUT, agent=_AGENT)
    if resp is not None and resp.isValid() and resp.hasData():
        return resp.getData()
    return None


try:
    import threading as _threading

    class _FetchThread(_threading.Thread):
        """Downloads + parses the MoE table off the main thread. Stores the parsed dict
        on self.result (None on failure) and, on failure, the formatted traceback on
        self.error. Never touches game state -- including NOT logging from here: the
        main-thread poll adopts the result AND emits any stashed traceback, so WG's logger
        is only ever touched on the main thread (honouring this invariant)."""

        def __init__(self, url):
            _threading.Thread.__init__(self)
            self.url = url
            self.result = None
            self.error = None
            self.name = "MoE table downloader"
            self.daemon = True

        def run(self):
            try:
                text = _fetch_text(self.url)
                self.result = parse_table(text)
            except Exception:
                import traceback
                self.error = traceback.format_exc()
                self.result = None
except Exception:  # pragma: no cover - threading always present; defensive only
    _FetchThread = None


# --- router-facing extra -----------------------------------------------------
# The offline provider records per-player samples; the router calls record_sample() on
# whichever provider is active, so tomato supplies an inert version.

def record_sample(int_cd, percentile, avg_damage):
    """No-op: the tomato source needs no per-player samples (the router calls this on every
    garage read regardless of the active source)."""
    return
