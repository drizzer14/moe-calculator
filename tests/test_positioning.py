# -*- coding: utf-8 -*-
"""Tests for the engine-free overlay-placement math. Runs on Python 3 (no game engine):
domain.positioning imports zero game symbols. The extents below are the REAL far-sentinel
readouts measured in-client at 4K (probe_scale.py): 1x -> space 3840x2160, 2x -> 1920x1080,
surface fixed 256x256, so movable extent = space - 256."""
from moe_calculator.domain.positioning import anchor_top_left
from moe_calculator.domain.constants import BATTLE_ANCHOR_X, BATTLE_ANCHOR_Y


# Measured movable extents (space - 256 surface) at 4K.
_EXTENT_1X = (3584, 1904)   # logical space 3840x2160
_EXTENT_2X = (1664, 824)    # logical space 1920x1080


def test_fixed_offset_is_scale_invariant():
    # The whole point of Phase 1: the SAME logical offset (264 from left, bottom-flush) at
    # BOTH scales -- reproducing the 2x-aligned placement at 1x (where the old fraction anchor
    # wrongly landed at x=529). X is identical; Y is bottom-flush (= each scale's max_y).
    x1, y1 = anchor_top_left(_EXTENT_1X[0], _EXTENT_1X[1], BATTLE_ANCHOR_X, BATTLE_ANCHOR_Y)
    x2, y2 = anchor_top_left(_EXTENT_2X[0], _EXTENT_2X[1], BATTLE_ANCHOR_X, BATTLE_ANCHOR_Y)
    assert (x1, y1) == (264, 1904)
    assert (x2, y2) == (264, 824)
    assert x1 == x2 == 264  # X does not change with scale


def test_y_from_bottom_raises_the_panel():
    # A positive y_from_bottom moves the top-left UP (smaller y) -- the Phase-2 raised anchor.
    _, y0 = anchor_top_left(3584, 1904, 264, 0)
    _, y200 = anchor_top_left(3584, 1904, 264, 200)
    assert y0 == 1904
    assert y200 == 1704
    assert y200 < y0


def test_clamps_x_into_movable_extent():
    # An offset past the right edge clamps to max_x (never off-screen).
    x, _ = anchor_top_left(1664, 824, 99999, 0)
    assert x == 1664


def test_clamps_y_non_negative():
    # A y_from_bottom larger than the whole extent clamps the top-left to 0 (top edge), not
    # a negative off-screen coordinate.
    _, y = anchor_top_left(3584, 1904, 264, 99999)
    assert y == 0


def test_zero_offsets_sit_at_bottom_left_corner():
    x, y = anchor_top_left(3584, 1904, 0, 0)
    assert (x, y) == (0, 1904)
