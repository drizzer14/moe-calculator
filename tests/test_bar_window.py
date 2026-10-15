# -*- coding: utf-8 -*-
"""Engine-free tests for bridge.bar_window.BarHost's Ctrl+drag gesture: `drag(phase)`, which is the
WHOLE reposition channel -- adapter/battle_input reports "start" / "move" / "end" and each move
re-places the window ABSOLUTELY from the live cursor. The window/view hosting itself
(open_window/_place/apply_position) needs the live client and is out of scope -- only the pure-ish
placement math is covered here.

Technique is test_progress_bridge's: stub the game-only imports bar_window pulls in at module
top so it imports under pytest, then drive it against a fake window that records .move() calls
and reports back a `.position` reflecting them (mirroring the real far-sentinel self-calibration:
moving to the FAR corner reveals the movable extent)."""
import sys
import types


def _stub(name, **attrs):
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


class _Permissive(object):
    def __init__(self, *a, **k):
        pass


class _PositionAnchor(object):
    LEFT = "LEFT"
    TOP = "TOP"


_stub("frameworks.wulf", ViewSettings=_Permissive, ViewFlags=object(), WindowFlags=object(),
      WindowLayer=object(), PositionAnchor=_PositionAnchor, ViewModel=_Permissive,
      Array=_Permissive)
_stub("gui.impl.pub", ViewImpl=_Permissive, WindowImpl=_Permissive)
_stub("openwg_gameface")

import pytest

from moe_calculator.bridge import bar_window
from moe_calculator.bridge import battle_bridge
from moe_calculator.bridge import mod_settings
from moe_calculator.domain.constants import (
    PROGRESS_ANCHOR_Y_SHIFT, PROGRESS_MM_TRACK_X, PROGRESS_MM_TRACK_X_LARGE,
    PROGRESS_MM_GAP_BOTTOM)
from moe_calculator.domain.positioning import anchor_centred_reduced

# A REALISTIC surface -- 256x92 (92 is the real PROGRESS bar's shipped 1x surface height, per the
# surface-mirror derivation "progress default: ... surface_h 92"), NOT the engine's 256x256
# size-timeout FALLBACK. At 256x256 -- the fixture's old default -- the Damage-Log anchor's Y
# computation clamps to max_y for every extent these tests use, which MASKS a shift-constant read
# straight through anchor_centred_reduced's y_shift argument: a wrong-semantics value flowed in
# silently because nothing here could see past the clamp. Width is left at 256 (unrealistically
# wide, but it keeps `1664 extent + 256 surface == 1920` -- the logical-space arithmetic the
# quarter-screen-movement assertions below are built on -- unchanged).
_SURFACE = (256, 92)
_MAX = (1664, 824)                                        # the tests' default movable extent
_SPACE = (_MAX[0] + _SURFACE[0], _MAX[1] + _SURFACE[1])    # the FULL logical space it pairs with


class _FakeWindow(object):
    """Records every .move(); reports .position back as whatever the last move requested, so a
    far-sentinel clamp (bar_window._FAR, _FAR) reads back the fixture's chosen movable extent --
    exactly the self-calibration trick _extent uses on the real Wulf window.

    `.size` mirrors Wulf's own read-only Window.size (= self.proxy.windowSize, the sibling of the
    windowPosition that .position reads, in the SAME logical units). It is what lets _space recover
    the FULL logical space as extent + surface -- the term that makes the drag's gain exactly 1
    instead of (space - surface) / space. Default _SURFACE pairs the default extent 1664x824 with
    a 1920x916 logical space (see _SURFACE's own comment on why this is not 256x256)."""

    def __init__(self, max_x, max_y, size=_SURFACE):
        self._max = (max_x, max_y)
        self.size = size
        self.position = (0, 0)
        self.moves = []

    def move(self, x, y, xAnchor=None, yAnchor=None):
        self.moves.append((x, y))
        if (x, y) == (bar_window._FAR, bar_window._FAR):
            self.position = self._max
        else:
            self.position = (x, y)


class _FakeView(object):
    def __init__(self):
        pass


@pytest.fixture(autouse=True)
def _reset_settings():
    mod_settings._seed(dict(mod_settings.DEFAULTS))
    yield
    mod_settings._seed(dict(mod_settings.DEFAULTS))


def _host(max_x, max_y, y_frac=0.865, x_off=0, y_shift=PROGRESS_ANCHOR_Y_SHIFT, align=None):
    """An open, ALREADY-PLACED host: _place is what _onReady runs, so a live window always has a
    real .position by the time a drag can reach it. Placing here matters because the drag's
    ownership gate tests the cursor against that .position -- an unplaced fake window sitting at
    (0, 0) would decline every gesture.

    `y_shift` is the PURE intra-surface shift BarHost's constructor now takes (the composite
    `y_off` this fixture used to pass -- e.g. the shipped 36 -- has a DIFFERENT meaning under the
    new anchor_centred_reduced call site: it is no longer -shift+round(frac*surface_h), it is
    -shift alone, and the two are not interchangeable at the same call-site position).

    `align`, when given, is written into the live settings cache BEFORE the host is built --
    every DRAG test needs Alignment=Free now that BarHost.drag() refuses to move the bar at all
    otherwise (see test_drag_is_a_noop_under_fixed_alignment below); the _resolve-focused tests
    further down leave it None and keep exercising the DEFAULT (Fixed), which is what they test.

    The placement's own moves are then cleared so each test still reads its own from index 0. The
    extent memo is left WARM, as it is live: _place always repopulates it, which is what keeps the
    far-sentinel measurement out of the drag path (and why drag() reads .position BEFORE _extent --
    a cold read would teleport the window to the sentinel and the ownership rect would be there)."""
    if align is not None:
        mod_settings._settings[mod_settings.PROGRESS_ALIGNMENT_KEY] = align
    host = bar_window.BarHost("test.item", lambda: object(), y_frac, x_off, y_shift, y_shift,
                              PROGRESS_MM_TRACK_X, PROGRESS_MM_TRACK_X_LARGE,
                              PROGRESS_MM_GAP_BOTTOM, "[test]")
    window = _FakeWindow(max_x, max_y)
    host._active = (window, _FakeView())
    host._place(window)
    del window.moves[:]
    return host, window


def _cold_host(max_x, max_y, y_frac=0.865, x_off=0, y_shift=PROGRESS_ANCHOR_Y_SHIFT, align=None):
    """Like `_host`, but the extent memo is left COLD (never placed) -- the reachable-in-practice
    case `test_the_ownership_rect_is_read_against_the_real_position_not_a_cold_far_sentinel` pins:
    open_window() publishes `_active` BEFORE window.load() resolves, so a drag can arrive before
    _onReady's first _place() ever warms the cache, with the window still at its untouched native
    position (0, 0). `align` -- see `_host`."""
    if align is not None:
        mod_settings._settings[mod_settings.PROGRESS_ALIGNMENT_KEY] = align
    host = bar_window.BarHost("test.item", lambda: object(), y_frac, x_off, y_shift, y_shift,
                              PROGRESS_MM_TRACK_X, PROGRESS_MM_TRACK_X_LARGE,
                              PROGRESS_MM_GAP_BOTTOM, "[test]")
    window = _FakeWindow(max_x, max_y)
    host._active = (window, _FakeView())
    return host, window


# --- THE Ctrl+DRAG GESTURE, driven entirely from Python --------------------------------------
# `drag(phase)` is the whole reverse channel now: adapter/battle_input samples Ctrl + the left
# button and reports "start" / "move" / "end", and each MOVE re-places the window ABSOLUTELY from
# the live cursor (domain.positioning.cursor_top_left). No delta arrives from anywhere, so there is
# no gain factor and no dependence on the surface's mouse hit rect -- the three structural failures
# of the superseded JS delta protocol.


def _at(monkeypatch, cursor, screen=_SPACE):
    """Point bar_window's two engine reads at a fixed cursor / resolution.

    `screen` defaults to `_SPACE` -- at 1x interfaceScale, screenResolution (device px) equals the
    window's own logical space, and keeping them equal here is what makes the PIXEL-space cursor
    convention's gain come out exactly 1 in these tests (see cursor_logical's two branches)."""
    monkeypatch.setattr(bar_window, "_cursor_position", lambda: cursor)
    monkeypatch.setattr(bar_window, "_screen_resolution", lambda: screen)


def _centred(max_x, max_y, y_frac=0.865, y_shift=PROGRESS_ANCHOR_Y_SHIFT):
    # THE COMPUTED anchor bar_window.BarHost._resolve now places the Damage-Log-aligned bar with --
    # anchor_centred (the pre-reduction reference) is NOT what's live any more; see its own
    # docstring ("do NOT place with this one"). space_y is the extent plus this fixture's own
    # _SURFACE height, exactly as bar_window._space recovers it.
    space_y = max_y + _SURFACE[1]
    return anchor_centred_reduced(max_x, max_y, space_y, y_frac, y_shift)


# A cursor ON THE BAR, which every gesture now has to start from: the drag is claimed per host only
# if it began inside that host's own window rect (the fix for "Ctrl+drag anywhere dragged whichever
# bar was open, including while dragging another mod's UI"). The screen CENTRE, which these tests
# used to grab from, sits above the bar and is correctly refused.
_GRAB_PX = (960, 800)                # a point inside the centred 256x92 bar at (832, 748)
_GRAB = (0.0, 1 - 2.0 * _GRAB_PX[1] / _SPACE[1])   # ...the same point in CLIP space


# --- BLOCKED OUTRIGHT UNDER FIXED: the gate at the very top of drag() ---------------------------
# Every OTHER drag test below runs with Alignment=Free (via _host(..., align=...)); these two pin
# the opposite case -- the window must never move AND nothing must be persisted through MSA, for
# every phase of the gesture, not just "start".

def test_drag_is_a_noop_under_fixed_alignment(monkeypatch):
    # Fixed is _host's own default (align=None leaves DEFAULTS' PROGRESS_ALIGN_FIXED in place).
    host, window = _host(1664, 824)
    _at(monkeypatch, _GRAB)
    host.drag("start")
    host.drag("move")
    host.drag("end")
    assert window.moves == [], "the window moved despite Alignment=Fixed"
    assert host._grab is None and host._drag_pos is None


def test_drag_under_fixed_alignment_never_calls_set_bar_position(monkeypatch):
    # THE CALL COUNT is the real assertion (memory a-noop-mutation-and-a-fail-soft-branch-can-
    # look-identical): a value-only check could pass even if the gate ran the gesture and then
    # happened to persist the SAME coordinates back.
    calls = []
    monkeypatch.setattr(mod_settings, "set_bar_position",
                        lambda *a, **k: calls.append((a, k)))
    host, window = _host(1664, 824)
    _at(monkeypatch, _GRAB)
    host.drag("start")
    host.drag("move")
    host.drag("end")
    assert calls == [], "set_bar_position was called even though Alignment is Fixed"


def test_drag_works_normally_under_free_alignment(monkeypatch):
    # The sibling positive case: with Alignment=Free (as every other drag test in this file uses),
    # the gesture is NOT gated and behaves exactly as the rest of this section pins.
    host, window = _host(1664, 824, align=mod_settings.PROGRESS_ALIGN_FREE)
    _at(monkeypatch, _GRAB)
    host.drag("start")
    assert window.moves == []          # start never moves the bar either way
    host.drag("move")
    assert window.moves != [], "a move under Free must reposition the bar"


def test_drag_start_moves_nothing_and_records_the_grab_offset(monkeypatch):
    # THE DIFFERENCE BETWEEN "picks up where you grabbed it" AND "snaps": the gesture's first event
    # must leave the bar exactly where it was, however far the cursor is from its top-left corner.
    host, window = _host(1664, 824, align=mod_settings.PROGRESS_ALIGN_FREE)
    _at(monkeypatch, _GRAB)
    host.drag("start")
    assert window.moves == [], "start must not re-place the bar"
    assert host._grab is not None


def test_a_move_at_the_grab_point_keeps_the_bar_put(monkeypatch):
    # The grab offset, proven end to end: mapping the SAME cursor again must reproduce the
    # placement the bar was grabbed at, NOT put its corner under the cursor.
    host, window = _host(1664, 824, align=mod_settings.PROGRESS_ALIGN_FREE)
    _at(monkeypatch, _GRAB)
    host.drag("start")
    host.drag("move")
    assert window.moves[-1] == _centred(1664, 824)


def test_a_move_repositions_absolutely_and_preserves_the_grab_offset(monkeypatch):
    host, window = _host(1664, 824, align=mod_settings.PROGRESS_ALIGN_FREE)
    _at(monkeypatch, _GRAB)                            # grabbed on the bar
    host.drag("start")
    base = _centred(1664, 824)
    _at(monkeypatch, (0.5, _GRAB[1]))                  # cursor moved a quarter-screen right (y held)
    host.drag("move")
    # A quarter of the LOGICAL SPACE (1664 extent + 256 surface = 1920) to the right of where it was
    # grabbed -- offset intact on both axes, and the gain is 1, not 1664/1920.
    assert window.moves[-1] == (base[0] + 1920 // 4, base[1])


def test_a_move_with_no_start_records_the_grab_instead_of_snapping(monkeypatch):
    # Defensive, and reachable: battle_input's MOUSE wrap can latch the gesture on the first
    # movement (with the cursor raised, the button press may never reach the key dispatcher), so a
    # "move" is allowed to be the first event this host sees. It must behave like a start.
    host, window = _host(1664, 824, align=mod_settings.PROGRESS_ALIGN_FREE)
    _at(monkeypatch, _GRAB)
    host.drag("move")
    assert window.moves == []                          # ...i.e. it recorded the grab and moved nothing
    host.drag("move")
    assert window.moves[-1] == _centred(1664, 824)


def test_a_live_move_updates_the_position_without_persisting(monkeypatch):
    host, _window = _host(1664, 824, align=mod_settings.PROGRESS_ALIGN_FREE)
    calls = []
    monkeypatch.setattr(mod_settings, "set_bar_position",
                        lambda x, y, persist: calls.append((x, y, persist)))
    _at(monkeypatch, _GRAB)
    host.drag("start")
    _at(monkeypatch, (0.4, -0.4))
    host.drag("move")
    assert len(calls) == 1 and calls[0][2] is False


def test_the_gesture_end_persists_the_last_applied_position(monkeypatch):
    # v22 (Trap 3 Fix B): what gets PERSISTED is the ANCHOR POINT, not the top-left window.move()
    # actually applied -- window.moves stays in top-left space (see the drag() docstring); only the
    # value handed to set_bar_position converts.
    from moe_calculator.domain.positioning import free_anchor_point

    host, window = _host(1664, 824, align=mod_settings.PROGRESS_ALIGN_FREE)
    calls = []
    monkeypatch.setattr(mod_settings, "set_bar_position",
                        lambda x, y, persist: calls.append((x, y, persist)))
    _at(monkeypatch, _GRAB)
    host.drag("start")
    _at(monkeypatch, (0.4, -0.4))
    host.drag("move")
    host.drag("end")
    expected = free_anchor_point(window.moves[-1], _SURFACE, False)
    assert calls[-1] == (expected[0], expected[1], True)


def test_a_gesture_that_never_moved_persists_nothing(monkeypatch):
    # A stray Ctrl+click must not convert the AUTO anchor (0/0) into an explicit pin at whatever
    # the bar is currently placed at -- that would be a silent opt-out of every future anchor
    # change (a Large-mode retune, a new default) and is invisible on the day it happens.
    host, _window = _host(1664, 824, align=mod_settings.PROGRESS_ALIGN_FREE)
    calls = []
    monkeypatch.setattr(mod_settings, "set_bar_position",
                        lambda x, y, persist: calls.append((x, y, persist)))
    _at(monkeypatch, _GRAB)
    host.drag("start")
    host.drag("end")
    assert calls == []


def test_the_gesture_state_does_not_leak_into_the_next_one(monkeypatch):
    # The end must drop BOTH the grab offset and the "we moved" record, or the next gesture would
    # pick up the previous one's offset (and a click-only gesture would persist its position).
    host, _window = _host(1664, 824, align=mod_settings.PROGRESS_ALIGN_FREE)
    _at(monkeypatch, _GRAB)
    host.drag("start")
    host.drag("move")
    host.drag("end")
    assert host._grab is None and host._drag_pos is None


def test_the_grab_is_measured_from_the_windows_actual_position_not_resolve(monkeypatch):
    # Bug A: the grab offset must come from where the window ACTUALLY sits (window.position), NOT
    # from _resolve() -- the two diverge when the engine clamped a Free pin, or the minimap size /
    # interface scale changed since the last _place. Grabbing off _resolve() teleports the bar by
    # that divergence on the first move. (Revert -- grab from _resolve() -- lands the move on the
    # resolved point instead of `origin`.)
    host, window = _host(1664, 824, align=mod_settings.PROGRESS_ALIGN_FREE)
    origin = (900, 600)                      # where the bar ACTUALLY sits
    window.position = origin
    max_x, max_y = host._extent(window)      # warm from _host's _place -- no far-sentinel teleport
    space_x, space_y = host._space(window)
    assert host._resolve(max_x, max_y, space_x, space_y) != origin, \
        "fixture: _resolve() must differ from the actual position for this test to bite"
    cursor = (950, 620)                      # a point inside the 256x92 bar sitting at `origin`
    _at(monkeypatch, cursor)                 # pixel-space: device px == logical at 1x
    host.drag("start")
    assert window.moves == [], "start must not move the bar"
    host.drag("move")                        # same cursor -> the bar must stay PUT at `origin`
    assert window.moves[-1] == origin, "a move at the grab point teleported off _resolve()"


def test_the_gesture_end_clears_state_and_skips_persist_when_alignment_left_free(monkeypatch):
    # Bug B: an "end" arriving after Alignment flipped away from Free mid-gesture (a radio flip or
    # Reset) must STILL clear _grab/_drag_pos -- the old code early-returned before the cleanup,
    # leaking drag state into the next gesture -- while NOT persisting a stale Free pin.
    host, _window = _host(1664, 824, align=mod_settings.PROGRESS_ALIGN_FREE)
    calls = []
    monkeypatch.setattr(mod_settings, "set_bar_position",
                        lambda x, y, persist: calls.append((x, y, persist)))
    _at(monkeypatch, _GRAB)
    host.drag("start")
    _at(monkeypatch, (0.4, -0.4))
    host.drag("move")
    assert host._grab is not None and host._drag_pos is not None
    # Alignment leaves Free underneath the live gesture.
    mod_settings._settings[mod_settings.PROGRESS_ALIGNMENT_KEY] = mod_settings.PROGRESS_ALIGN_FIXED
    host.drag("end")
    assert host._grab is None and host._drag_pos is None, "end must clear state after a non-Free flip"
    assert all(c[2] is not True for c in calls), "a non-Free end must not persist a stale pin"


def test_drag_past_the_top_left_edge_goes_negative_and_is_not_clamped(monkeypatch):
    # THERE IS NO SAFEZONE: a bar dragged off the left/top edge keeps going into negative logical
    # coordinates. The old [1, max] clamp stopped the corner at the screen edge, which made the last
    # part of the drag silently ignore the cursor.
    host, window = _host(1664, 824, align=mod_settings.PROGRESS_ALIGN_FREE)
    _at(monkeypatch, _GRAB)
    host.drag("start")
    _at(monkeypatch, (-1.0, 1.0))                      # cursor to the screen's top-left corner
    host.drag("move")
    # The grab offset (the bar's corner relative to the cursor that grabbed it) is carried, so the
    # corner lands that far PAST the origin.
    base = _centred(1664, 824)
    assert window.moves[-1] == (base[0] - _GRAB_PX[0], base[1] - _GRAB_PX[1])
    assert window.moves[-1][0] < 0 and window.moves[-1][1] < 0


def test_drag_past_the_bottom_right_edge_is_not_clamped_to_the_extent(monkeypatch):
    host, window = _host(1664, 824, align=mod_settings.PROGRESS_ALIGN_FREE)
    _at(monkeypatch, _GRAB)
    host.drag("start")
    _at(monkeypatch, (1.0, -1.0))                      # cursor to the screen's bottom-right corner
    host.drag("move")
    base = _centred(1664, 824)
    # Cursor travel from _GRAB_PX to (space_x, space_y), gain 1, and NOTHING clamps it back to the
    # movable extent (1664x824) -- the bar is allowed to hang off the edge.
    assert window.moves[-1] == (base[0] + _SPACE[0] - _GRAB_PX[0],
                                base[1] + _SPACE[1] - _GRAB_PX[1])
    assert window.moves[-1][0] > 1664 and window.moves[-1][1] > 824


def test_drag_handles_a_pixel_space_cursor_too(monkeypatch):
    # The units of GUI.mcursor().position are not settled in the decompiled client, so the mapping
    # is unit-agnostic -- and this is the OTHER convention, end to end through the host.
    host, window = _host(1664, 824, align=mod_settings.PROGRESS_ALIGN_FREE)
    _at(monkeypatch, _GRAB_PX)
    host.drag("start")
    _at(monkeypatch, (_GRAB_PX[0] + 480, _GRAB_PX[1]))  # a quarter-screen right, in device px
    host.drag("move")
    base = _centred(1664, 824)
    assert window.moves[-1] == (base[0] + 1920 // 4, base[1])


def test_the_drag_gain_is_exactly_one_through_the_host(monkeypatch):
    # THE ACCEPTANCE CRITERION, at the seam that supplies the missing term: N logical units of cursor
    # travel == N logical units of window travel. The window's OWN size (Wulf's read-only
    # Window.size, = self.proxy.windowSize) is what turns _extent's `space - surface` back into
    # `space`; without it the mapping scales by (space - surface) / space -- 1664/1920 = 0.867 here,
    # ~0.74 with the real Large surface -- and the bar visibly trails the cursor.
    host, window = _host(1664, 824, align=mod_settings.PROGRESS_ALIGN_FREE)
    _at(monkeypatch, _GRAB_PX)
    host.drag("start")
    host.drag("move")
    first = window.moves[-1]
    _at(monkeypatch, (_GRAB_PX[0] + 500, _GRAB_PX[1] - 200))   # +500 logical px on x, -200 on y
    host.drag("move")
    assert (window.moves[-1][0] - first[0], window.moves[-1][1] - first[1]) == (500, -200)


def test_an_unreadable_surface_size_fails_soft_and_declines_the_gesture(monkeypatch):
    # FAIL SOFT, not a raise: Wulf itself hands back (0.0, 0.0) for a window with no proxy (which
    # cannot be moved either), so _space degrades to the extent alone...
    host, window = _host(1664, 824, align=mod_settings.PROGRESS_ALIGN_FREE)
    window.size = None                                 # unpacking this raises inside _space
    assert host._space(window) == (1664, 824)
    # ...and with no surface size the OWNERSHIP RECT collapses to a point, so this host simply does
    # not claim the gesture: nothing moves, and nothing escapes into the engine's input path. A
    # proxy-less window could not have been moved anyway.
    _at(monkeypatch, _GRAB)
    host.drag("start")
    host.drag("move")
    assert [m for m in window.moves if m != (bar_window._FAR, bar_window._FAR)] == []


def test_the_reporting_events_own_cursor_position_is_preferred(monkeypatch):
    # gui.g_mouseEventHandlers hands the drag `event.cursorPosition` -- the position the engine
    # itself measured -- which makes GUI.mcursor() a FALLBACK. Proven by pointing the fallback
    # somewhere else entirely: the passed cursor is what places the bar.
    host, window = _host(1664, 824, align=mod_settings.PROGRESS_ALIGN_FREE)
    _at(monkeypatch, (-1.0, 1.0))                      # the fallback read says "top-left corner"
    host.drag("start", _GRAB)
    host.drag("move", _GRAB)
    assert window.moves[-1] == _centred(1664, 824)     # ...but the event's on-bar cursor won


def test_a_gesture_that_began_off_the_bar_is_not_claimed(monkeypatch):
    # THE OWNERSHIP GATE. battle_bridge hands every drag event to BOTH bars unconditionally and
    # battle_input samples Ctrl+LMB globally, so before this a Ctrl+drag ANYWHERE grabbed whichever
    # bar was open -- dragging another mod's UI dragged ours with it.
    host, window = _host(1664, 824, align=mod_settings.PROGRESS_ALIGN_FREE)
    _at(monkeypatch, (0.0, 0.0))                          # the screen centre: ABOVE the bar's box
    host.drag("start")
    host.drag("move")
    assert host._grab is None
    assert [m for m in window.moves if m != (bar_window._FAR, bar_window._FAR)] == []


def test_the_ownership_rect_is_read_against_the_real_position_not_a_cold_far_sentinel(monkeypatch):
    # LOAD-BEARING READ ORDER: window.position must be read BEFORE _extent() is called, because a
    # COLD extent cache measures by teleporting the window to the far sentinel (bar_window._FAR) --
    # reading .position AFTER that would test the ownership rect against the sentinel corner instead
    # of wherever the bar actually is. Reachable in practice: open_window() publishes `_active` BEFORE
    # window.load() resolves, so a drag can arrive before _onReady's first _place() has ever warmed
    # the memo -- i.e. exactly the cold-cache case, with the window still sitting at its untouched
    # native position.
    host, window = _cold_host(1664, 824, align=mod_settings.PROGRESS_ALIGN_FREE)        # UNPLACED: position stays (0, 0), cache cold
    _at(monkeypatch, (-1.0, 1.0))               # clip-space top-left -> logical (0, 0), on the window
    host.drag("start")
    assert host._grab is not None and host._declined is False, (
        "declined a gesture that started on the window's real (unplaced) position")


def test_a_declined_gesture_is_never_reconsidered_mid_flight(monkeypatch):
    # ...and the refusal LATCHES for the whole gesture: a foreign drag that happens to sweep the
    # cursor across our bar must not hijack it halfway (which would snap the bar to the cursor).
    host, window = _host(1664, 824, align=mod_settings.PROGRESS_ALIGN_FREE)
    _at(monkeypatch, (0.0, 0.0))
    host.drag("start")
    _at(monkeypatch, _GRAB)                               # ...the cursor now passes over the bar
    host.drag("move")
    host.drag("move")
    assert host._grab is None
    assert [m for m in window.moves if m != (bar_window._FAR, bar_window._FAR)] == []
    # The latch is per gesture, not permanent: the next drag that DOES start on the bar works.
    host.drag("end")
    _at(monkeypatch, _GRAB)
    host.drag("start")
    host.drag("move")
    assert window.moves[-1] == _centred(1664, 824)


def test_a_claimed_gesture_keeps_the_bar_once_the_cursor_leaves_the_box(monkeypatch):
    # The mirror image, and why only the START tests the rect: a bar is 256px wide and the cursor
    # leaves it within the first few px of any real drag. Re-testing per move would drop the bar.
    host, window = _host(1664, 824, align=mod_settings.PROGRESS_ALIGN_FREE)
    _at(monkeypatch, _GRAB)
    host.drag("start")
    _at(monkeypatch, (100, 100))                          # far outside the bar's own box
    host.drag("move")
    base = _centred(1664, 824)
    assert window.moves[-1] == (base[0] + 100 - _GRAB_PX[0], base[1] + 100 - _GRAB_PX[1])


def test_drag_is_a_noop_when_no_window_is_open(monkeypatch):
    host = bar_window.BarHost("test.item", lambda: object(), 0.865, 0,
                              PROGRESS_ANCHOR_Y_SHIFT, PROGRESS_ANCHOR_Y_SHIFT,
                              PROGRESS_MM_TRACK_X, PROGRESS_MM_TRACK_X_LARGE,
                              PROGRESS_MM_GAP_BOTTOM, "[test]")
    _at(monkeypatch, _GRAB)
    assert host._active is None
    host.drag("start")
    host.drag("move")
    host.drag("end")


def test_drag_leaves_the_bar_alone_when_the_cursor_cannot_be_read(monkeypatch):
    # FAIL SOFT: an unreadable cursor (or resolution) must leave the window exactly where it is,
    # never move it to a guessed position and never raise into the engine's input path.
    host, window = _host(1664, 824, align=mod_settings.PROGRESS_ALIGN_FREE)
    _at(monkeypatch, None)
    host.drag("start")
    host.drag("move")
    assert [m for m in window.moves if m != (bar_window._FAR, bar_window._FAR)] == []
    assert host._grab is None


def test_drag_never_raises_on_a_broken_engine_read(monkeypatch):
    host, _window = _host(1664, 824, align=mod_settings.PROGRESS_ALIGN_FREE)

    def _boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(bar_window, "_cursor_position", _boom)
    monkeypatch.setattr(bar_window, "_screen_resolution", _boom)
    host.drag("start")
    host.drag("move")
    host.drag("end")


def _far_measurements(window):
    """How many times the window was teleported to the far sentinel (= extent measurements)."""
    return [m for m in window.moves if m == (bar_window._FAR, bar_window._FAR)]


def test_a_drag_measures_the_movable_extent_only_once(monkeypatch):
    # THE JUMPING BUG: _extent teleports the window to (1<<20, 1<<20) to read the engine's clamp.
    # That is a one-shot calibration -- doing it per movement event costs a second native move()
    # per pointer event and made the bar visibly jump around the cursor. The extent is a function
    # of the surface size and the screen, neither of which changes mid-drag, so N events = 1 measure.
    host, window = _host(1664, 824, align=mod_settings.PROGRESS_ALIGN_FREE)
    _at(monkeypatch, _GRAB)
    host.drag("start")
    for i in range(8):
        _at(monkeypatch, (0.1 * i, 0.0))
        host.drag("move")
    host.drag("end")
    # ZERO here, because _place already warmed the memo when the window opened (see _host); an
    # un-memoized _extent would measure once per drag() call -- 9 times in this gesture.
    far = _far_measurements(window)
    assert len(far) == 0, "far-sentinel measured %d times in an 8-move drag" % len(far)


def test_a_size_change_re_measures_the_movable_extent(monkeypatch):
    # The one way the memoization can regress: a Default<->Large flip resizes the surface, so the
    # movable extent SHRINKS. _place is what onSizeChanged runs, and it must invalidate the memo.
    # Nothing CLAMPS to the extent any more (no safezone), so what a stale extent would corrupt now
    # is the Damage-Log anchor and the logical space the cursor maps onto (extent + surface).
    host, window = _host(1664, 824, align=mod_settings.PROGRESS_ALIGN_FREE)
    _at(monkeypatch, _GRAB)
    host.drag("start")
    host.drag("move")
    assert window.moves[-1] == _centred(1664, 824)

    window._max = (1600, 760)                             # Large surface -> smaller extent
    # That live move stored a real Free anchor point (every drag move persists one in-memory --
    # see set_bar_position's own docstring): reset the whole settings cache back to the shipped
    # Damage-Log-equivalent default (position 0/0), keeping Alignment=Free so the SECOND drag
    # below is still allowed to run at all -- BarHost.drag() now refuses to move the bar under
    # Fixed (see test_drag_is_a_noop_under_fixed_alignment).
    mod_settings._seed(dict(mod_settings.DEFAULTS,
                            **{mod_settings.PROGRESS_ALIGNMENT_KEY: mod_settings.PROGRESS_ALIGN_FREE}))
    host._place(window)
    _at(monkeypatch, _GRAB)
    host.drag("start")
    host.drag("move")
    assert window.moves[-1] == _centred(1600, 760)        # re-centred in the NEW extent, not the old
    assert len(_far_measurements(window)) == 1            # re-measured by _place, and only once


def test_the_engine_reads_fail_soft_to_none():
    # The two reads themselves: with no GUI module importable (pytest, game closed) each must hand
    # back None rather than raise, which is what makes the whole gesture a no-op off-client.
    assert bar_window._cursor_position() is None
    assert bar_window._screen_resolution() is None


def test_minimap_size_index_wrapper_fails_soft_when_the_adapter_read_raises(monkeypatch):
    # bar_window._minimap_size_index is a lazy-import wrapper so this module still imports with
    # the game closed; its own fallback (the LARGEST index -- see the wrapper's docstring for why
    # not the middle) must fire whether the import itself fails OR the adapter's read raises.
    from moe_calculator.adapter import battle_adapter
    from moe_calculator.domain.constants import MINIMAP_SIZES

    def _boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(battle_adapter, "read_minimap_size_index", _boom)
    assert bar_window._minimap_size_index() == len(MINIMAP_SIZES) - 1


def test_effective_variant_the_producer_itself_not_just_the_consumer_contract(monkeypatch):
    # bar_window._effective_variant()'s OWN body, driven for real (not monkeypatched wholesale, as
    # every other _effective_variant-consuming test in this file does) -- covers the two `return
    # None` paths (unreadable int_cd == 0, and a raising read) plus the normal mapped-variant path,
    # so the three are proven DISTINCT rather than all collapsing to the same branch.
    from moe_calculator.adapter import battle_adapter, variant_overrides

    monkeypatch.setattr(battle_adapter, "_player_vehicle_int_cd", lambda descr: 0)
    assert bar_window._effective_variant() is None, "int_cd 0 must read as unresolvable, not a variant"

    def _boom(descr):
        raise RuntimeError("boom")

    monkeypatch.setattr(battle_adapter, "_player_vehicle_int_cd", _boom)
    assert bar_window._effective_variant() is None, "a raising read must fail soft to None"

    monkeypatch.setattr(battle_adapter, "_player_vehicle_int_cd", lambda descr: 12345)
    monkeypatch.setattr(variant_overrides, "effective",
                        lambda int_cd, default: mod_settings.PROGRESS_VARIANT_EFFICIENCY)
    assert bar_window._effective_variant() == mod_settings.PROGRESS_VARIANT_EFFICIENCY, \
        "a readable int_cd must still resolve to the mapped variant, not None"


# --- BarHost._resolve's THREE alignment branches --------------------------------------------

def _resolved(host, window):
    max_x, max_y = host._extent(window)
    space_x, space_y = host._space(window)
    return host._resolve(max_x, max_y, space_x, space_y)


def test_fixed_alignment_resolves_to_damage_log_anchor_when_horizontal():
    # The shipped default (Fixed + Horizontal, v23): must still match _centred
    # (== anchor_centred_reduced) byte-for-byte -- Fixed resolves the SAME anchor Damage Log
    # always did, just picked internally by Orientation now instead of being its own stored value.
    host, window = _host(1664, 824)
    assert _resolved(host, window) == _centred(1664, 824)


def test_fixed_alignment_resolves_to_minimap_anchor_when_vertical(monkeypatch):
    # The other half of the v23 behavioural contract: Fixed + Vertical must resolve to the SAME
    # Minimap anchor the old, directly-selectable "Minimap" option always did -- composed through
    # the real _resolve (never a reimplementation of anchor_minimap).
    from moe_calculator.domain.constants import (
        MINIMAP_SIZES, MM_GAP, MM_TICK_OVERHANG, MM_TRACK_Y)
    from moe_calculator.domain.positioning import anchor_minimap

    monkeypatch.setattr(bar_window, "_minimap_size_index", lambda: 0)
    mod_settings._seed({mod_settings.PROGRESS_ORIENTATION_KEY: mod_settings.PROGRESS_ORIENT_VERTICAL})
    host, window = _host(1664, 824)
    space_x, space_y = host._space(window)
    expected = anchor_minimap(space_x, space_y, PROGRESS_MM_TRACK_X, MM_TRACK_Y,
                              MINIMAP_SIZES[0], MM_GAP, PROGRESS_MM_GAP_BOTTOM, MM_TICK_OVERHANG)
    assert _resolved(host, window) == expected
    assert _resolved(host, window) != _centred(1664, 824), \
        "vertical must resolve to Minimap, not Damage Log"


def test_resolve_free_alignment_converts_the_stored_pair_as_an_anchor_point():
    # v22 (Trap 3 Fix B): a NON-ZERO pair under Free is the ANCHOR POINT (bottom-centre,
    # horizontal), converted into a top-left using THIS placement's own surface size --
    # domain.positioning.free_top_left, never a literal top-left any more. (The pair (0, 0) is
    # the one exception; see the AUTO tests below.)
    from moe_calculator.domain.positioning import free_top_left

    mod_settings._seed({mod_settings.PROGRESS_ALIGNMENT_KEY: mod_settings.PROGRESS_ALIGN_FREE,
                        mod_settings.BAR_POS_X_KEY: 111, mod_settings.BAR_POS_Y_KEY: 222})
    host, window = _host(1664, 824)
    assert _resolved(host, window) == free_top_left((111, 222), _SURFACE, False)
    # Sanity: this is NOT the pre-v22 literal top-left any more.
    assert _resolved(host, window) != (111, 222)


def test_resolve_free_alignment_with_the_legacy_frame_still_uses_the_pair_verbatim():
    # A pre-v22 store that has not yet been through BarHost._materialise still honours its pair
    # as the literal top-left it always was -- see the SETTINGS_VERSION 21->22 comment.
    mod_settings._seed({mod_settings.PROGRESS_ALIGNMENT_KEY: mod_settings.PROGRESS_ALIGN_FREE,
                        mod_settings.BAR_POS_X_KEY: 111, mod_settings.BAR_POS_Y_KEY: 222,
                        mod_settings.PROGRESS_POS_FRAME_KEY: mod_settings.POS_FRAME_LEGACY})
    host, window = _host(1664, 824)
    assert _resolved(host, window) == (111, 222)


# --- FREE + (0, 0) IS AUTO: the orientation's own default anchor --------------------------------
# The branch survives the "Free is sticky" redesign (that rule is SUPERSEDED -- an Orientation or
# Alignment change now re-anchors Alignment away from Free unconditionally, see
# mod_settings._derive_layout), but it is still load-bearing for two OTHER reasons: picking
# Alignment = Free leaves the pair at (0, 0) until the bar's next battle mount computes the real
# on-screen point (no surface exists in the settings panel to compute it from), so (0, 0) is Free's
# "not yet materialised" marker; and a user who types 0 / 0 into the steppers gets AUTO rather than
# the screen origin, a deliberately accepted lost capability. Either way, (0, 0) under Free must
# resolve through the SAME default anchor the orientation/alignment auto-set would have picked:
# Horizontal -> Damage Log, Vertical -> Minimap. Composed through the real _resolve here (never a
# reimplementation of the anchor math), and each case additionally asserted NOT to be the literal
# screen origin, which is what the old semantics returned.

def _free_auto(monkeypatch, orientation):
    monkeypatch.setattr(bar_window, "_minimap_size_index", lambda: 0)
    mod_settings._seed({mod_settings.PROGRESS_ALIGNMENT_KEY: mod_settings.PROGRESS_ALIGN_FREE,
                        mod_settings.PROGRESS_ORIENTATION_KEY: orientation,
                        mod_settings.BAR_POS_X_KEY: 0, mod_settings.BAR_POS_Y_KEY: 0})
    host, window = _host(1664, 824)
    return _resolved(host, window)


def test_resolve_free_at_zero_zero_falls_back_to_the_damage_log_anchor_when_horizontal(monkeypatch):
    resolved = _free_auto(monkeypatch, mod_settings.PROGRESS_ORIENT_HORIZONTAL)
    assert resolved == _centred(1664, 824)
    assert resolved != (0, 0), "Free + (0, 0) must no longer mean the literal screen corner"


def test_resolve_free_at_zero_zero_falls_back_to_the_minimap_anchor_when_vertical(monkeypatch):
    from moe_calculator.domain.constants import (
        MINIMAP_SIZES, MM_GAP, MM_TICK_OVERHANG, MM_TRACK_Y)
    from moe_calculator.domain.positioning import anchor_minimap

    host, window = _host(1664, 824)
    space_x, space_y = host._space(window)
    resolved = _free_auto(monkeypatch, mod_settings.PROGRESS_ORIENT_VERTICAL)
    # The VERTICAL minimap branch in full -- track edges and the tick overhang, not the surface's
    # own edges: falling back through the alignment value means it goes through the identical
    # branch a stored Minimap alignment does, orientation gates and all.
    assert resolved == anchor_minimap(space_x, space_y, PROGRESS_MM_TRACK_X, MM_TRACK_Y,
                                      MINIMAP_SIZES[0], MM_GAP, PROGRESS_MM_GAP_BOTTOM,
                                      MM_TICK_OVERHANG)
    assert resolved != (0, 0), "Free + (0, 0) must no longer mean the literal screen corner"
    assert resolved != _centred(1664, 824), "vertical must fall back to Minimap, not Damage Log"


def test_resolve_free_auto_matches_the_two_stored_alignments_it_stands_in_for(monkeypatch):
    # The fallback is stated as an EQUIVALENCE, so a future divergence between the two paths (say,
    # someone re-anchoring Free's auto to a hardcoded anchor) is caught even if both still look
    # plausible on their own.
    horiz_free = _free_auto(monkeypatch, mod_settings.PROGRESS_ORIENT_HORIZONTAL)
    vert_free = _free_auto(monkeypatch, mod_settings.PROGRESS_ORIENT_VERTICAL)

    mod_settings._seed(dict(mod_settings.DEFAULTS))       # Horizontal + Damage Log, the shipped pair
    assert horiz_free == _resolved(*_host(1664, 824))
    assert vert_free == _minimap_x(monkeypatch, mod_settings.PROGRESS_ORIENT_VERTICAL,
                                   mod_settings.PROGRESS_SIZE_DEFAULT)


def test_resolve_free_with_a_nonzero_pair_converts_as_an_anchor_point_on_both_orientations(
        monkeypatch):
    # The other half of the contract, and the regression guard on the drag: only the EXACT pair
    # (0, 0) is auto. One px off it on either axis skips the AUTO branch entirely and goes through
    # free_top_left (v22, Trap 3 Fix B) instead -- no anchor, no partial composition, but also no
    # longer a literal top-left.
    from moe_calculator.domain.positioning import free_top_left

    for orientation in (mod_settings.PROGRESS_ORIENT_HORIZONTAL,
                        mod_settings.PROGRESS_ORIENT_VERTICAL):
        for pair in ((1, 0), (0, 1), (-40, 900)):
            mod_settings._seed({
                mod_settings.PROGRESS_ALIGNMENT_KEY: mod_settings.PROGRESS_ALIGN_FREE,
                mod_settings.PROGRESS_ORIENTATION_KEY: orientation,
                mod_settings.BAR_POS_X_KEY: pair[0], mod_settings.BAR_POS_Y_KEY: pair[1]})
            host, window = _host(1664, 824)
            vertical = orientation == mod_settings.PROGRESS_ORIENT_VERTICAL
            expected = free_top_left(pair, _SURFACE, vertical)
            assert _resolved(host, window) == expected, \
                "Free %r at orientation %r did not convert as an anchor point" % (pair, orientation)


def test_resolve_free_with_a_nonzero_pair_and_the_legacy_frame_is_absolute_on_both_orientations(
        monkeypatch):
    # The PRE-v22 behaviour, still reachable via the frame marker: a "legacy" pair is honoured as
    # the literal top-left it always was, on either orientation, until BarHost._materialise
    # converts it.
    for orientation in (mod_settings.PROGRESS_ORIENT_HORIZONTAL,
                        mod_settings.PROGRESS_ORIENT_VERTICAL):
        for pair in ((1, 0), (0, 1), (-40, 900)):
            mod_settings._seed({
                mod_settings.PROGRESS_ALIGNMENT_KEY: mod_settings.PROGRESS_ALIGN_FREE,
                mod_settings.PROGRESS_ORIENTATION_KEY: orientation,
                mod_settings.PROGRESS_POS_FRAME_KEY: mod_settings.POS_FRAME_LEGACY,
                mod_settings.BAR_POS_X_KEY: pair[0], mod_settings.BAR_POS_Y_KEY: pair[1]})
            host, window = _host(1664, 824)
            assert _resolved(host, window) == pair, \
                "legacy Free %r at orientation %r is not absolute" % (pair, orientation)


# --- BarHost._materialise -- Trap 2 / Trap 3 Fix B / DECISION 1&2 ----------------------------
# Deliberately built on `_cold_host`, never `_host`: `_host` warms `_extent_cache` AND runs one
# `_place()` during setup (memory `bar-window-warm-fixture-hides-cold-path-drag-bug` -- it has
# hidden two real bugs behind a degenerate fixture already). Materialisation's whole point is
# ORDER: nothing may write back until `_sized` flips true, so the fixture must not pre-empt that
# by placing before the test gets to control it.


def test_materialise_never_fires_before_onsizechanged_even_at_a_real_surface_size(monkeypatch):
    # `_sized` starts False -- exactly the state at _onReady's first _place, before any
    # onSizeChanged has ever fired -- and this fixture's surface (256x92) is a REAL,
    # non-degenerate size, not the engine's 256x256 fallback, so a bug that materialised off "is
    # the surface plausible" rather than "did onSizeChanged actually fire" would slip through a
    # weaker test.
    mod_settings._seed({
        mod_settings.PROGRESS_ALIGNMENT_KEY: mod_settings.PROGRESS_ALIGN_FREE,
        mod_settings.BAR_POS_X_KEY: 0, mod_settings.BAR_POS_Y_KEY: 0,
        mod_settings.PROGRESS_VARIANT_KEY: mod_settings.PROGRESS_VARIANT_MOVING_AVERAGE})
    host, window = _cold_host(1664, 824)
    host._variant = mod_settings.PROGRESS_VARIANT_MOVING_AVERAGE
    calls = []
    monkeypatch.setattr(mod_settings, "set_bar_position",
                        lambda x, y, persist=True: calls.append((x, y, persist)))
    host._place(window)
    assert calls == []


def test_materialise_never_fires_against_the_engines_256x256_fallback_surface(monkeypatch):
    # The literal fallback size, for good measure: `_sized` is the real gate, but this pins the
    # scenario the gate exists FOR, by name.
    mod_settings._seed({
        mod_settings.PROGRESS_ALIGNMENT_KEY: mod_settings.PROGRESS_ALIGN_FREE,
        mod_settings.BAR_POS_X_KEY: 0, mod_settings.BAR_POS_Y_KEY: 0,
        mod_settings.PROGRESS_VARIANT_KEY: mod_settings.PROGRESS_VARIANT_MOVING_AVERAGE})
    host, window = _cold_host(1664, 824)
    window.size = (256, 256)
    host._variant = mod_settings.PROGRESS_VARIANT_MOVING_AVERAGE
    calls = []
    monkeypatch.setattr(mod_settings, "set_bar_position",
                        lambda x, y, persist=True: calls.append((x, y, persist)))
    host._place(window)
    assert calls == []


def test_materialise_writes_exactly_once_after_onsizechanged_for_its_own_variant(monkeypatch):
    from moe_calculator.domain.positioning import free_anchor_point

    mod_settings._seed({
        mod_settings.PROGRESS_ALIGNMENT_KEY: mod_settings.PROGRESS_ALIGN_FREE,
        mod_settings.BAR_POS_X_KEY: 0, mod_settings.BAR_POS_Y_KEY: 0,
        mod_settings.PROGRESS_VARIANT_KEY: mod_settings.PROGRESS_VARIANT_MOVING_AVERAGE})
    host, window = _cold_host(1664, 824)
    host._variant = mod_settings.PROGRESS_VARIANT_MOVING_AVERAGE
    calls = []
    orig = mod_settings.set_bar_position

    def _spy(x, y, persist=True):
        calls.append((x, y, persist))
        orig(x, y, persist=persist)
    monkeypatch.setattr(mod_settings, "set_bar_position", _spy)

    # Fallback-sized first placement (see the tests above) -- must not fire.
    host._place(window)
    assert calls == []

    # onSizeChanged fires -> _sized flips True (mirroring _BarWindow._on_size_changed) -> the
    # NEXT _place materialises exactly once, PERSISTED (not the live-drag persist=False path).
    host._sized = True
    host._place(window)
    assert len(calls) == 1
    assert calls[0][2] is True
    expected = free_anchor_point(window.moves[-1], _SURFACE, False)
    assert (calls[0][0], calls[0][1]) == expected
    # ...and the pair really did land in memory (the spy delegates to the real function).
    assert (mod_settings.bar_pos_x(), mod_settings.bar_pos_y()) == expected

    # A THIRD _place (e.g. another resize, or Default<->Large) must NOT re-materialise: the pair
    # is no longer (0, 0) and the frame is already "anchor".
    host._place(window)
    assert len(calls) == 1


def test_materialise_only_fires_for_its_own_variant(monkeypatch):
    # Both hosts share ONE stored pair; a live variant flip mid-battle can briefly have both open
    # (see BarHost's own docstring), so a materialisation triggered by ONE bar's mount must never
    # fire for the OTHER bar's host. The gate keys on _effective_variant() (a READABLE frame's
    # resolved variant) -- model that directly rather than via an unreadable descr, which now means
    # "can't tell -> proceed" (see test_materialise_proceeds_when_the_descr_is_unreadable).
    mod_settings._seed({
        mod_settings.PROGRESS_ALIGNMENT_KEY: mod_settings.PROGRESS_ALIGN_FREE,
        mod_settings.BAR_POS_X_KEY: 0, mod_settings.BAR_POS_Y_KEY: 0})
    monkeypatch.setattr(bar_window, "_effective_variant",
                        lambda: mod_settings.PROGRESS_VARIANT_EFFICIENCY)
    host, window = _cold_host(1664, 824)
    host._variant = mod_settings.PROGRESS_VARIANT_MOVING_AVERAGE   # the OTHER bar is selected
    host._sized = True
    calls = []
    monkeypatch.setattr(mod_settings, "set_bar_position",
                        lambda x, y, persist=True: calls.append((x, y, persist)))
    host._place(window)
    assert calls == []


def test_materialise_proceeds_when_the_descr_is_unreadable(monkeypatch):
    # Bug C: _effective_variant() returns None when the played vehicle's descr can't be read this
    # frame. That must NOT flip the own-variant gate against the correctly-open host -- otherwise a
    # per-vehicle-override host would skip a fresh Free AUTO write for the frame, leaving the
    # steppers reading 0/0 longer. None -> proceed. (Revert -- gate treating None as a mismatch --
    # makes this fail: calls stays empty.)
    from moe_calculator.domain.positioning import free_anchor_point

    mod_settings._seed({
        mod_settings.PROGRESS_ALIGNMENT_KEY: mod_settings.PROGRESS_ALIGN_FREE,
        mod_settings.BAR_POS_X_KEY: 0, mod_settings.BAR_POS_Y_KEY: 0})
    monkeypatch.setattr(bar_window, "_effective_variant", lambda: None)
    host, window = _cold_host(1664, 824)
    host._variant = mod_settings.PROGRESS_VARIANT_MOVING_AVERAGE
    host._sized = True
    calls = []
    monkeypatch.setattr(mod_settings, "set_bar_position",
                        lambda x, y, persist=True: calls.append((x, y, persist)))
    host._place(window)
    assert len(calls) == 1
    assert (calls[0][0], calls[0][1]) == free_anchor_point(window.moves[-1], _SURFACE, False)


def test_materialise_converts_a_legacy_pre_v22_pin_exactly_once(monkeypatch):
    # DECISION 2's deferred conversion: a pre-v22 legacy pair is honoured verbatim as a top-left
    # (see the _resolve test above) until this bar's next real mount, which converts it into the
    # anchor-point frame and flips the marker -- the SAME action DECISION 1's fresh pin uses.
    from moe_calculator.domain.positioning import free_anchor_point

    mod_settings._seed({
        mod_settings.PROGRESS_ALIGNMENT_KEY: mod_settings.PROGRESS_ALIGN_FREE,
        mod_settings.BAR_POS_X_KEY: 111, mod_settings.BAR_POS_Y_KEY: 222,
        mod_settings.PROGRESS_POS_FRAME_KEY: mod_settings.POS_FRAME_LEGACY,
        mod_settings.PROGRESS_VARIANT_KEY: mod_settings.PROGRESS_VARIANT_MOVING_AVERAGE})
    host, window = _cold_host(1664, 824)
    host._variant = mod_settings.PROGRESS_VARIANT_MOVING_AVERAGE
    host._sized = True
    calls = []
    orig = mod_settings.set_bar_position

    def _spy(x, y, persist=True):
        calls.append((x, y, persist))
        orig(x, y, persist=persist)
    monkeypatch.setattr(mod_settings, "set_bar_position", _spy)

    host._place(window)
    assert len(calls) == 1
    expected = free_anchor_point((111, 222), _SURFACE, False)
    assert (calls[0][0], calls[0][1]) == expected
    assert mod_settings.progress_bar_pos_frame() == mod_settings.POS_FRAME_ANCHOR

    host._place(window)
    assert len(calls) == 1   # not converted a second time


def test_a_place_failure_never_strands_the_window_at_the_far_sentinel_corner(monkeypatch):
    # _extent() teleports the window to the far sentinel (bar_window._FAR) BEFORE _space/_resolve
    # ever run -- and that sentinel corner IS the minimap's own corner (both anchor bottom-right).
    # Any exception between that measuring move and the real window.move() in _place would
    # otherwise strand the bar sitting on top of the minimap: indistinguishable from a genuine
    # placement bug, and silent (LOG_CURRENT_EXCEPTION only logs). _place must move it clear --
    # part (a) below is the same scenario, pinning WHERE it moves to.
    host, window = _host(1664, 824)

    def _boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(host, "_resolve", _boom)
    host._place(window)
    assert window.moves[-1] != (bar_window._FAR, bar_window._FAR), (
        "a _place failure left the window parked on the far-sentinel/minimap corner")
    assert window.moves[-1] != (0, 0), (
        "a _place failure must never fall back to the screen origin -- the bar must appear only "
        "near the minimap")


def test_a_place_failure_after_a_prior_success_restores_the_last_good_position(monkeypatch):
    # (a) THE ACCEPTANCE CASE: _host's own setup already ran one successful _place, so `_last_good`
    # is the position that placement landed at. A raise on the NEXT _place must restore exactly
    # that -- no recompute (so it cannot re-raise the same fault), never the far sentinel, never
    # (0, 0).
    host, window = _host(1664, 824)
    last_good = host._last_good
    assert last_good is not None and last_good != (bar_window._FAR, bar_window._FAR)

    monkeypatch.setattr(host, "_resolve", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    host._place(window)
    assert window.moves[-1] == last_good, (
        "a _place failure with a last-good position on record must restore exactly there")
    assert window.moves[-1] != (bar_window._FAR, bar_window._FAR)
    assert window.moves[-1] != (0, 0)


def test_a_place_failure_with_no_last_good_position_leaves_has_placed_false(monkeypatch):
    # (b) NO prior success exists (the very first placement this host has ever attempted, e.g. the
    # engine's 256x256 size-timeout fallback surface at _onReady) -- there is nothing to restore
    # to, so the except branch now does NOTHING further: has_placed() (== `_last_good is not
    # None`) is what keeps the bar off-screen, at the push site (battle_bridge), not here. Built
    # on _cold_host (never placed), so `_last_good` really is still None going in.
    host, window = _cold_host(1664, 824)
    assert host.has_placed() is False

    def _boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(host, "_resolve", _boom)
    host._place(window)
    assert host.has_placed() is False
    # And it must not have moved the window anywhere claiming to be a real placement -- only the
    # far-sentinel measuring move from _extent() is expected here.
    assert [m for m in window.moves if m != (bar_window._FAR, bar_window._FAR)] == []


def test_a_subsequent_success_flips_has_placed_true_and_records_a_new_last_good_position(
        monkeypatch):
    # (c) The very first placement can still fail; the NEXT successful _place must flip
    # has_placed() True and record its own last-good position, with no extra retry machinery
    # needed on top of the ordinary onSizeChanged re-arm (see _place's docstring) -- this test
    # drives that "next success" call directly, exactly as onSizeChanged would.
    host, window = _cold_host(1664, 824)

    def _boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(host, "_resolve", _boom)
    host._place(window)
    assert host.has_placed() is False

    monkeypatch.undo()   # restore the real _resolve for the "next success"
    host._place(window)
    assert host.has_placed() is True
    assert host._last_good == window.moves[-1]
    assert host._last_good not in ((bar_window._FAR, bar_window._FAR), (0, 0))


def test_resolve_stored_offset_composes_on_top_of_every_alignment():
    # anchor_offset applies uniformly regardless of which base anchor was selected -- proven here
    # against the Damage-Log branch (the other two are exercised at (0, 0) offset above).
    mod_settings._seed({mod_settings.BAR_POS_X_KEY: 10, mod_settings.BAR_POS_Y_KEY: -5})
    host, window = _host(1664, 824)
    base = _centred(1664, 824)
    assert _resolved(host, window) == (base[0] + 10, base[1] - 5)


# --- the minimap alignment's OVERHANG under Large ----------------------------------------------
# anchor_minimap's overhang term is MM_TICK_OVERHANG(_LARGE) for a vertical bar (a CROSS-AXIS
# length). Fixed always resolves to Minimap when vertical (v23), so there is no horizontal case
# left to gate here any more -- see test_fixed_alignment_resolves_to_minimap_anchor_when_vertical
# for the Default-size, overhang=MM_TICK_OVERHANG case this test's sibling covers.

def _minimap_x(monkeypatch, orientation, size):
    monkeypatch.setattr(bar_window, "_minimap_size_index", lambda: 0)
    mod_settings._seed({mod_settings.PROGRESS_ORIENTATION_KEY: orientation,
                        mod_settings.PROGRESS_SIZE_KEY: size})
    host, window = _host(1664, 824)
    return _resolved(host, window)


def test_minimap_overhang_scales_to_the_large_constant_when_vertical_and_large(monkeypatch):
    from moe_calculator.domain.constants import (
        MINIMAP_SIZES, MM_GAP, MM_TICK_OVERHANG_LARGE, PROGRESS_MM_TRACK_X_LARGE,
        MM_TRACK_Y_LARGE, PROGRESS_MM_GAP_BOTTOM)
    from moe_calculator.domain.positioning import anchor_minimap

    host, window = _host(1664, 824)
    max_x, max_y = host._extent(window)
    space_x, space_y = host._space(window)

    large = _minimap_x(monkeypatch, mod_settings.PROGRESS_ORIENT_VERTICAL,
                       mod_settings.PROGRESS_SIZE_LARGE)
    expected_large = anchor_minimap(space_x, space_y, PROGRESS_MM_TRACK_X_LARGE, MM_TRACK_Y_LARGE,
                                    MINIMAP_SIZES[0], MM_GAP, PROGRESS_MM_GAP_BOTTOM,
                                    MM_TICK_OVERHANG_LARGE)
    assert large == expected_large


# --- THE DERIVED PLACEMENT: the shipped Damage Efficiency position, END TO END ------------------
# The fresh-install configuration (steppers at 0), pinned END TO END through the shipped efficiency
# host (not a from-scratch anchor_minimap call -- that would only restate the formula and could not
# see EFFICIENCY_ANCHOR_X_OFFSET, the MINIMAP_SIZES lookup or the orientation/size gates).
#
#   screen 3840x2160 device px @ interfaceScale 2  ->  logical GUI space 1920x1080
#   surface 200x318 logical px (MoEEfficiency.js V_VIEW_W_REM x V_VIEW_H_REM, widened from 116 in
#     two passes -- the per-mark caption pass's V_PAD_X_REM fix, then corrected again once the
#     .bt row and the top/bottom-block nudges were folded in)
#   -> movable extent 1720x762
#   minimap size index 4, Default size, VERTICAL, Minimap alignment
#
# X == 1242 is the PURE composition derivation (1920 - 510 - 8 - 3 - 157). This bar's own hand-drag
# (see constants.py's EFFICIENCY_MM_TRACK_X comment) predates every one of those widenings and
# checked a MUCH narrower surface (edge_x 53, X == 1346) -- it landed 2px off that OLDER derivation
# (1344), read at the time as hand-drag scatter against a second, independent Moving Average drag
# that missed the OTHER way. THAT READING NO LONGER STANDS FOR THE MOVING AVERAGE BAR (a third,
# independent drag in a different geometry repeated its miss exactly -- see constants.py's
# PROGRESS_MM_TRACK_X), and the Damage Efficiency bar's own single drag was already accepted as
# correct AS DERIVED rather than as measured, so this still ships the pure (now-widened)
# derivation, not either drag -- a fresh in-game check of the new position is owed more than ever
# (see constants.py). Y == 762 is NOT their stored 820, and that is the point of the second
# half of this test: 820 is 58 px past the movable extent, so the engine clamps it (compiled C++, no
# opt-out -- memory `engine-clamps-every-wulf-window-to-screen-and-the-mod-depends-on-it`) and the
# bar they were looking at was ALREADY at 762, i.e. already at EFFICIENCY_MM_GAP_BOTTOM's hard floor.
# Folding the 58 into that constant would change nothing on screen; lowering the bar needs a smaller
# surface (MoEEfficiency.js V_CLIP_B_REM), not a constant.

_EFF_SPACE = (1920, 1080)
_EFF_SURFACE = (171, 318)   # MUST track test_efficiency_surface_mirror._v_surface_wh
_EFF_MAX = (_EFF_SPACE[0] - _EFF_SURFACE[0], _EFF_SPACE[1] - _EFF_SURFACE[1])


def _efficiency_host(max_xy=_EFF_MAX, surface=_EFF_SURFACE):
    """The REAL Damage Efficiency host's constants against a real-sized fake surface."""
    from moe_calculator.domain.constants import (
        EFFICIENCY_ANCHOR_X_OFFSET, EFFICIENCY_ANCHOR_Y_FRAC,
        EFFICIENCY_ANCHOR_Y_SHIFT, EFFICIENCY_ANCHOR_Y_SHIFT_LARGE, EFFICIENCY_MM_GAP_BOTTOM,
        EFFICIENCY_MM_TRACK_X, EFFICIENCY_MM_TRACK_X_LARGE)

    host = bar_window.BarHost(
        "MoEEfficiencyView", lambda: object(), EFFICIENCY_ANCHOR_Y_FRAC,
        EFFICIENCY_ANCHOR_X_OFFSET, EFFICIENCY_ANCHOR_Y_SHIFT, EFFICIENCY_ANCHOR_Y_SHIFT_LARGE,
        EFFICIENCY_MM_TRACK_X, EFFICIENCY_MM_TRACK_X_LARGE, EFFICIENCY_MM_GAP_BOTTOM, "[test-eff]")
    window = _FakeWindow(max_xy[0], max_xy[1], size=surface)
    host._active = (window, object())
    return host, window


def test_the_vertical_efficiency_bar_lands_on_the_derived_position(monkeypatch):
    monkeypatch.setattr(bar_window, "_minimap_size_index", lambda: 4)
    mod_settings._seed({mod_settings.PROGRESS_ORIENTATION_KEY: mod_settings.PROGRESS_ORIENT_VERTICAL,
                        mod_settings.PROGRESS_SIZE_KEY: mod_settings.PROGRESS_SIZE_DEFAULT,
                        mod_settings.BAR_POS_X_KEY: 0, mod_settings.BAR_POS_Y_KEY: 0})
    host, window = _efficiency_host()
    assert _resolved(host, window) == (1242, 762)


def test_the_hand_placed_y_was_below_the_engines_clamp_floor_so_none_of_it_was_folded_in():
    # WHY the pin above says 762 and not the 820 that is actually stored in the maintainer's MSA
    # payload. Two independent statements of the same floor, so a future "just bump the gap by 58"
    # cannot go green: the stored y exceeds the movable extent, AND the shipped gap already IS the
    # surface's whole below-the-track slack. Neither may be papered over in Python.
    from moe_calculator.domain.constants import EFFICIENCY_MM_GAP_BOTTOM, MM_TRACK_Y

    assert 820 > _EFF_MAX[1] == 762, "the hand-dragged y is past the engine's clamp, not reachable"
    assert _EFF_SURFACE[1] - MM_TRACK_Y == EFFICIENCY_MM_GAP_BOTTOM == 28


# --- THE TWO VERTICAL BARS' TRACKS DELIBERATELY DIFFER BY 2px NOW --------------------------------
# A THIRD, independent Ctrl+drag of the Moving Average bar (see constants.py's PROGRESS_MM_TRACK_X)
# showed the earlier "shared track-left" reading was wrong for that bar specifically: it must sit
# 2 logical px to the RIGHT of where the pure derivation (and the Damage Efficiency bar, which
# keeps that pure derivation) puts it. Do NOT "fix" this back to equality -- it is a recorded
# in-game measurement, confirmed by two independent drags in two different surface geometries.

_PROG_V_SPACE = (1920, 1080)
_PROG_V_SURFACE = (182, 320)   # MUST track test_progress_surface_mirror._v_surface_wh
_PROG_V_MAX = (_PROG_V_SPACE[0] - _PROG_V_SURFACE[0], _PROG_V_SPACE[1] - _PROG_V_SURFACE[1])


def _progress_vertical_host(max_xy=_PROG_V_MAX, surface=_PROG_V_SURFACE):
    """The REAL Moving Average host's constants against its real vertical surface, sized to share
    _efficiency_host's SAME logical screen (1920x1080)."""
    from moe_calculator.domain.constants import (
        PROGRESS_ANCHOR_X_OFFSET, PROGRESS_ANCHOR_Y_FRAC,
        PROGRESS_ANCHOR_Y_SHIFT, PROGRESS_ANCHOR_Y_SHIFT_LARGE)

    host = bar_window.BarHost(
        "MoEProgressView", lambda: object(), PROGRESS_ANCHOR_Y_FRAC,
        PROGRESS_ANCHOR_X_OFFSET, PROGRESS_ANCHOR_Y_SHIFT, PROGRESS_ANCHOR_Y_SHIFT_LARGE,
        PROGRESS_MM_TRACK_X, PROGRESS_MM_TRACK_X_LARGE, PROGRESS_MM_GAP_BOTTOM, "[test-prog]")
    window = _FakeWindow(max_xy[0], max_xy[1], size=surface)
    host._active = (window, object())
    return host, window


def test_the_moving_average_bars_track_sits_2px_right_of_damage_efficiencys(monkeypatch):
    # Composed through each bar's REAL _resolve (not a reimplementation of anchor_minimap), then
    # cross-checked against the PURE derivation numbers -- 157 for the efficiency edge (V_PAD_X_REM 114 +
    # 40 + 3) and 170 for the progress edge (V_PAD_X_REM 133 + 34 + 3; both grew when the % caption's
    # font went to the numeral's 16rem) -- rather than
    # against whatever EFFICIENCY_MM_TRACK_X / PROGRESS_MM_TRACK_X
    # happen to currently hold: adding a bar's OWN (possibly corrected) mm_track_x back onto its own
    # resolved x cancels algebraically for ANY value fed to anchor_minimap, so that comparison could
    # never see a correction land. Pinning against the literal PURE derived numbers instead means
    # PROGRESS_MM_TRACK_X's shipped -2 correction shows up as exactly a +2 here -- intentional, a
    # recorded in-game measurement (see constants.py), NOT a bug to loosen into a tolerance or
    # revert back to equality.
    monkeypatch.setattr(bar_window, "_minimap_size_index", lambda: 4)
    mod_settings._seed({mod_settings.PROGRESS_ORIENTATION_KEY: mod_settings.PROGRESS_ORIENT_VERTICAL,
                        mod_settings.PROGRESS_SIZE_KEY: mod_settings.PROGRESS_SIZE_DEFAULT,
                        mod_settings.BAR_POS_X_KEY: 0, mod_settings.BAR_POS_Y_KEY: 0})
    eff_host, eff_window = _efficiency_host()
    prog_host, prog_window = _progress_vertical_host()
    eff_x, _ = _resolved(eff_host, eff_window)
    prog_x, _ = _resolved(prog_host, prog_window)
    assert prog_x + 170 == eff_x + 157 + 2, (
        "the Moving Average bar's track must sit 2px RIGHT of Damage Efficiency's -- a recorded "
        "in-game measurement (two independent Ctrl+drags, two geometries), not a bug to fix back "
        "to equality")


# --- SELF-HEAL A NATIVELY-DESTROYED HANDLE (BarHost._is_dead / open_window re-mount) ------------
# The engine can destroy one of our WindowFlags.TOOLTIP bar windows out from under us (clicking an
# alternative-equipment slot on the battle countdown): windowStatus/viewStatus go
# DESTROYING/DESTROYED and View._cFini nulls the viewModel, with NO Python destroy() call. Before
# this, open_window's `_active is not None` guard trusted the dead handle forever, active_view()
# kept handing it back, and every push no-op'd on its None viewModel -- the bar silently stopped
# updating for the rest of the battle. open_window() must now DROP a dead handle and re-mount, while
# leaving a LIVE handle untouched (no needless re-create).


class _StatusHandle(object):
    """A fake window/view exposing exactly the liveness fields BarHost._is_dead reads. Doubles as
    both roles of the (window, view) tuple -- _is_dead reads window.windowStatus and
    view.viewStatus / view.viewModel, so one object with all three serves both slots."""

    def __init__(self, window_status=3, view_status=3, view_model="vm"):
        self.windowStatus = window_status   # LOADED == 3 by default
        self.viewStatus = view_status
        self.viewModel = view_model


def _bare_host():
    return bar_window.BarHost("test.item", lambda: object(), 0.865, 0,
                              PROGRESS_ANCHOR_Y_SHIFT, PROGRESS_ANCHOR_Y_SHIFT,
                              PROGRESS_MM_TRACK_X, PROGRESS_MM_TRACK_X_LARGE,
                              PROGRESS_MM_GAP_BOTTOM, "[test]")


def test_is_dead_is_false_for_a_live_handle_and_when_none():
    host = _bare_host()
    assert host._is_dead() is False              # no window open
    live = _StatusHandle(window_status=3, view_status=3, view_model="vm")
    host._active = (live, live)
    assert host._is_dead() is False


def test_is_dead_is_true_when_the_engine_destroyed_the_window_or_view():
    for kw in ({"window_status": 4}, {"window_status": 5}, {"view_status": 4},
               {"view_status": 5}, {"view_model": None}):
        host = _bare_host()
        h = _StatusHandle(**kw)
        host._active = (h, h)
        assert host._is_dead() is True, kw


def test_is_dead_fails_soft_to_alive_on_an_unreadable_status():
    # A false 'dead' would tear down and re-mount a healthy bar every tick -- so an unreadable
    # status must read as ALIVE, not dead.
    class _Boom(object):
        @property
        def windowStatus(self):
            raise RuntimeError("boom")
    host = _bare_host()
    host._active = (_Boom(), _Boom())
    assert host._is_dead() is False


class _FakeMount(object):
    """Stands in for both _BarView and _BarWindow so open_window()'s real mount path runs without
    the live client: it has load()/destroy()/detach() and the liveness fields _is_dead reads."""

    def __init__(self, *a, **k):
        self.windowStatus = 3
        self.viewStatus = 3
        self.viewModel = "vm"

    def load(self):
        pass

    def destroy(self):
        pass

    def detach(self):
        pass


def test_open_window_re_mounts_a_destroyed_handle_but_leaves_a_live_one(monkeypatch):
    host = _bare_host()
    monkeypatch.setattr(host, "_layout_id", lambda: 7)   # a resolvable layout
    monkeypatch.setattr(bar_window, "_BarView", _FakeMount)
    monkeypatch.setattr(bar_window, "_BarWindow", _FakeMount)

    v1 = host.open_window()
    assert v1 is not None
    # A LIVE handle is NOT needlessly re-created -- open_window returns the same view.
    assert host.open_window() is v1
    assert host.active_view() is v1

    host._sized = True   # a real mount would have flipped this via onSizeChanged
    # The engine destroys it the way it really does (View._cFini nulls the viewModel).
    host._active[1].viewModel = None
    assert host._is_dead() is True

    # The next open_window() (what battle_bridge.refresh() re-drives every tick) drops the dead
    # handle and re-mounts a fresh one -- and _sized is reset for a clean mount.
    v2 = host.open_window()
    assert v2 is not None and v2 is not v1
    assert host._sized is False
    assert host._is_dead() is False


# --- THE CORE REGRESSION: window.move() can silently NO-OP, not raise -------------------------
# _place()'s try/except fallback (the "last-good restore" tests above) only covers a move that
# RAISES. The pre-fix bug was different and worse: on a not-yet-realized window (the engine's
# 256x256 size-timeout fallback -- see the module docstring), window.move() to the real anchor
# applies NOTHING AT ALL -- no exception, the window just stays wherever _extent()'s own
# far-sentinel clamp parked it (the minimap's own corner). The OLD _place() stamped `_last_good`
# unconditionally right after that call, so has_placed() came back True and the vertical bar
# rendered PARKED ON THE MINIMAP. THE SHIPPED FIX discriminates on REALIZATION (surface !=
# _FALLBACK_SURFACE_SIZE), not on position -- see bar_window._place's own docstring for why
# position alone cannot tell a no-op apart from a legitimate off-screen clamp.

_EFF_LARGE_SURFACE = (230, 398)   # MUST track test_efficiency_surface_mirror (Large pin)
_EFF_LARGE_MAX = (_EFF_SPACE[0] - _EFF_LARGE_SURFACE[0], _EFF_SPACE[1] - _EFF_LARGE_SURFACE[1])
_PROG_LARGE_SURFACE = (242, 400)   # MUST track test_progress_surface_mirror (Large pin)
_PROG_LARGE_MAX = (_PROG_V_SPACE[0] - _PROG_LARGE_SURFACE[0],
                   _PROG_V_SPACE[1] - _PROG_LARGE_SURFACE[1])


class _RealizableWindow(_FakeWindow):
    """Like `_FakeWindow`, but BOTH `.size` (the surface) and the measured movable extent switch
    together off `realized`, keeping the FULL logical GUI space (`space`, the screen resolution)
    fixed -- exactly how the real engine works: extent = space - surface, and only the surface
    changes when the JS resizes it. While `realized` is False the surface is
    `bar_window._FALLBACK_SURFACE_SIZE` (256x256, the engine's un-resized fallback) and a move to
    anything OTHER than the far sentinel silently NO-OPS, mirroring the live bug -- once
    `realized` flips True the surface becomes the real size passed in and every move applies
    normally, exactly like `_FakeWindow`.

    `size`/`_max` are recomputed on every `move()` call (not just once) because `_extent()` reads
    the surface via a move-to-far-sentinel *before* `_place()` ever reads `.size` again for
    `_space()` -- both must already agree with `realized` at read time."""

    def __init__(self, space, real_size):
        self._space_wh = space
        self._real_size = real_size
        self.realized = False
        fallback = bar_window._FALLBACK_SURFACE_SIZE
        super(_RealizableWindow, self).__init__(
            space[0] - fallback[0], space[1] - fallback[1], size=fallback)

    def move(self, x, y, xAnchor=None, yAnchor=None):
        size = self._real_size if self.realized else bar_window._FALLBACK_SURFACE_SIZE
        self.size = size
        self._max = (self._space_wh[0] - size[0], self._space_wh[1] - size[1])
        self.moves.append((x, y))
        if (x, y) == (bar_window._FAR, bar_window._FAR):
            self.position = self._max
        elif self.realized:
            self.position = (x, y)
        # else: silent no-op on the still-256x256 surface -- the live bug this fixture pins.


def _efficiency_host_realizable(space=_EFF_SPACE, real_size=_EFF_LARGE_SURFACE):
    """The real Damage Efficiency host, against a `_RealizableWindow` -- the live-confirmed
    defect config: Vertical + Large + Fixed(minimap) alignment."""
    from moe_calculator.domain.constants import (
        EFFICIENCY_ANCHOR_X_OFFSET, EFFICIENCY_ANCHOR_Y_FRAC,
        EFFICIENCY_ANCHOR_Y_SHIFT, EFFICIENCY_ANCHOR_Y_SHIFT_LARGE, EFFICIENCY_MM_GAP_BOTTOM,
        EFFICIENCY_MM_TRACK_X, EFFICIENCY_MM_TRACK_X_LARGE)

    host = bar_window.BarHost(
        "MoEEfficiencyView", lambda: object(), EFFICIENCY_ANCHOR_Y_FRAC,
        EFFICIENCY_ANCHOR_X_OFFSET, EFFICIENCY_ANCHOR_Y_SHIFT, EFFICIENCY_ANCHOR_Y_SHIFT_LARGE,
        EFFICIENCY_MM_TRACK_X, EFFICIENCY_MM_TRACK_X_LARGE, EFFICIENCY_MM_GAP_BOTTOM, "[test-eff]")
    window = _RealizableWindow(space, real_size)
    host._active = (window, object())
    return host, window


def test_a_place_against_an_unrealized_window_does_not_report_placed(monkeypatch):
    # THE RED ASSERTION: the pre-fix code returned True here (proven below, RED-then-GREEN).
    monkeypatch.setattr(bar_window, "_minimap_size_index", lambda: 4)
    mod_settings._seed({
        mod_settings.PROGRESS_ORIENTATION_KEY: mod_settings.PROGRESS_ORIENT_VERTICAL,
        mod_settings.PROGRESS_SIZE_KEY: mod_settings.PROGRESS_SIZE_LARGE})
    host, window = _efficiency_host_realizable()
    assert host.has_placed() is False                     # never placed yet

    # The first _place() (mirrors _onReady, run against the not-yet-resized window -- surface
    # still the 256x256 fallback).
    host._place(window)
    assert window.size == bar_window._FALLBACK_SURFACE_SIZE
    corner = window._max
    assert window.position == corner, "fixture bug: the un-realized window actually moved"
    assert host.has_placed() is False, (
        "has_placed() came back True after a move that silently no-opped -- the bar would "
        "render PARKED ON THE MINIMAP (the pre-fix bug this test pins)")

    # Sanity: the intended point is genuinely far from the far-sentinel/minimap corner, or the
    # tolerance check this pins would be meaningless.
    intended = window.moves[-1]
    assert abs(intended[0] - corner[0]) > 50 or abs(intended[1] - corner[1]) > 50

    # The surface becomes realized (mirrors the JS's post-deadline size re-assert firing
    # onSizeChanged) and battle_bridge.refresh() drives ensure_placed() on its next tick.
    window.realized = True
    host.ensure_placed()
    assert host.has_placed() is True
    assert window.size == _EFF_LARGE_SURFACE
    assert window.position != corner
    # The TRUE resolved point for the real Large surface -- independently derived, not the bogus
    # point `intended` computed against the still-256x256 fallback space (space = extent +
    # surface, so a wrong surface at the first _place also poisons the space the anchor math
    # used): 1920 - 510(minimap@idx4) - 8(gap) - 5(overhang) - 214(track edge) == 1183,
    # 1080 - 28(gap_bottom) - 363(track edge y) == 689 -- but 689 is 7px BELOW the movable extent
    # (_EFF_LARGE_MAX[1] == 682), so _place clamps y into the extent (the real engine already
    # clamps this window on-screen; the clamp just makes the readback confirm instead of reject).
    assert window.position == (1183, 682)


def test_a_place_against_an_already_realized_window_places_normally(monkeypatch):
    # THE TOLERANCE GUARD: a healthy, already-realized window (the common case) must place and
    # report has_placed() True on the very first _place(), exactly as before the readback existed
    # -- zero regression on the happy path.
    monkeypatch.setattr(bar_window, "_minimap_size_index", lambda: 4)
    mod_settings._seed({
        mod_settings.PROGRESS_ORIENTATION_KEY: mod_settings.PROGRESS_ORIENT_VERTICAL,
        mod_settings.PROGRESS_SIZE_KEY: mod_settings.PROGRESS_SIZE_LARGE})
    host, window = _efficiency_host_realizable()
    window.realized = True
    host._place(window)
    assert host.has_placed() is True
    assert host._last_good == window.moves[-1]


class _UltrawideFallbackWindow(_FakeWindow):
    """An UNREALIZED window whose engine-forced "default view size" is deliberately NOT
    `bar_window._FALLBACK_SURFACE_SIZE` (256x256) -- the exact ultrawide-client defect the
    universal-readback fix targets (see the module docstring's ultrawide note and
    `_FALLBACK_SURFACE_SIZE`'s own "DEAD in shipped code" comment). Move-to-far-sentinel still
    self-calibrates the extent (mirroring `_extent`'s own trick); any OTHER move silently NO-OPS
    while unrealized and the readback falls back to (0, 0), exactly what the reported client's
    python.log shows (applied=(0, 0)). The unrealized surface is passed in explicitly and is
    NEVER (256, 256) -- proving the fix needs no knowledge of that constant, or any fixed fallback
    size, at all."""

    def __init__(self, space, unrealized_surface):
        max_x = space[0] - unrealized_surface[0]
        max_y = space[1] - unrealized_surface[1]
        super(_UltrawideFallbackWindow, self).__init__(max_x, max_y, size=unrealized_surface)

    def move(self, x, y, xAnchor=None, yAnchor=None):
        self.moves.append((x, y))
        if (x, y) == (bar_window._FAR, bar_window._FAR):
            self.position = self._max
        else:
            self.position = (0, 0)   # unrealized: the move did not apply; readback is (0, 0)


def test_a_place_against_an_unrealized_ultrawide_fallback_does_not_report_placed(monkeypatch):
    # THE ULTRAWIDE REGRESSION this fix actually targets: the OLD `surface !=
    # _FALLBACK_SURFACE_SIZE` discriminator assumed every unrealized window is stuck at exactly
    # (256, 256). True on the dev machine it was measured against; FALSE on a real ultrawide
    # client at 1x interface scale, whose engine-forced fallback is some OTHER size -- so the old
    # test read `surface != (256, 256)` as True, took the "trust the move outright" branch, and
    # stamped `_last_good` even though the move below had silently no-opped, parking the bar on the
    # minimap. This fixture's unrealized surface (1720, 720) is neither (256, 256) NOR
    # `bar_window._FALLBACK_SURFACE_SIZE`, on purpose -- the fix must not need to know it. RED
    # against the old surface-size branch (it would report has_placed() True here); GREEN against
    # the universal position-readback fix.
    monkeypatch.setattr(bar_window, "_minimap_size_index", lambda: 4)
    mod_settings._seed({
        mod_settings.PROGRESS_ORIENTATION_KEY: mod_settings.PROGRESS_ORIENT_VERTICAL,
        mod_settings.PROGRESS_SIZE_KEY: mod_settings.PROGRESS_SIZE_LARGE})
    from moe_calculator.domain.constants import (
        EFFICIENCY_ANCHOR_X_OFFSET, EFFICIENCY_ANCHOR_Y_FRAC,
        EFFICIENCY_ANCHOR_Y_SHIFT, EFFICIENCY_ANCHOR_Y_SHIFT_LARGE, EFFICIENCY_MM_GAP_BOTTOM,
        EFFICIENCY_MM_TRACK_X, EFFICIENCY_MM_TRACK_X_LARGE)
    host = bar_window.BarHost(
        "MoEEfficiencyView", lambda: object(), EFFICIENCY_ANCHOR_Y_FRAC,
        EFFICIENCY_ANCHOR_X_OFFSET, EFFICIENCY_ANCHOR_Y_SHIFT, EFFICIENCY_ANCHOR_Y_SHIFT_LARGE,
        EFFICIENCY_MM_TRACK_X, EFFICIENCY_MM_TRACK_X_LARGE, EFFICIENCY_MM_GAP_BOTTOM, "[test-uw]")
    window = _UltrawideFallbackWindow(_EFF_SPACE, unrealized_surface=(1720, 720))
    host._active = (window, object())

    host._place(window)
    assert window.position == (0, 0), "the unrealized no-op readback is (0, 0), not the far corner"
    assert host.has_placed() is False, (
        "an ultrawide client's non-256x256 unrealized fallback must not be mistaken for a "
        "realized surface -- the old surface-size discriminator trusted this no-op move outright, "
        "which is the exact regression this fix closes")


class _ClampingRealizedWindow(_FakeWindow):
    """A REALIZED window (its `.size` is the plain `_SURFACE` default -- never the 256x256
    fallback) whose move() CLAMPS to the movable extent, exactly like the real engine clamps
    every Wulf window to the screen (memory `engine-clamps-every-wulf-window-to-screen-and-the-
    mod-depends-on-it`). Because `_place` now pre-clamps the target INTO that extent, the move it
    issues is already in-bounds and lands dead-on -- so a legitimate off-screen Free/legacy pin
    resolves to the extent's corner and the bar SHOWS there (the pre-b24e0b4 clamp-visible
    behaviour, restored)."""

    def move(self, x, y, xAnchor=None, yAnchor=None):
        self.moves.append((x, y))
        if (x, y) == (bar_window._FAR, bar_window._FAR):
            self.position = self._max
        else:
            self.position = (min(max(x, 0), self._max[0]), min(max(y, 0), self._max[1]))


class _UnrealizedZeroWindow(_FakeWindow):
    """An UNREALIZED surface modelling the REPORTED client's real no-op: the far-sentinel move
    still measures the extent (mirrors _extent's own trick), but a real in-bounds move NO-OPS and
    the readback falls back to (0, 0) -- exactly what the reported python.log shows
    (applied=(0, 0) surface=(0, 0)), NOT the far-sentinel corner (memory
    `bar-host-place-must-gate-on-surface-realization`). Since the clamp can never produce (0, 0)
    for a real pin (the AUTO sentinel is floored to (1, 0)), this no-op is always > tolerance from
    the target, so the plain readback check rejects it -- the cold-start bar stays hidden."""

    def move(self, x, y, xAnchor=None, yAnchor=None):
        self.moves.append((x, y))
        if (x, y) == (bar_window._FAR, bar_window._FAR):
            self.position = self._max
        else:
            self.position = (0, 0)   # unrealized: the move did not apply; readback is (0, 0)


def test_a_clamped_bottom_right_pin_shows_when_realized_but_hides_on_cold_start():
    # v3.1.4 off-screen-pin fix: _place clamps the resolved target INTO the movable extent BEFORE
    # moving, so a wildly-off legacy Free pin (5000, 5000) clamps to the extent's bottom-right
    # corner. On a REALIZED surface that corner target lands dead-on and the bar SHOWS there
    # (restoring the pre-b24e0b4 clamp-visible behaviour). The at_far_corner guard that briefly
    # rejected this was CUT: it assumed the unrealized no-op parks at the far corner, but the real
    # client parks it at (0, 0), so the guard caught nothing real and only hid this legitimate
    # realized corner pin.
    seed = {mod_settings.PROGRESS_ALIGNMENT_KEY: mod_settings.PROGRESS_ALIGN_FREE,
            mod_settings.PROGRESS_POS_FRAME_KEY: mod_settings.POS_FRAME_LEGACY,
            mod_settings.BAR_POS_X_KEY: 5000, mod_settings.BAR_POS_Y_KEY: 5000}

    def _fresh_host():
        host = bar_window.BarHost("test.item", lambda: object(), 0.865, 0,
                                  PROGRESS_ANCHOR_Y_SHIFT, PROGRESS_ANCHOR_Y_SHIFT,
                                  PROGRESS_MM_TRACK_X, PROGRESS_MM_TRACK_X_LARGE,
                                  PROGRESS_MM_GAP_BOTTOM, "[test]")
        return host

    # REALIZED -> the clamped corner target applies dead-on -> SHOWS.
    mod_settings._seed(dict(seed))
    host = _fresh_host()
    window = _ClampingRealizedWindow(1664, 824)
    host._active = (window, object())
    host._place(window)
    assert window.moves[-1] == (1664, 824), "the off-screen pin clamps to the extent's corner"
    assert window.position == (1664, 824), "the realized window applies the clamped corner target"
    assert host.has_placed() is True, "a realized clamped corner pin must SHOW at the corner"

    # UNREALIZED cold-start -> the same clamped corner target no-ops, the readback is (0, 0), far
    # from the target -> the bar stays HIDDEN (no flash) until the surface realizes.
    mod_settings._seed(dict(seed))
    host = _fresh_host()
    window = _UnrealizedZeroWindow(1664, 824)
    host._active = (window, object())
    host._place(window)
    assert window.position == (0, 0), "the unrealized no-op readback is (0, 0), not the corner"
    assert host.has_placed() is False, "a cold-start no-op must stay hidden -- the real regression"


# --- THE DERIVED PLACEMENT AT LARGE, END TO END, BOTH BARS --------------------------------------
# The coverage gap flagged alongside the fix: the Default-size end-to-end pin above
# (test_the_vertical_efficiency_bar_lands_on_the_derived_position) has no Large twin, and neither
# bar had one for the Moving Average bar at all. Composed through each bar's REAL _resolve against
# its own real Large surface (test_efficiency_surface_mirror / test_progress_surface_mirror), and
# checked against an INDEPENDENTLY hand-derived expected point (not `anchor_minimap(<the same
# constants>)`, which only re-checks constant wiring already covered by
# test_minimap_overhang_scales_to_the_large_constant_when_vertical_and_large) --
# `x = space_x - mm_size - gap - overhang - edge_x`, `y = space_y - gap_bottom - edge_y`, by hand.

def test_the_vertical_efficiency_bar_lands_on_the_derived_position_at_large(monkeypatch):
    from moe_calculator.domain.constants import EFFICIENCY_MM_TRACK_X_LARGE, MINIMAP_SIZES

    monkeypatch.setattr(bar_window, "_minimap_size_index", lambda: 4)
    mod_settings._seed({mod_settings.PROGRESS_ORIENTATION_KEY: mod_settings.PROGRESS_ORIENT_VERTICAL,
                        mod_settings.PROGRESS_SIZE_KEY: mod_settings.PROGRESS_SIZE_LARGE,
                        mod_settings.BAR_POS_X_KEY: 0, mod_settings.BAR_POS_Y_KEY: 0})
    host, window = _efficiency_host(max_xy=_EFF_LARGE_MAX, surface=_EFF_LARGE_SURFACE)
    space_x, space_y = host._space(window)
    resolved = _resolved(host, window)
    # 1920 - 510(minimap idx4) - 8(MM_GAP) - 5(MM_TICK_OVERHANG_LARGE) - 214(track edge) == 1183
    # 1080 - 28(EFFICIENCY_MM_GAP_BOTTOM) - 363(MM_TRACK_Y_LARGE) == 689
    assert resolved == (1183, 689)
    mm_size = MINIMAP_SIZES[4]
    assert resolved[0] + EFFICIENCY_MM_TRACK_X_LARGE <= space_x - mm_size, \
        "the Large Damage Efficiency bar's track overlaps the minimap"


def test_the_vertical_progress_bar_lands_on_the_derived_position_at_large(monkeypatch):
    from moe_calculator.domain.constants import PROGRESS_MM_TRACK_X_LARGE, MINIMAP_SIZES

    monkeypatch.setattr(bar_window, "_minimap_size_index", lambda: 4)
    mod_settings._seed({mod_settings.PROGRESS_ORIENTATION_KEY: mod_settings.PROGRESS_ORIENT_VERTICAL,
                        mod_settings.PROGRESS_SIZE_KEY: mod_settings.PROGRESS_SIZE_LARGE,
                        mod_settings.BAR_POS_X_KEY: 0, mod_settings.BAR_POS_Y_KEY: 0})
    host, window = _progress_vertical_host(max_xy=_PROG_LARGE_MAX, surface=_PROG_LARGE_SURFACE)
    space_x, space_y = host._space(window)
    resolved = _resolved(host, window)
    # 1920 - 510(minimap idx4) - 8(MM_GAP) - 5(MM_TICK_OVERHANG_LARGE) - 226(track edge) == 1171
    # 1080 - 30(PROGRESS_MM_GAP_BOTTOM) - 363(MM_TRACK_Y_LARGE) == 687
    assert resolved == (1171, 687)
    mm_size = MINIMAP_SIZES[4]
    assert resolved[0] + PROGRESS_MM_TRACK_X_LARGE <= space_x - mm_size, \
        "the Large Moving Average bar's track overlaps the minimap"


# DELETED (v23, the Fixed-alignment redesign): the RULE 5 vertical + Damage Log right-edge
# invariance tests (`_dl_vertical`, `_right_edge`, `_PROG_V_SURFACE_LARGE`, `_EFF_V_SURFACE_LARGE`,
# and `test_x_shift_large_default_is_a_pure_no_op_for_horizontal_and_minimap`). A vertical bar
# resolving to the Damage Log anchor is no longer reachable through the UI OR a stored value at
# all (Alignment only ever stores Fixed or Free; Fixed always resolves to Minimap when vertical --
# see bar_window._resolve and mod_settings.py's SETTINGS_VERSION 22->23 comment), and the
# `x_shift_large` machinery those tests protected is deleted with it (constants.py,
# domain/positioning.py, bar_window.BarHost, progress_view.py, efficiency_view.py).


# --- LOG_PROD diagnostics: the reject line's new alignment/off fields, and the new success line -

def test_place_reject_line_echoes_alignment_and_offset(monkeypatch):
    # The reject LOG_PROD line grew `alignment=`/`off=(...)` fields so a remote python.log can
    # confirm the Fixed/Free shared-pair fix -- drive an UNREALIZED cold-start (the real rejection
    # path: the move no-ops, readback (0, 0)) and check the logged text carries both new fields
    # (and the pre-existing ones), not just that it fired.
    mod_settings._seed({
        mod_settings.PROGRESS_ALIGNMENT_KEY: mod_settings.PROGRESS_ALIGN_FREE,
        mod_settings.PROGRESS_POS_FRAME_KEY: mod_settings.POS_FRAME_LEGACY,
        mod_settings.BAR_POS_X_KEY: 5000, mod_settings.BAR_POS_Y_KEY: 5000})
    host = bar_window.BarHost("test.item", lambda: object(), 0.865, 0,
                              PROGRESS_ANCHOR_Y_SHIFT, PROGRESS_ANCHOR_Y_SHIFT,
                              PROGRESS_MM_TRACK_X, PROGRESS_MM_TRACK_X_LARGE,
                              PROGRESS_MM_GAP_BOTTOM, "[test]")
    window = _UnrealizedZeroWindow(1664, 824)
    host._active = (window, object())

    logged = []
    monkeypatch.setattr(bar_window, "LOG_PROD", lambda msg: logged.append(msg))
    host._place(window)

    assert host.has_placed() is False
    assert len(logged) == 1
    assert "placement rejected" in logged[0]
    assert "alignment=%d" % mod_settings.PROGRESS_ALIGN_FREE in logged[0]
    assert "off=(5000, 5000)" in logged[0]


def test_place_success_logs_once_per_mount_and_includes_alignment(monkeypatch):
    # The new success line (`_place_logged`) must fire exactly ONCE for the host's lifetime, not
    # on every successful _place (battle_bridge.refresh() drives _place every tick) -- every normal
    # battle would otherwise spam python.log. Patch LOG_PROD BEFORE the host is even built, so
    # _host's own internal first-placement call is captured as the "first success" this test pins.
    logged = []
    monkeypatch.setattr(bar_window, "LOG_PROD", lambda msg: logged.append(msg))

    host, window = _host(1664, 824, align=mod_settings.PROGRESS_ALIGN_FIXED)
    assert host._place_logged is True
    assert len(logged) == 1, "the first successful _place did not log the confirmed-placement line"
    assert "placement confirmed" in logged[0]
    assert "alignment=%d" % mod_settings.PROGRESS_ALIGN_FIXED in logged[0]

    # A SECOND real success against the same host (mirrors battle_bridge.refresh() driving _place
    # every tick) must NOT log again -- the latch stays flipped for the host's whole mount.
    host._place(window)
    assert len(logged) == 1, "a second successful _place re-fired the once-per-mount success line"


def test_place_logged_latch_resets_on_remount(monkeypatch):
    # Mirrors _reject_logged's own remount-reset contract: a fresh open_window() (a new battle)
    # must reset _place_logged so the new mount gets its own confirmed-placement line, rather than
    # inheriting a stale True from a previous battle that never mounts again.
    host = _bare_host()
    monkeypatch.setattr(host, "_layout_id", lambda: 7)
    monkeypatch.setattr(bar_window, "_BarView", _FakeMount)
    monkeypatch.setattr(bar_window, "_BarWindow", _FakeMount)

    host.open_window()
    host._place_logged = True   # simulate a prior mount's confirmed placement

    host._sized = True
    host._active[1].viewModel = None   # engine destroyed the handle
    assert host._is_dead() is True

    host.open_window()   # re-mount
    assert host._place_logged is False


def test_last_good_resets_on_remount_so_has_placed_is_false_until_reconfirmed(monkeypatch):
    # A mid-battle remount (dead-handle heal / variant or orientation flip) gives a FRESH unrealized
    # window that has placed nothing yet. _last_good -- what has_placed() reads -- must reset with the
    # other cold-start latches, or a stale True from the previous mount makes ensure_placed()
    # early-return (no retry) and opens the visibility gate immediately, flashing the bar mis-placed
    # at the far-sentinel corner before this window's own _place ever confirms.
    host = _bare_host()
    monkeypatch.setattr(host, "_layout_id", lambda: 7)
    monkeypatch.setattr(bar_window, "_BarView", _FakeMount)
    monkeypatch.setattr(bar_window, "_BarWindow", _FakeMount)

    host.open_window()
    host._last_good = (500, 300)          # simulate the previous mount's confirmed placement
    assert host.has_placed() is True

    host._sized = True
    host._active[1].viewModel = None      # engine destroyed the handle
    assert host._is_dead() is True

    host.open_window()                    # re-mount
    assert host._last_good is None
    assert host.has_placed() is False, "a fresh remount must not inherit the prior mount's placement"


# --- COLD-START PUSH GAP: _on_size_changed must push on a has_placed() False->True transition ---
# _BarWindow._onReady()'s own first _place() call races the JS's real surface resize (see its own
# docstring): on a cold mount the surface is still the engine's 256x256 fallback, that first
# _place() rejects, and has_placed() stays False. The FIX is in _on_size_changed: it now lazily
# calls battle_bridge.refresh() on exactly the has_placed() False->True transition, so the late
# successful placement still pushes visible=True to the VM (the only other writer of that VM
# field is battle_bridge.refresh()/push_progress/push_efficiency, and nothing else on this path
# calls it).

def _bind_on_size_changed(window, host):
    """Wire `_BarWindow._on_size_changed`'s own two collaborators (`_place`/`_host`) directly onto
    a fake WINDOW (not a separate `_BarWindow` instance) -- the real `_BarWindow` IS the engine
    window (`_onReady` calls `self._place(self)`), so `_place`'s `window.move()`/`.size`/
    `.position` reads must land on the SAME object `_on_size_changed` is called against. Building
    a standalone `_BarWindow` would also need a live WindowFlags/WindowLayer that this file's
    module-top stubs deliberately keep permissive stand-ins for. Returns a zero-arg callable
    matching `Window.onSizeChanged`'s handler signature."""
    window._place = host._place
    window._host = host
    bound = bar_window._BarWindow._on_size_changed.__get__(window)
    return bound


def test_on_size_changed_pushes_battle_bridge_refresh_on_cold_placement_transition(monkeypatch):
    monkeypatch.setattr(bar_window, "_minimap_size_index", lambda: 4)
    mod_settings._seed({
        mod_settings.PROGRESS_ORIENTATION_KEY: mod_settings.PROGRESS_ORIENT_VERTICAL,
        mod_settings.PROGRESS_SIZE_KEY: mod_settings.PROGRESS_SIZE_LARGE})
    host, window = _efficiency_host_realizable()
    on_size_changed = _bind_on_size_changed(window, host)
    refresh_calls = []

    def _fake_refresh():
        refresh_calls.append(1)
        host.ensure_placed()   # mirrors the real battle_bridge.refresh()'s per-host retry

    monkeypatch.setattr(battle_bridge, "refresh", _fake_refresh)

    # Cold mount: the surface is still the 256x256 fallback -> _place() rejects -> no transition,
    # no push.
    on_size_changed(1, 0, 0)
    assert host.has_placed() is False
    assert refresh_calls == [], "a rejected placement must not push a refresh"

    # The JS resizes the surface for real -> _place() now succeeds -> has_placed() flips
    # False->True -> EXACTLY ONE refresh() push.
    window.realized = True
    on_size_changed(1, window._real_size[0], window._real_size[1])
    assert host.has_placed() is True
    assert len(refresh_calls) == 1, "the cold False->True transition must push exactly once"

    # A ROUTINE resize afterward (already placed) must NOT push again -- the False->True guard.
    on_size_changed(1, window._real_size[0], window._real_size[1])
    assert host.has_placed() is True
    assert len(refresh_calls) == 1, "a resize that leaves has_placed() True re-fired the push"

    # NO INFINITE RE-ENTRANCY: the one push that DID fire drove refresh() -> ensure_placed() ->
    # _place(), and that inner _place() found has_placed() already True on entry to THIS test's
    # fake, so it took the no-op branch rather than cascading into another onSizeChanged/refresh.
    assert len(refresh_calls) == 1



def test_clamp_to_extent_pulls_offscreen_targets_into_bounds():
    """_clamp_to_extent makes every resolved target reachable so _place's readback is a pure
    realization test (the v3.1.4 off-screen-pin bug: an off-screen target the engine clamps back
    on-screen fails the readback and hides the bar forever)."""
    # Off-screen HIGH (below/right of the extent) clamps to the far edge -- the shipped bug's shape:
    # y=1446 on a screen whose bar has max_y=1184.
    assert bar_window._clamp_to_extent(2814, 1446, 3184, 1184) == (2814, 1184)
    # Off-screen NEGATIVE (past top-left) clamps to 0 on each axis -- but never the AUTO sentinel.
    assert bar_window._clamp_to_extent(-50, -20, 3184, 1184) == (1, 0)
    # In-bounds is returned unchanged (no spurious movement of a valid pin).
    assert bar_window._clamp_to_extent(500, 300, 3184, 1184) == (500, 300)
    # A target clamping to exactly (0, 0) is floored 1px on x so it can't be misread as Free's AUTO
    # sentinel by _materialise's write-back (unclamping-drag-is-constrained-by-the-auto...).
    assert bar_window._clamp_to_extent(0, 0, 3184, 1184) == (1, 0)
