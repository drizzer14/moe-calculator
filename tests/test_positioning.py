# -*- coding: utf-8 -*-
"""Tests for the engine-free overlay-placement math. Runs on Python 3 (no game engine):
domain.positioning imports zero game symbols. The extents below are the REAL far-sentinel
readouts measured in-client at 4K (probe_scale.py): 1x -> space 3840x2160, 2x -> 1920x1080,
surface fixed 256x256, so movable extent = space - 256."""
from moe_calculator.domain.positioning import (
    anchor_top_left, damage_log_summary_hidden, efficiency_panel_wide)
from moe_calculator.domain.constants import (
    BATTLE_ANCHOR_X, BATTLE_ANCHOR_Y, BATTLE_ANCHOR_X_RAISED, BATTLE_ANCHOR_Y_RAISED,
    BATTLE_ANCHOR_X_SHIFT, EFFICIENCY_WIDE_THRESHOLD)


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


# --- 5-digit efficiency-panel right-shift -----------------------------------
# When an ENABLED "Summarized damage" total goes 5-digit (> EFFICIENCY_WIDE_THRESHOLD), WG's
# panel widens and the overlay shifts right by BATTLE_ANCHOR_X_SHIFT. flags/values are aligned
# (total, blocked, assist, stun): flags = which totals are drawn, values = their amounts.
_ALL_ON = (True, True, True, True)
_ALL_OFF = (False, False, False, False)
_T = EFFICIENCY_WIDE_THRESHOLD


def test_wide_when_an_enabled_total_exceeds_threshold():
    assert efficiency_panel_wide(_ALL_ON, (10000, 0, 0, 0), _T) is True


def test_not_wide_when_high_total_is_disabled():
    # A 5-digit total whose summary flag is unticked isn't drawn -> can't widen the panel.
    assert efficiency_panel_wide((False, True, True, True), (10000, 0, 0, 0), _T) is False


def test_not_wide_when_enabled_totals_below_threshold():
    assert efficiency_panel_wide(_ALL_ON, (9999, 9999, 9999, 9999), _T) is False


def test_threshold_is_strict_boundary():
    # Exactly 9999 (4 digits) does NOT widen; 10000 (5 digits) does.
    assert efficiency_panel_wide(_ALL_ON, (9999, 0, 0, 0), _T) is False
    assert efficiency_panel_wide(_ALL_ON, (10000, 0, 0, 0), _T) is True


def test_not_wide_all_zero():
    assert efficiency_panel_wide(_ALL_ON, (0, 0, 0, 0), _T) is False


def test_wide_checks_each_enabled_column():
    # Any single enabled 5-digit total (blocked / assist / stun) triggers the shift.
    assert efficiency_panel_wide(_ALL_ON, (0, 12000, 0, 0), _T) is True
    assert efficiency_panel_wide(_ALL_ON, (0, 0, 12000, 0), _T) is True
    assert efficiency_panel_wide(_ALL_ON, (0, 0, 0, 12000), _T) is True


def test_not_wide_when_all_flags_off():
    # No totals drawn at all (raised-anchor case) -> never widened, whatever the values.
    assert efficiency_panel_wide(_ALL_OFF, (50000, 50000, 50000, 50000), _T) is False


def test_wide_coerces_flag_and_guards_none_value():
    # getSetting flags may be 0/1/None; a value may read None on a bad fetch -> treated as 0.
    assert efficiency_panel_wide((1, 0, 0, 0), (10000, None, None, None), _T) is True
    assert efficiency_panel_wide((0, 0, 0, 0), (10000, 0, 0, 0), _T) is False
    assert efficiency_panel_wide((1, 0, 0, 0), (None, 0, 0, 0), _T) is False


def test_shift_constant_is_positive():
    # A positive addend shifts the window RIGHT (x measured from the left edge). Guards against
    # the constant being left at 0 (the feature would then be a silent no-op).
    assert BATTLE_ANCHOR_X_SHIFT > 0


def test_shift_composes_with_default_anchor():
    # The shift adds to the DEFAULT anchor's X; the shifted placement sits right of the unshifted
    # one (same movable extent).
    xd, _ = anchor_top_left(3584, 1904, BATTLE_ANCHOR_X, BATTLE_ANCHOR_Y)
    xd_s, _ = anchor_top_left(3584, 1904, BATTLE_ANCHOR_X + BATTLE_ANCHOR_X_SHIFT, BATTLE_ANCHOR_Y)
    assert xd_s > xd


def test_shift_never_applies_in_the_raised_state():
    # The raised anchor means the summary block is COLLAPSED (all four flags off) -- WG doesn't
    # draw the totals, so nothing can widen and the shift must not fire. efficiency_panel_wide is
    # the gate _place uses; with every flag off it is False regardless of how huge the values are.
    assert efficiency_panel_wide(_ALL_OFF, (99999, 99999, 99999, 99999), _T) is False


def test_wide_does_not_truncate_on_short_values_tuple():
    # A fail-soft adapter read that returns FEWER values than flags must not silently drop the
    # trailing column via zip-truncation: a 5-digit total there would be missed and the overlay
    # would collide with the widened panel. The missing value defaults to 0 (no false shift)...
    assert efficiency_panel_wide(_ALL_ON, (0, 0, 0), _T) is False
    # ...and a short FLAGS tuple with a wide value present still fires (missing flag = ticked).
    assert efficiency_panel_wide((True,), (0, 0, 0, 12000), _T) is True
