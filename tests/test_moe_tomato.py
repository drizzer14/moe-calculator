# -*- coding: utf-8 -*-
"""State-machine tests for adapter/moe_tomato: the main-thread poll loop, idempotent start,
and the ready-hook (including the late-subscriber fire-if-already-loaded path). moe_tomato
imports BigWorld/helpers.http lazily inside the fetch functions, so the state machine is
exercisable on plain Python 3 by driving _poll directly with a fake thread and stubbing the
poll scheduler -- no network, no real threads. (Previously tests/test_moe_data.py, before
moe_data became the source router.)"""
from moe_calculator.adapter import moe_tomato


class _FakeThread(object):
    def __init__(self, alive, result):
        self._alive = alive
        self.result = result

    def is_alive(self):
        return self._alive


def _reset(monkeypatch, **state):
    """Give each test a clean module state (auto-restored by monkeypatch)."""
    monkeypatch.setattr(moe_tomato, "_table", {})
    monkeypatch.setattr(moe_tomato, "_loaded", False)
    monkeypatch.setattr(moe_tomato, "_loading", False)
    monkeypatch.setattr(moe_tomato, "_thread", None)
    monkeypatch.setattr(moe_tomato, "_poll_cb", None)
    monkeypatch.setattr(moe_tomato, "_ready_listeners", [])
    for key, value in state.items():
        monkeypatch.setattr(moe_tomato, key, value)


# --- start(): idempotent ------------------------------------------------------

def test_start_is_noop_when_already_loaded(monkeypatch):
    _reset(monkeypatch, _loaded=True)
    scheduled = []
    monkeypatch.setattr(moe_tomato, "_schedule_poll", lambda: scheduled.append(True))
    moe_tomato.start()
    assert scheduled == []            # no fetch kicked
    assert moe_tomato._thread is None


def test_start_is_noop_when_already_loading(monkeypatch):
    _reset(monkeypatch, _loading=True)
    scheduled = []
    monkeypatch.setattr(moe_tomato, "_schedule_poll", lambda: scheduled.append(True))
    moe_tomato.start()
    assert scheduled == []


def test_start_kicks_fetch_when_fresh(monkeypatch):
    _reset(monkeypatch)
    scheduled = []
    started = []
    monkeypatch.setattr(moe_tomato, "_schedule_poll", lambda: scheduled.append(True))

    class _FT(object):
        def __init__(self, url):
            self.url = url

        def start(self):
            started.append(self.url)

    monkeypatch.setattr(moe_tomato, "_FetchThread", _FT)
    moe_tomato.start()
    assert moe_tomato._loading is True
    assert started == [moe_tomato.URL]
    assert scheduled == [True]


# --- _poll(): state machine ---------------------------------------------------

def test_poll_adopts_result_and_fires_listeners(monkeypatch):
    _reset(monkeypatch, _loading=True)
    fired = []
    monkeypatch.setattr(moe_tomato, "_ready_listeners", [lambda: fired.append(True)])
    monkeypatch.setattr(moe_tomato, "_thread",
                        _FakeThread(alive=False, result={1073: {1: 1, 2: 2, 3: 3, 100: 4}}))
    moe_tomato._poll()
    assert moe_tomato._loaded is True
    assert moe_tomato._loading is False
    assert moe_tomato._thread is None
    assert moe_tomato.get_thresholds(1073) == {1: 1, 2: 2, 3: 3, 100: 4}
    assert fired == [True]


def test_poll_skips_empty_result(monkeypatch):
    # An empty result dict (fetch/parse failure) is skipped by `if result:` -- the table is
    # left untouched but the fetch is marked done so the mod degrades to no-labels, not a hang.
    _reset(monkeypatch, _loading=True)
    monkeypatch.setattr(moe_tomato, "_thread", _FakeThread(alive=False, result={}))
    moe_tomato._poll()
    assert moe_tomato._loaded is True
    assert moe_tomato._table == {}


def test_poll_reschedules_while_thread_alive(monkeypatch):
    _reset(monkeypatch, _loading=True)
    rescheduled = []
    monkeypatch.setattr(moe_tomato, "_schedule_poll", lambda: rescheduled.append(True))
    monkeypatch.setattr(moe_tomato, "_thread", _FakeThread(alive=True, result=None))
    moe_tomato._poll()
    assert rescheduled == [True]
    assert moe_tomato._loaded is False   # still in flight


# --- add_ready_listener(): late-subscriber path -------------------------------

def test_add_ready_listener_queues_when_not_loaded(monkeypatch):
    _reset(monkeypatch)
    cb = lambda: None
    moe_tomato.add_ready_listener(cb)
    assert cb in moe_tomato._ready_listeners


def test_add_ready_listener_fires_immediately_when_already_loaded(monkeypatch):
    # A subscriber armed AFTER the fetch already completed must still fire (else the bridge
    # ready-hook silently never runs). It fires immediately and is NOT queued.
    _reset(monkeypatch, _loaded=True)
    fired = []
    moe_tomato.add_ready_listener(lambda: fired.append(True))
    assert fired == [True]
    assert moe_tomato._ready_listeners == []


def test_add_ready_listener_immediate_fire_is_guarded(monkeypatch):
    # A raising callback on the immediate-fire path must not propagate into the caller.
    _reset(monkeypatch, _loaded=True)

    def boom():
        raise RuntimeError("boom")

    moe_tomato.add_ready_listener(boom)   # must not raise


# --- router-facing extra ------------------------------------------------------

def test_tomato_record_sample_is_noop():
    moe_tomato.record_sample(1073, 80.0, 1500)   # must not raise (no per-player samples)
