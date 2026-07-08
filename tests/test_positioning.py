# -*- coding: utf-8 -*-
"""Tests for the engine-free overlay-placement math. Runs on Python 3 (no game engine):
domain.positioning imports zero game symbols. The extents below are the REAL far-sentinel
readouts measured in-client at 4K (probe_scale.py): 1x -> space 3840x2160, 2x -> 1920x1080,
surface fixed 256x256, so movable extent = space - 256."""
from moe_calculator.domain.positioning import anchor_top_left, damage_log_summary_hidden
from moe_calculator.domain.constants import (
    BATTLE_ANCHOR_X, BATTLE_ANCHOR_Y, BATTLE_ANCHOR_X_RAISED, BATTLE_ANCHOR_Y_RAISED)


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


# --- Phase 2: damage-log-summary-aware anchor -------------------------------
# The "Summarized damage" group is four flags. When ALL four are unticked, the summary
# block disappears and the damage-log events shift UP, so the overlay must use the raised
# anchor. Any one flag ticked -> the block is present -> default anchor.


def test_summary_hidden_only_when_all_four_unticked():
    assert damage_log_summary_hidden(False, False, False, False) is True


def test_summary_visible_when_any_single_flag_ticked():
    # Each of the four flags on its own keeps the summary block present (default anchor).
    assert damage_log_summary_hidden(True, False, False, False) is False
    assert damage_log_summary_hidden(False, True, False, False) is False
    assert damage_log_summary_hidden(False, False, True, False) is False
    assert damage_log_summary_hidden(False, False, False, True) is False


def test_summary_visible_when_all_ticked():
    assert damage_log_summary_hidden(True, True, True, True) is False


def test_summary_hidden_coerces_truthy_falsey():
    # getSetting returns the stored value (may be 0/1 or None); bool()-coercion means
    # 0/None read as unticked and any truthy value reads as ticked.
    assert damage_log_summary_hidden(0, 0, 0, 0) is True
    assert damage_log_summary_hidden(None, None, None, None) is True
    assert damage_log_summary_hidden(0, 1, 0, 0) is False


def test_raised_anchor_is_higher_than_default():
    # The raised anchor must sit ABOVE the default (larger y_from_bottom -> smaller top y).
    # Guards against someone leaving the two constants equal (Phase 2 would then be a no-op).
    assert BATTLE_ANCHOR_Y_RAISED > BATTLE_ANCHOR_Y


def test_raised_anchor_has_its_own_x():
    # Phase 2's raised anchor carries its own X (calibrated left of the default here), which
    # must be a valid on-screen offset and independent of the signed-off default X.
    assert BATTLE_ANCHOR_X_RAISED >= 0
    assert BATTLE_ANCHOR_X == 264  # default X stays exactly as signed off in Phase 1


def test_raised_anchor_places_left_and_up_of_default():
    # With the calibrated raised anchor, the window sits left of and above the default
    # placement (same movable extent). Concrete regression check on the shipped values.
    xd, yd = anchor_top_left(3584, 1904, BATTLE_ANCHOR_X, BATTLE_ANCHOR_Y)
    xr, yr = anchor_top_left(3584, 1904, BATTLE_ANCHOR_X_RAISED, BATTLE_ANCHOR_Y_RAISED)
    assert xr < xd   # raised X (215) < default X (264)
    assert yr < yd   # raised (33 from bottom) -> smaller top y than bottom-flush
