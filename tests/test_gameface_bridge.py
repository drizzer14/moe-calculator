# -*- coding: utf-8 -*-
"""Engine-free tests for the garage bridge's reverse channel (`_on_set_position`).

The bridge normally imports live game symbols at module top (helpers, skeletons, Wulf,
OpenWG), so -- mirroring conftest's documented fake-game-symbol technique -- we install bare
stub modules into sys.modules BEFORE importing gameface_bridge. These stubs only satisfy the
imports; every assertion drives real behavior by spying on `mod_settings.set_position`, never
these stubs. Only `_on_set_position`'s pure guard/parse logic is exercised here; the mount /
inject / marshal path needs the live client and is out of scope for a unit test."""
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


# CurrentVehicle + BigWorld are already stubbed by conftest; add the rest gameface_bridge needs.
_stub("helpers", dependency=types.SimpleNamespace(instance=lambda *a, **k: None))
_stub("skeletons.gui.shared", IItemsCache=object)


class _StubViewModel(object):
    def __init__(self, *a, **k):
        pass


class _StubArray(object):
    def __init__(self, *a, **k):
        pass


_stub("frameworks.wulf", ViewModel=_StubViewModel, Array=_StubArray)
_stub("openwg_gameface", gf_mod_inject=lambda *a, **k: None)

from moe_calculator.bridge import gameface_bridge
from moe_calculator.adapter import engine_adapter
from moe_calculator.adapter import moe_wgapi
from moe_calculator.adapter import baseline_cache


def teardown_function(_):
    baseline_cache.clear()


class _WulfMap(object):
    """A Wulf-wrapped map: not a dict, but exposes .get(key) -- as delivered by the engine."""
    def __init__(self, d):
        self._d = d

    def get(self, key):
        return self._d.get(key)


def _spy_set_position(monkeypatch):
    """Replace mod_settings.set_position with a recorder and return the call list."""
    calls = []
    monkeypatch.setattr(
        gameface_bridge.mod_settings, "set_position",
        lambda x, y, w=0, h=0: calls.append((x, y, w, h)))
    return calls


def test_persists_a_real_pin(monkeypatch):
    # A positive (x, y) drag release persists, carrying the capture viewport (w, h).
    calls = _spy_set_position(monkeypatch)
    gameface_bridge._on_set_position({"x": 100, "y": 200, "w": 1920, "h": 1080})
    assert calls == [(100, 200, 1920, 1080)]


def test_persists_from_wulf_wrapped_map(monkeypatch):
    # The engine may deliver a Wulf map object rather than a plain dict.
    calls = _spy_set_position(monkeypatch)
    gameface_bridge._on_set_position(_WulfMap({"x": 50, "y": 60, "w": 800, "h": 600}))
    assert calls == [(50, 60, 800, 600)]


def test_persists_without_viewport(monkeypatch):
    # w/h absent -> stored as 0 (unknown), but a valid pin still persists.
    calls = _spy_set_position(monkeypatch)
    gameface_bridge._on_set_position({"x": 10, "y": 20})
    assert calls == [(10, 20, 0, 0)]


def test_drops_when_x_not_positive(monkeypatch):
    # x <= 0 is the auto sentinel / a bad measurement -> never clobber the stored pin.
    calls = _spy_set_position(monkeypatch)
    gameface_bridge._on_set_position({"x": 0, "y": 200, "w": 1920, "h": 1080})
    gameface_bridge._on_set_position({"x": -5, "y": 200, "w": 1920, "h": 1080})
    assert calls == []


def test_drops_when_y_not_positive(monkeypatch):
    calls = _spy_set_position(monkeypatch)
    gameface_bridge._on_set_position({"x": 100, "y": 0, "w": 1920, "h": 1080})
    gameface_bridge._on_set_position({"x": 100, "y": -1, "w": 1920, "h": 1080})
    assert calls == []


def test_drops_the_parse_failure_signature(monkeypatch):
    # A missing / unparseable map parses to (0, 0) -- the drop guard swallows it.
    calls = _spy_set_position(monkeypatch)
    gameface_bridge._on_set_position({})
    gameface_bridge._on_set_position({"x": "nope", "y": "nope"})
    assert calls == []


def test_never_raises_into_js(monkeypatch):
    # A handler that raised would propagate into the Wulf command dispatch; it must swallow.
    def _boom(*a, **k):
        raise RuntimeError("MSA exploded")

    monkeypatch.setattr(gameface_bridge.mod_settings, "set_position", _boom)
    # Must not raise.
    gameface_bridge._on_set_position({"x": 100, "y": 200, "w": 1920, "h": 1080})


# --- widget-independent priming (decouple data-priming from the garage widget) ---------------
# The two widget-independent hooks (_on_vehicle_changed / _on_sync_completed) must prime the
# in-battle overlay's data -- seed the career baseline AND kick the WG threshold fetch -- even when
# the garage widget is OFF, because then refresh()->push()->build_snapshot() (the usual prime path)
# never runs. When the widget is ON that push path already primes, so the hook must NOT double-read.
# engine_adapter.prime_current is the single side-effecting seam; we drive it through its own
# stubbed reads (mirroring test_engine_adapter) and assert the observable effects at the bridge.

class _Veh(object):
    intCD = 1073
    nationName = "germany"


class _CV(object):
    def __init__(self, present, item=None):
        self._present = present
        self.item = item

    def isPresent(self):
        return self._present


def _prime_seams(monkeypatch):
    """Stub engine_adapter's read seams so prime_current/build_snapshot run game-closed, recording
    each dossier read (`reads`) and each threshold request (`thresh`). A synced 5-tuple read seeds
    the baseline; a non-empty threshold dict keeps build_snapshot off the estimator branch."""
    reads, thresh = [], []
    monkeypatch.setattr(engine_adapter, "g_currentVehicle", _CV(present=True, item=_Veh()))
    monkeypatch.setattr(engine_adapter, "_read_moe",
                        lambda cd: reads.append(cd) or (2, 73.7, 1800, 100, True))
    monkeypatch.setattr(engine_adapter.moe_wgapi, "get_thresholds",
                        lambda cd: thresh.append(cd) or {65: 1, 85: 2, 95: 3, 100: 4})
    monkeypatch.setattr(engine_adapter.sample_log, "resolve", lambda *a: False)
    return reads, thresh


def test_vehicle_changed_widget_off_primes_baseline_and_thresholds(monkeypatch):
    # Widget OFF (_active is None) + a current vehicle selected -> _on_vehicle_changed's refresh()
    # no-ops, so the hook itself must prime: seed the baseline AND request the threshold fetch, with
    # NO widget ever mounted.
    monkeypatch.setattr(gameface_bridge, "_active", None)
    reads, thresh = _prime_seams(monkeypatch)
    gameface_bridge._on_vehicle_changed()
    assert baseline_cache.get(1073) == (73.7, 1800)   # baseline seeded
    assert thresh == [1073]                            # threshold fetch requested
    assert reads == [1073]                             # exactly one dossier read, no widget push


def test_sync_completed_widget_off_primes_baseline_and_thresholds(monkeypatch):
    # Same widget-OFF priming, driven by the items-cache sync hook (post-battle career update).
    # The ownership-reconcile + scheduled refresh are neighbours out of scope here -> stubbed.
    monkeypatch.setattr(gameface_bridge, "_active", None)
    monkeypatch.setattr(moe_wgapi, "start", lambda: None)
    monkeypatch.setattr(moe_wgapi, "reconcile_ownership", lambda: None)
    monkeypatch.setattr(gameface_bridge, "_schedule_refresh", lambda: None)
    reads, thresh = _prime_seams(monkeypatch)
    gameface_bridge._on_sync_completed()
    assert baseline_cache.get(1073) == (73.7, 1800)
    assert thresh == [1073]
    assert reads == [1073]


def test_widget_on_does_not_double_prime(monkeypatch):
    # Widget ON (_active set): refresh()->push()->build_snapshot() already primes once, so the hook's
    # `if _active is None` guard must skip its own prime -> exactly ONE dossier read per event, not
    # two. The full Wulf marshal path needs the live client (out of scope), so push stands in as
    # build_snapshot -- which IS where the push path's prime happens.
    reads, thresh = _prime_seams(monkeypatch)
    monkeypatch.setattr(gameface_bridge, "_active", (object(), object()))
    monkeypatch.setattr(gameface_bridge, "_host_alive", lambda: True)
    monkeypatch.setattr(gameface_bridge, "push",
                        lambda rvm, host_vm=None: engine_adapter.build_snapshot())
    gameface_bridge._on_vehicle_changed()
    assert reads == [1073]   # one read via the push path; the hook did NOT prime a second time


def test_sync_ordering_keeps_the_persisted_fetch_list(monkeypatch, tmp_path):
    # THE ordering fix: _on_sync_completed calls moe_wgapi.start() (which _load_list()s the persisted
    # fetch list into _want) BEFORE reconcile_ownership() (which _save_list()s _want on a buy/sell).
    # With the widget off, start() would otherwise never have run this session, so a reconcile that
    # persists a freshly-bought tank into an EMPTY in-memory _want clobbers the on-disk list. Seed a
    # prior-session list on disk, stage a buy for reconcile to persist, and assert the persisted ids
    # survive. RED if start() is moved back after reconcile_ownership().
    NOW = 1_700_000_000
    monkeypatch.setattr(moe_wgapi, "REGION", "eu")
    monkeypatch.setattr(moe_wgapi, "data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(moe_wgapi, "_now_epoch", lambda: NOW)
    # A prior session persisted these two owned tanks.
    monkeypatch.setattr(moe_wgapi, "_want", {111: NOW, 222: NOW})
    moe_wgapi._save_list()
    # Fresh session: nothing loaded, an owned baseline from an earlier sync, and 333 freshly bought
    # in the current garage so reconcile has a buy to persist.
    monkeypatch.setattr(moe_wgapi, "_want", {})
    monkeypatch.setattr(moe_wgapi, "_started", False)
    monkeypatch.setattr(moe_wgapi, "_list_ready", False)
    monkeypatch.setattr(moe_wgapi, "_owned", {111, 222})
    monkeypatch.setattr(moe_wgapi.garage_roster, "owned_int_cds", lambda: [111, 222, 333])
    monkeypatch.setattr(moe_wgapi.garage_roster, "recency_map",
                        lambda ids: dict((cd, NOW) for cd in ids))
    monkeypatch.setattr(moe_wgapi.garage_roster, "selected_int_cd", lambda: 111)
    monkeypatch.setattr(moe_wgapi.garage_roster, "recent_int_cds", lambda n: [111, 222])
    # Isolate the ordering from the network / scheduled-refresh / prime machinery.
    monkeypatch.setattr(moe_wgapi, "_load_cache", lambda: None)
    monkeypatch.setattr(moe_wgapi, "_enqueue", lambda ids: None)
    monkeypatch.setattr(gameface_bridge, "_active", None)
    monkeypatch.setattr(gameface_bridge, "_schedule_refresh", lambda: None)
    monkeypatch.setattr(gameface_bridge.engine_adapter, "prime_current", lambda: None)

    gameface_bridge._on_sync_completed()

    persisted = moe_wgapi.valid_list(
        moe_wgapi.read_json(moe_wgapi._list_store_path()), moe_wgapi.REGION)
    assert 111 in moe_wgapi._want and 222 in moe_wgapi._want   # in-memory list preserved
    assert persisted, "list file was never written/read back"
    assert 111 in persisted and 222 in persisted               # on-disk list not clobbered
