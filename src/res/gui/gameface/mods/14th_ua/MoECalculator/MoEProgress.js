// 14th_ua's MoE Calculator -- in-battle centre-screen MoE progress bar (the TRANSIENT one; the
// always-on corner readout is MoEBattle.js). Front-end of a STANDALONE OpenWG-registered Gameface
// view (MoEProgressView.html, declared in gui/gen_resources/com.14th_ua.moe_calculator.json) that
// bridge/progress_view.py opens as a CONTENT-SIZED (NOT full-screen), input-transparent window
// centred over the battle HUD. Do NOT re-add full-screen sizing / width:100% -- see
// bridge/battle_view.py for the Ctrl+click/hover input-steal that cost us.
//
// Because this is a registered view, OUR data model (ProgressVM) IS the view's own root
// ViewModel: a bare ModelObserver() with NO feature name, fields read DIRECTLY off the root
// (model.projAvg, ...). No nested submodel and NO unwrap dance -- that is only the garage's
// nested-model path.
//
// WHAT THE BAR SHOWS: where the career moving-average combined damage sits between the
// requirement for the mark you HOLD and the requirement for the next one, and the nudge THIS
// battle contributes. Everything derived here is derived in COMBINED DAMAGE, not percentiles:
// Python pushes the two axis ends plus pre_avg / proj_avg and this file does the arithmetic.
//
// THE LOOK IS FINISHED AND NOT NEGOTIABLE: MoEProgress.css was settled in a browser tuner
// (tools/dev/gen_bar_tuner.ps1) and copied verbatim, and this file is a port of that tuner's own
// preview script (setPos / showVal / replay / the animationend force-settle) -- not an
// invention. Its comments explain every value; read them before changing a number. The battle
// window has NO hot-reload (it pins its resources at client launch), so every tweak here costs a
// full client relaunch: tune in the browser, not in the client.
//
// TWO ORIENTATIONS, ONE DOCUMENT. The bar draws HORIZONTALLY (MoEProgress.css, .mp-*) or VERTICALLY
// beside the minimap (MoEProgressVertical.css, .mpv-*) depending on mod_settings'
// progress_bar_orientation, pushed as the VM's `vertical`. Both stylesheets are <link>ed from
// MoEProgressView.html and are namespace-DISJOINT; the choice is a MOUNT-TIME branch (goVertical),
// NOT a second registered layout. The PLACEMENT half is Python's and already orientation-aware (bridge/bar_window._resolve).
//
// pointer-events:none throughout (in the CSS) -- pure HUD info, never an input target.
import { ModelObserver } from "../../libs/model.js";
// The transient machinery -- arming, the negative-delay debounce, the Alt peek's pause/seek, the end
// race and the surface re-assert -- is SHARED with MoEEfficiency.js. Every behaviour in there cost a
// client relaunch to find; read its header before changing anything that touches timing. Separate
// documents, so this module is instantiated twice with no cross-talk.
import { createTransient, fmt, pctText, FADE_IN_MS } from "./MoEBarTransient.js";

// No feature name -> observe this view's OWN root model (window.model == ProgressVM).
const observer = ModelObserver();

// This bar's ONE timing of its own: when the bottom numeral commits to proj_avg. It tracks
// tickDelayMs by construction, which is the shared FADE_IN_MS.
const VALUE_SWAP_MS = FADE_IN_MS;

// --- the surface, and the rigid shift into it ----------------------------------------------
// A Gameface view PUSHES its own size to C++ through the `viewEnv` global
// (viewEnv.resizeViewRem(w, h), rem == logical px); a view that never calls it gets the engine's
// "default view size" fallback after a `Size calculation timeout` -- a flat 256x256 logical px,
// which is what clipped this bar. WG precedent for the same window shape: DogTagMarkerView.js
// calls resize(500, 300, "rem") once on mount, and ~85 WG views do the same. There is NO
// Python-side and NO resource-declaration lever for this (see bridge/bar_window.py).
//
// BUT THE ENGINE ALSO TRIES TO MEASURE THE DOCUMENT, AND ITS FALLBACK RUNS LAST AND WINS. Pushing
// the size is not sufficient on its own: our resize landed at 04.8s, the size-calculation deadline
// expired at 06.2s and its action ("Set the default view size") overwrote our pushed size with the
// 256x256 default. The static, in-flow #moe-bar-box (MoEProgressView.html, sized in
// MoEProgress.css to exactly the derived surface -- keep it in lockstep with the BOX_*/PAD_REM
// below) was meant to make the document measurable and stop the timeout. RE-MEASURED LIVE: IT DOES
// NOT. The box is there, in-flow and correctly sized, and the timeout fires anyway. So the shared
// module's SURFACE_REASSERT_MS is not a belt-and-braces guard -- it is the ONLY fix, and the window
// before it is the one T.settled() hides the bar through.
//
// The composition's MEASURED bounding box, document origin at (0,0) and 1rem == 1 logical px, is
// 360 x 55 -- the per-caption .mp-bd strips are the visible extremes; .mp-backdrop is the invisible
// surface marker (left -80rem / top -22rem / 360 wide / 55 tall, MoEProgress.css; CLIP_B_REM == 8
// trims the surface bottom) and every caption, tick and glow sits inside it. So the surface is that box
// plus PAD_REM of slack on all four sides (the text-/box-shadow bleed reaches the box edge
// exactly), and the whole composition is rigidly translated by that much so NOTHING sits at a
// negative coordinate -- an origin overflow is clipped no matter how big the surface is.
//
// THE SIDE CLEARANCE IS 80rem AND IT IS NOT WIDTH-DERIVED: the box is the 200rem track (see
// #moe-bar-root's width note in the CSS) plus BOX_LEFT_REM on each side, so a track resize moves
// BOX_W_REM by exactly the same amount and every per-side margin is preserved.
// WHICH CAPTION IS THE EXTREME HAS NOW MOVED THREE TIMES, so all three extremes are RE-DERIVED here
// from the shipped CSS and MoEBattle.ttf's own advances (digit 0.4932em, comma 0.2471, paren 0.3008,
// plus 0.4932; 1rem == 1 logical px; every figure re-checked against the ttf's hmtx; the MoE-%
// caption adds percent 0.7734 and period 0.2471 -- see THE MoE-% CAPTION below). The two moves
// in THIS revision: the .mp-capL axis-floor caption is GONE outright, and the REMAINING-BATTLES
// COUNT moved OFF the delta and ONTO .mp-capR with a glyph of its own.
//   RIGHT -- .mp-capR, and it is now the extreme by a wide margin. ONE flex row, FOUR items --
//   plus a FIFTH term now, the ETA GAP (.mp-ico.battles's own margin-left, DOM order after the
//   requirement numeral and before the battles glyph -- it widens the row, not a box of its own):
//     3.00 (.mp-cap.side.mp-capR's margin-left off the track end)
//     + 17.00 (.mp-ico.mk / .mp-ico.moe) + 1.00 (.mp-cap .mp-ico's shared gap)
//     + 31.08 ("3,050", a 4-digit requirement, at the .side 14rem: 4*6.9048 + 3.4594)
//     + 4.00 (.mp-ico.battles's margin-left -- the ETA GAP, added to breathe the requirement
//       numeral apart from the remaining-battles count that follows it)
//     + 13.00 (.mp-ico.battles -- it takes .mp-ico's BASE box, the only glyph in the file that does)
//     + 1.00 (that same shared gap) + 13.81 ("99", the PROGRESS_ETA_CAP ceiling, 2*6.9048 at 14rem)
//     == 83.89rem of BOXES, + 1.00 for the numerals' dark-drop text-shadow radius == 84.89rem.
//     SO IT OVERHANGS THE 80rem BACKDROP CLEARANCE BY 4.89rem (UP FROM 0.89rem BEFORE THE GAP) --
//     and unlike before, that overhang is NO LONGER pure shadow halo. The final "99" numeral's own
//     box now spans 70.08 -> 83.89rem, i.e. 3.89rem of ITS BOX (not just its shadow) sits PAST the
//     80rem backdrop edge, on bare HUD. At the .side 14rem size one digit is 6.9048rem wide, so
//     3.89rem is a bit over half a digit -- WORST CASE IS ROUGHLY THE OUTER HALF OF THE LAST DIGIT
//     LOSING ITS DARK BACKING, and it only reaches that worst case when a 4-digit requirement
//     ("3,050"-shaped) and a 2-digit ETA ("99") land together. THIS IS A KNOWN, ACCEPTED TRADEOFF
//     OF THE 4rem GAP, not a bug to chase: do NOT fix it by moving the backdrop, changing
//     PROGRESS_ANCHOR_X_OFFSET, shrinking this gap, or re-deriving it away -- that is the
//     maintainer's call, not this file's.
//     DISTINGUISH OVERHANG FROM CLIPPING before reaching for the geometry -- the surface is a
//     further PAD_REM out at 90rem, so CLIPPING STARTS AT 90 and there is still 5.11rem of
//     clearance before that (90 - 84.89): nothing here is clipped, only unbacked.
//     REBALANCING THE BACKDROP IS NOT FREE AND WAS DELIBERATELY NOT DONE. Taking clearance off the
//     now-empty left side (80/80 -> e.g. 52/108, keeping BOX_W_REM and so the surface AND the mouse
//     hit rect) breaks the symmetry that lets positioning.anchor_centred's `max_x // 2` centre the
//     bar with NO X term in Python: constants.PROGRESS_ANCHOR_X_OFFSET is 0, and
//     tests/test_progress_surface_mirror.py::test_the_large_backdrop_stays_symmetric_about_the_track
//     pins exactly that. Any asymmetry slides the bar half the error sideways at every resolution
//     until that constant -- plus a Large twin for it, since it is logical px and the block's
//     x-lengths carry SIZE_XF -- follows. That is a positioning change, not a CSS one.
//   CENTRE (.mp-capC) RIGHT -- back down, now that the "/NN" suffix is off the delta:
//     17.76 (half of "3,050" at the .dn 16rem == 35.52) + 4.20 (.mp-d's 0.35em gap of its OWN 12rem
//     font) + 30.89 ("(+297)" at 12rem) + 6.00 (.mp-d-num's sign-glow text-shadow radius)
//     == 58.85rem, i.e. 21.15rem SPARE. That reproduces the pre-count figure exactly, as it must.
//     A 4-digit delta ("(+2,970)" == 39.78) still only reaches 67.74rem, and needs cd ~ 150,000.
//   LEFT -- .mp-capC at 0% is the ONLY candidate left, and its ICON path beats its numeral's glow:
//     17.76 (the same half-numeral) + 17.00 (.mp-capC .mp-ico's negative-margin overhang)
//     + 0.48 (that icon's ::before glow, 3% of its 16rem box) == 35.24rem, against the numeral's
//     own 17.76 + 6.00 == 23.76. So 35.24rem and 44.76rem SPARE: ~45rem of dead space out there.
//     (An earlier revision of this note SUMMED those two paths into 41.24rem. They are
//     ALTERNATIVES, not terms -- the 6rem is the numeral's own text-shadow and stops at -23.76.)
//   The .mp-full case is UNCHANGED and now provably so: battles_to_axis_hi returns 0 exactly when
//   proj_avg >= axis_hi, which is the same test .mp-full toggles on, so the count is suppressed on
//   every gold frame and needs no `#moe-bar-root.mp-full .mp-eta` rule of its own.
//   Large is NOT size-mode-agnostic (it needs its own sum, the x-length terms scale by SIZE_XF while
//   the boxes/numerals scale via the root font alone) but is still strictly slacker: the clearance
//   grows 80 -> 106.667rem, and the ETA GAP's own Large twin (.mp-ico.battles's margin-left, an
//   x-length like the shared gaps: 4 * 4/3 == 5.333) is the only new term --
//   capR' == 4 + 17 + 1.333 + 31.08 + 5.333 + 13 + 1.333 + 13.81 + 1 == 87.89rem, 18.78rem spare
//   (down from 24.1rem before the gap, since the gap only widens the reach and the backdrop grows
//   for a different reason). Still comfortably unclipped, so the Default size keeps binding on
//   every side.
//   THE MoE-% CAPTION. capC carries "(73.84%)" (.mp-pct), OUT OF FLOW at left:100% so the numeral
//   stays on its tick, with the delta re-parented INSIDE it so ITS left:100% resolves off the % box's
//   right edge. THE % IS THE DAMAGE NUMERAL'S SIZE (.mp-pct takes .mp-cap.dn's 16rem / 20.5rem, no Y
//   offset, so the caption's HEIGHT -- hence BOX_TOP/PAD/CLIP_B and the Y shift -- did not move).
//   CAPC RIGHT reach at axis 100 % ("(100.00%)" == 2*0.3008 + 5*0.4932 + period 0.2471 +
//   percent 0.7734 == 4.0881em == 65.41rem at the 16rem numeral size; "(73.84%)" is 57.52rem):
//     17.76 + 4.20 (gap, ABSOLUTE: .mp-pct-t's margin-left, the delta's own 0.35em of 12rem) + 65.41
//     + 4.20 (the delta's gap) + 30.89 ("(+297)" at the delta's own 12rem) + 6.00 == 128.46rem
//   against the clearance -BOX_LEFT_REM + PAD_REM == 120 + 10 == 130rem (1.54rem spare): the box grew
//   symmetrically 105 -> 120 / 410 -> 440 (remedy (i); was 80 -> 105 for the 12rem %). The
//   surface-mirror test's own sum is the authority
//   (test_the_horizontal_capc_percent_reach_at_axis_100_fits_the_surface). The 58.85rem above is the
//   PRE-% figure -- do not trust it while the % shows. .mp-bd-2 (capC's strip, centred on the tick)
//   stays 150 (grown 108 -> 150 for the 12rem %): at the 16rem % the +-75 strip no longer fully backs
//   the rare 100.00% gold state (87.37 == 17.76 + 4.20 + 65.41) -- accepted, it overhangs by a few rem.
// Keep the 80rem, and re-derive ALL THREE extremes again before ever moving it -- "which one is the
// extreme" has now moved three times, and each move invalidated the previous revision's spare.
// These five ARE this bar's surface contract and stay HERE, per bar. MoEBarTransient derives the
// rest from them (its box*/pad arguments), exactly as this file used to:
//   VIEW_W_REM = BOX_W_REM + 2 * PAD_REM == 460     SHIFT_X_REM = PAD_REM - BOX_LEFT_REM == 130
//   VIEW_H_REM = BOX_H_REM + 2*PAD_REM - CLIP_B_REM == 67   SHIFT_Y_REM = PAD_REM - BOX_TOP_REM == 32
// SHIFT_Y_REM is MIRRORED (negated) in Python as
// domain/constants.PROGRESS_ANCHOR_Y_SHIFT, so changing BOX_TOP_REM or PAD_REM moves the bar on
// screen until that constant follows -- and #moe-bar-box in MoEProgress.css is sized to the derived
// surface, a THIRD copy: keep all three in lockstep. The hit padding and the re-assert timing live
// in the shared module (its HIT_MAGIC / SURFACE_REASSERT_MS -- both LOAD-BEARING, read its header).
// SEED (FIRST CUT, box re-cut for edge-drag): now the whole-bar backdrop is gone the surface is
// re-derived from the ACTUAL visible composition (track + captions + per-caption .mp-bd shadow
// strips), NOT the old backdrop rect. The long prose ABOVE predates this re-cut and describes the
// old 360x72 numbers -- treat the four consts below as the source of truth, tune in the browser.
// HEIGHT (iter 3): FIX A restored capC's OWN strip (.mp-bd-2) to a taller 26rem re-centred on the
// numeral (the shared 16rem left it too thin); the mark strips (.mp-bd-1 capP / .mp-bd-3 capR) stay
// at 16. Topmost is .mp-bd-1's top (capP, -22); bottommost is now capC's taller strip bottom
// (top 7 + 26 == 33). BOX_TOP -22 .. BOX bottom 33 == 55 tall.
// FIX B (reach the bottom screen edge): PAD_REM stays 10 -- the RIGHT side genuinely needs it (capR's
// ETA sign-glow reaches ~90rem past the track end, and the surface must stay SYMMETRIC about the
// track for anchor_centred_reduced, so padX==padXR==10), and the TOP does no harm at 10. Instead the
// BOTTOM alone is trimmed by CLIP_B_REM (the shared module's clipB: viewH = boxH + 2*PAD - clipB),
// which shortens the surface's bottom WITHOUT moving the composition (clipB never enters shiftY), so
// the mirrored Python Y-shift is unchanged. Bottom pad becomes PAD_REM - CLIP_B_REM == 2rem: capC's
// numeral sign-glow (~6rem past its ink) lands at ~31.7 == INSIDE box bottom 33, and the strip box
// (33) sits 2rem inside the surface -- nothing clips.
// WIDTH is -120/440: symmetric, now bound by the capC "(100.00%)" reach (see THE MoE-% CAPTION above;
// it was -80/360, capR-overhang-bound). .mp-bd-3 was pulled in from 126->88 (iter 1) so it no longer
// clips the surface edge.
const BOX_LEFT_REM = -120;                           // leftmost edge (== -clearance; symmetric)
const BOX_TOP_REM = -22;                             // topmost edge (.mp-bd-1's top)
const BOX_W_REM = 440;                               // track 200 + 2*120 clearance (symmetric)
const BOX_H_REM = 55;                                // seed: bounds the strips (capC strip now 26 tall)  [was 50]
const PAD_REM = 10;
// BOTTOM-only surface trim (iter 3). Effective bottom pad == PAD_REM - CLIP_B_REM == 2rem. Y-length,
// scales with SIZE_F in applySize; never enters shiftY, so the domain Y-shift constants are unchanged.
const CLIP_B_REM = 8;

// --- THE VERTICAL ORIENTATION (mod_settings.progress_bar_orientation, pushed as the VM's
// `vertical`) ------------------------------------------------------------------------------------
// A SECOND COMPOSITION IN THE SAME DOCUMENT, not a restyle of this one: its own stylesheet
// (MoEProgressVertical.css, <link>ed alongside MoEProgress.css from MoEProgressView.html), its own
// namespace-disjoint class prefix (.mpv-*), its own DOM order (numeral BEFORE icon) and its own
// surface. NO second registered layout and NO second BarHost: orientation is a MOUNT-TIME branch.
//
// V_BOX_* IS .mpv-backdrop, exactly as BOX_* above is .mp-backdrop -- and it is the axis-swap of it
// with the tuner's own tuned lengths, NOT a transpose of these four (46 wide against 360 tall, vs
// 360 x 72; the side clearance is 34 a side, not 80, because a vertical bar's captions grow along
// its cross axis and the tuned overhang differs, and the RIGHT edge is trimmed -- see V_BOX_W_REM's
// own note below). PAD_REM serves the Y axis; the X axis is a SPLIT pad, V_PAD_X_REM on the left
// (caption ink) and V_PAD_XR_REM on the right (the track's own tick overhang, deliberately smaller
// -- see both constants' own notes below), so:
//   V_VIEW_W_REM = V_BOX_W_REM                   V_SHIFT_X_REM = V_PAD_X_REM - V_BOX_LEFT_REM == 167
//               + V_PAD_X_REM + V_PAD_XR_REM == 182
//   V_VIEW_H_REM = V_BOX_H_REM + 2 * PAD_REM
//                                - V_CLIP_B_REM == 320 V_SHIFT_Y_REM = PAD_REM - V_BOX_TOP_REM  == 90
// V_SHIFT_Y_REM is MIRRORED (negated) in Python as domain/constants.VERTICAL_ANCHOR_Y_SHIFT (-90,
// and -113 for Large == -round(90 * SIZE_F)), which is SHARED with the Damage Efficiency bar --
// unlike the horizontal pair's 44-vs-50 split, both vertical compositions have the identical
// backdrop top and height. #moe-bar-box in MoEProgressVertical.css is sized to the derived surface,
// a THIRD copy: keep all three in lockstep.
//
// THE SURFACE IS THE ONLY SIDE THAT IS NOT box + PAD_REM, AND THAT IS THE WHOLE POINT (V_CLIP_B_REM).
// The engine clamps EVERY window into [0, space - surface] in compiled C++ (movePyWindow -- memory
// `engine-clamps-every-wulf-window-to-screen-and-the-mod-depends-on-it`; bar_window._extent's
// far-sentinel calibration DEPENDS on that clamp existing), so the surface's bottom edge can never go
// below the screen's, and a bar anchored to the minimap therefore lands however far its TRACK sits
// above its own surface bottom -- never closer. At a full box + PAD_REM surface that was
// 380 - 290 == 90 logical px, against the vertical tuner's tuned `mmGapBottom` of 30
// (tools/dev/gen_bar_tuner_vertical.ps1:451), i.e. the tuned look was unreachable by ~60px and
// domain/constants.PROGRESS_MM_GAP_BOTTOM could not be honoured at all.
// THE SURFACE DOES NOT HAVE TO CONTAIN THE BACKDROP -- only the caption INK. The tuner's stage clips
// the backdrop's lower bleed at exactly this gap and that IS the approved appearance, so the surface
// is shortened to the tuned gap and the bleed clips at its bottom edge:
//   V_CLIP_B_REM == (V_BOX_H_REM + 2*PAD_REM) - (V_SHIFT_Y_REM + barLen + mmGapBottom)
//                == 380 - (90 + 200 + 30) == 60
// and the surface's below-the-track slack becomes 320 - 290 == 30 == the tuned gap exactly (290 is
// V_SHIFT_Y_REM + barLen == domain/constants.MM_TRACK_Y, which this does NOT move -- see below).
// WHAT IT COSTS, DERIVED FROM THE SHIPPED CSS, is 3rem of clearance on the bottom caption's ink and
// nothing else. .mpv-capC (MoEProgressVertical.css) is `top: 100%` + `margin-top: 6rem` off the
// track's bottom end, its flex row is `line-height: 20.5rem` tall (the tallest of its three children:
// the 20.5 numeral line box beats the 16rem .dmgc icon and the 15.5rem delta), so its box ends
// 6 + 20.5 == 26.5rem below the track; the numeral's own translateY(-0.5rem) plus its 1rem dark-drop
// text-shadow radius reaches 27.0, the delta's translateY(1.5rem) + the same 1rem reaches 25.5, and
// the icon's translate(0, 1rem) + its ::before 106% glow (3% of 16rem) reaches 26.2. So the deepest
// ink is 27.0 against 30 of slack. The ONLY thing past the edge is the sign-glow's soft tail (the
// 6rem blur on .mpv-d-num / .mpv-v in the up/down states, reaching ~32.5) -- which the tuner clips
// at its stage bottom too, at the same 30, which is what the maintainer approved.
// IT MOVES NOTHING ELSE, BY CONSTRUCTION: the clip is applied to the SURFACE only and never to
// shiftY, so the composition sits exactly where it did inside the surface and BOTH mirrored Python
// constants -- VERTICAL_ANCHOR_Y_SHIFT (-90) and MM_TRACK_Y (290) -- are unchanged. Nothing reflows
// either: every length in the two vertical stylesheets is a rem or a % of a rem-sized ancestor (the
// only viewport-relative rule in either document is `body { margin: 0 }`), so a shorter surface can
// only clip, never re-lay-out.
// UNDER LARGE the clip is inside applySize's `* f`, so the slack is 400 - 363 == 37 logical px while
// PROGRESS_MM_GAP_BOTTOM stays a fixed 30: the gap is then UNREACHABLE and the engine flushes the
// surface to the screen bottom, which lands the track at 30 * SIZE_F == 37.5 -> 37. That is the
// tuned gap SCALED, i.e. the same look 1.25x, which is exactly right -- do NOT "fix" it with a
// MM_GAP_BOTTOM_LARGE twin, and do NOT take the clip out of the `* f` to force reachability: a
// fixed-px clip would keep biting the same 60rem out of a composition whose ink grew 1.25x, and the
// bottom caption would start clipping for real.
// THE 256x256 SIZE-TIMEOUT FALLBACK STILL RUNS LAST AND STILL WINS on this path -- the vertical
// surface is pushed and RE-ASSERTED after the deadline by exactly the same shared machinery
// (MoEBarTransient's SURFACE_REASSERT_MS), and each push round-trips back to Python as
// onSizeChanged -> bar_window._place, which is what makes the placement agree with the surface.
//
// ...AND THE X AXIS IS NOT box + PAD_REM EITHER (V_PAD_X_REM). The three captions are
// RIGHT-ANCHORED and grow LEFTWARD from a fixed edge (`right: 100%; left: auto`,
// MoEProgressVertical.css's .mpv-cap), so their ink runs well past .mpv-backdrop's left edge --
// and unlike the horizontal bar, THE BACKDROP IS NOT MEANT TO COVER THEM (maintainer's call: the
// look is settled, the backdrop stays exactly where the tuner put it). At the shipped
// PAD_REM the surface's left edge sat at -44rem and CUT TWO OF THE THREE ROWS. So the X slack is
// decoupled from the backdrop rect: V_PAD_X_REM widens the SURFACE alone, .mpv-backdrop's
// `left: -34rem; width: 72rem` is untouched, and nothing on screen moves but the clip.
//
// IT IS APPLIED TO BOTH SIDES EVEN THOUGH ONLY THE LEFT NEEDS IT, and that is the load-bearing
// half. Only the LEFT reach is a real requirement -- the right side has ~48rem of dead space at
// PAD_REM already -- but a LEFT-ONLY pad makes the surface asymmetric about the track, and the
// centred (Damage Log) alignment is `max_x // 2` with NO x term in Python
// (positioning.anchor_centred_reduced), i.e. it centres the SURFACE and only centres the BAR while
// the two are concentric. Left-only would have slid that alignment 26 logical px right at Default
// and 33 at Large -- a visible move, for a fix whose whole brief was "nothing on screen may look
// different except that the caption text is no longer cut off". Symmetric costs 53rem of surface
// on a side nobody looks at and is FREE: the surface rect is never drawn, the mouse hit rect is
// collapsed PER AXIS (MoEBarTransient's pushHitArea pads X by half the surface WIDTH and Y by half
// the surface HEIGHT), so widening padX only grows the X pad by exactly the same amount it grows
// viewW by -- the X axis still collapses to zero width either way, and the Y axis (which this
// widening never touches) is untouched. The input rect does not move. Do NOT "reclaim" the right
// side.
// THE WORST-CASE REACH, RE-DERIVED for the row split with Job 2's icon BOXES reverted (maintainer:
// "icon sizes must stay the same, adjust paddings individually" -- dmgp/mk/moe are back at their
// pre-039a58c 14/17/17rem, only per-icon margin-left differs from the shared 1rem now; see
// MoEProgressVertical.css's own notes), from the shipped CSS and MoEBattle.ttf's own advances
// (digit 0.4932em, comma 0.2471, paren 0.3008, sign 0.4932 -- the same figures the horizontal
// extremes above use). Each row's ink starts at `-padding-right + translateX` off the track's left
// edge and grows leftward; the design is digit-count INVARIANT at the anchor (see the CSS's own
// note), so a static worst case is sound:
//   .mpv-capC (bottom) IS STILL THE EXTREME, and MORE so now: the maintainer's own "move the
//     bottom block left 7px" nudge shrank its translateX from 16 to 9, moving the anchor 7rem
//     CLOSER to the surface's left edge (mind the clip -- every one of these captions is
//     right-anchored, so "left" is the OVERFLOW direction). .mpv-ico.dmgc still keeps its base
//     1rem margin ("the reference"), and this is still budgeted for the 4-DIGIT delta case, not
//     the 3-digit one:
//     (-6 + 9) - [ 39.78 ("(+2,970)" at the .mpv-d 12rem) + 4.20 (its 0.35em gap of that same
//     12rem) + 35.52 ("3,050" at 16rem) + 1.00 (the shared icon gap) + 16.00 (.mpv-ico.dmgc) ]
//     - 6.00 (.mpv-d-num's up/down sign GLOW, the widest text-shadow in the file) == -99.49rem
//     (was -92.49 before the nudge -- exactly +7, the same device-px count the translateX lost).
//     A 3-digit delta ("(+297)" == 30.89) reaches only -90.61.
//   .mpv-capR (now JUST the requirement group -- the eta group moved to its own row below): the
//     mark icon's own margin correction (-1.25rem) makes IT the shorter reach; the icon that
//     actually binds is .moe (the achievement glyph that REPLACES .mk once 3 marks are earned),
//     whose margin correction (+0.885rem) is now the LARGER combined offset -- the two are no
//     longer interchangeable the way they were pre-039a58c (same box, same shared margin, same
//     18-total either way):
//     mk:  (-6 + 14) - [ 31.08 ("3,050" at 14rem) + (-1.25) + 17 (.mpv-ico.mk) ] - 1.00 == -39.83
//     moe: (-6 + 14) - [ 31.08 + 0.885 + 17 (.mpv-ico.moe) ] - 1.00 == -41.97rem (the WORSE case)
//   .mpv-capEta (stacked above capR): (-6 + 14) - [ 13.81 ("99" at 14rem, the PROGRESS_ETA_CAP
//     ceiling) + 1.038 (.mpv-ico.battles's own margin correction, not the shared 1rem) + 13
//     (.mpv-ico's base box, the battles glyph) ] - 1.00 == -20.85rem -- still the SLACKEST row in
//     the file by a wide margin.
//   .mpv-capP (moving, dmgp back at 14rem, margin corrected to 1.253rem): (-6 + 0) -
//     [ 31.08 + 1.253 + 14 (.mpv-ico.dmgp) ] - 1.00 == -53.33rem.
// THE MoE-% CAPTION: V_MARKUP puts an in-flow .mpv-pct "(73.84%)" between the delta and the
//   numeral, so capC's leftward reach GROWS by that node + one gap: + 65.41 ("(100.00%)" at the
//   NUMERAL'S 16rem -- the % matches the damage numeral's size, same 20.5rem line box, same -0.5rem
//   Y nudge, so the row's height did not move: 2 parens + 5 digits + period 0.2471 + percent 0.7734
//   == 4.0881em) + 4.2 (the gap, ABSOLUTE 4.2rem, the delta's own 0.35em of 12rem). The 99.49 above
//   is the PRE-% figure. THE TEST IS THE AUTHORITY for the new one (it reads every term off the CSS,
//   incl. the row's padding-right/translateX): test_the_vertical_captions_fit_inside_the_surface
//   measures .mpv-capC at 162.10rem, and wants >= 4rem spare, so the allowance had to reach 166.10:
//   V_PAD_X_REM == 167 + V_BOX_LEFT_REM == 167 - 34 == 133   (was 116 at the 12rem %; +17 -> allowance
//   167, 4.90 spare)
// capC is STILL the extreme (162.10 > 53.33 > 41.97 > 20.85), and the maintainer's own 7px-left
// nudge ate the margin earlier (104 - 99.49 == 4.51, was 97 - 92.49 == 4.51 before -- the SAME margin,
// because V_PAD_X_REM grew by the identical +7): the surface's left edge had to move WITH it:
//   (earlier pass: V_PAD_X_REM == 104 + V_BOX_LEFT_REM == 104 - 34 == 70, was 63; +7)
// GROWING THIS MOVES THE TRACK INSIDE THE SURFACE, so domain/constants.PROGRESS_MM_TRACK_X(
// _LARGE) had to grow with it by the exact same amount (in logical px, i.e. *SIZE_F under Large)
// or the visible bar would slide RIGHT into the minimap -- see that constant's own comment.
// tests/test_progress_surface_mirror.py::test_the_vertical_captions_fit_inside_the_surface is the
// GATE on all of the above -- it re-derives every row from the stylesheet and the advances rather
// than trusting this note, and goes red the moment V_PAD_X_REM is trimmed. Splitting capR into
// capR + capEta means the test's `rows` dict owes a matching split, or it silently keeps checking
// the STALE (pre-split) shape and goes green over a layout it no longer describes.
//
// THE Y-AXIS FIT FOR THE NEW STACKED ROW (Job 1's own re-derivation obligation -- the maintainer's
// estimate of "~56rem of headroom" was explicitly flagged as unverified and is checked here
// instead of trusted). Measuring DOWN from the track's own top edge (y=0, the same origin
// V_BOX_TOP_REM uses): .mpv-capR's own box reaches capR's padding-bottom(6) + line-height(18) ==
// 24rem above the track top. .mpv-capEta stacks on top of THAT via its own
// `padding-bottom: 30rem` (== capR's 24rem box + a 6rem visual gap, the same magnitude this file
// already uses to clear the track), so capEta's box reaches 30 + 18(its own line-height) == 48rem
// above the track top. Add the row's own translateY nudge (-0.5rem, capEta's numeral) and the
// widest text-shadow in the file (the up/down sign glow, 6rem) for the worst-case ink, exactly as
// the X-fit test's own `halo` term does: 48 + 0.5 + 6 == 54.5rem.
// THE SURFACE'S OWN TOP CLEARANCE is -V_BOX_TOP_REM + PAD_REM == 80 + 10 == 90rem (the backdrop's
// own top bleed plus the uniform Y pad -- V_CLIP_B_REM only shortens the BOTTOM, never the top).
// 90 - 54.5 == 35.5rem of spare: the new row fits comfortably inside the EXISTING backdrop/surface
// with room to spare, so NEITHER V_BOX_TOP_REM/V_BOX_H_REM NOR VERTICAL_ANCHOR_Y_SHIFT (shared with
// the vertical Damage Efficiency bar) had to move for this change -- exactly what Job 1 asked to
// confirm before touching either. tests/test_progress_surface_mirror.py carries the matching gate,
// re-deriving both sides from source rather than hardcoding 54.5 and 90 as two literals that would
// have to agree by hand.
// LARGE IS STRICTLY SLACKER and needs no twin: the allowance is `V_PAD_X_REM - V_BOX_LEFT_REM*4/3`
// == 178.33rem (was 161.33 at V_PAD_X_REM 116, 115.33 at 70, 108.33 at 63 -- the backdrop's left bleed is an
// x-length and takes SIZE_XF; V_PAD_X_REM, like PAD_REM, does NOT -- the ink it covers is
// rem-sized and rides the root font's SIZE_F alone), while the ink only grows on its three
// x-GAPS. The Default size keeps binding.
// THE MINIMAP ANCHOR MUST FOLLOW THIS CONSTANT. domain/constants.PROGRESS_MM_TRACK_X's PURE
// derivation is `V_SHIFT_X_REM + trackW`, i.e. where the track sits inside the surface -- widen
// the left slack without growing it and the whole bar slides left by the difference. The shipped
// constant also carries a further -2 measured hand-placement correction on top; see its
// derivation there.
//
// FOUR DURABLE FACTS, established by reading the source rather than assuming (a maintainer once
// saw the minimap's first column "covered by a dark panel" and the fix took four rounds to land):
//   1. THE BACKDROP IS NOT MEANT TO COVER THE RIGHT-ANCHORED CAPTIONS -- only V_PAD_X_REM (above)
//      was ever sized for their ink. .mpv-backdrop is a SEPARATE rectangle, drawn for the
//      shadow/glow bleed around the TRACK, and every one of capR/capEta/capP/capC already reaches
//      far past it by design (see the worst-case reach note above -- 20.85 to 99.49rem, against a
//      34rem backdrop bleed). Do not "fix" a clip by widening the backdrop; that is V_PAD_X_REM's
//      job, on the SURFACE, which is never drawn.
//   2. THE VERTICAL BAR'S BACKDROP HAS NO SYMMETRY CONTRACT. `test_the_large_backdrop_stays_
//      symmetric_about_the_track` (tests/test_progress_surface_mirror.py) asserts symmetry ONLY
//      for the HORIZONTAL bar's `.mp-backdrop`, because `anchor_centred_reduced`'s `max_x // 2` has
//      no X term and only centres the BAR by centring the SURFACE -- true for the Damage Log
//      (horizontal) anchor. Fixed+Vertical resolves through `anchor_minimap` instead
//      (bar_window._resolve), whose `x = space_x - mm_size - gap - overhang - edge_x` reads
//      `edge_x` (PROGRESS_MM_TRACK_X) and NOTHING about the backdrop's own width or left. Trimming
//      `.mpv-backdrop` asymmetrically (this file's own V_BOX_W_REM, leaving V_BOX_LEFT_REM alone)
//      moves nothing the placement math depends on.
//   3. THE BACKDROP TRIM (V_BOX_W_REM 72 -> 46) WAS REAL WORK -- KEEP IT. A maintainer report of
//      the backdrop "sitting well clear of the minimap" turned out to describe a DIFFERENT panel;
//      measured live (window pos (1294,760), minimap index 4 == 510px wide at 1920x1080 logical
//      space), THIS backdrop's own right edge (V_PAD_X_REM + V_BOX_W_REM == 70+46==116) landed
//      EXACTLY on the minimap's own left edge (PROGRESS_MM_TRACK_X + MM_GAP + MM_TICK_OVERHANG ==
//      105+8+3==116) -- zero overlap, by design, at the tuned 46, AT THE TIME (the shared MM_GAP
//      was 8). Reverting to 72 (right edge 142) would reopen a real 26rem overlap. Do not touch
//      V_BOX_W_REM again without a live measurement to justify it.
//      SINCE THEN, PLACEMENT MOVED CLOSER TO THE MINIMAP (domain/constants.PROGRESS_MM_GAP(_LARGE),
//      5/6, replacing the shared MM_GAP(8) for this bar's own anchor) -- the backdrop's own DRAWN
//      right edge no longer sits flush with the minimap's own (now closer) left edge, it is a few
//      rem PAST it. That is not a regression: fact 4 below already established the DRAWN backdrop
//      is not what clears the minimap, the invisible SURFACE is (V_PAD_XR_REM/_LARGE), and the
//      surface still clears it with a real, checked margin at the new gap -- see V_PAD_XR_REM's own
//      derivation below for the current numbers.
//   4. THE ACTUAL CULPRIT WAS THE INVISIBLE SURFACE'S OWN RIGHT PAD, NEVER UPDATED TO MATCH. The
//      backdrop trim shrank the DRAWN rect; nothing shrank the SURFACE (the mouse-hit-blocking rect
//      per this file's header) on that side, so it stayed the OLD symmetric V_PAD_X_REM(70) past
//      the ALREADY-TRIMMED backdrop -- measured live: window size (186,320) == 46+70+70, its right
//      edge 70 logical px INSIDE the minimap (space_x - mm_size == 1410; window right == 1294+186==
//      1480). See MoEBarTransient.js's `padXR`/`padXRLarge` arg notes for the fix (a SEPARATE,
//      smaller right pad, V_PAD_XR_REM/_LARGE below) and V_PAD_XR_REM's own derivation. Because the
//      fix only shrinks the RIGHT pad and V_PAD_X_REM (the LEFT side, where the caption ink and the
//      track itself both live) is untouched, `shiftX` and therefore PROGRESS_MM_TRACK_X(_LARGE) --
//      both pure functions of the LEFT side alone -- need no correction, and the bar does not move
//      on screen (confirmed live: the measured window position matches anchor_minimap bit-exactly
//      already, before this pad fix, and stays that way after it).
//   5. PROGRESS_MM_TRACK_X CARRIES A -2 HAND CORRECTION (see its own derivation in domain/
//      constants.py) THAT MUST NOT LEAK INTO THIS FILE'S OWN SURFACE-WIDTH MATH. That correction
//      exists ONLY to match a measured discrepancy in where the WINDOW lands in SPACE (two
//      independent Ctrl-drags); it shifts the whole window (surface + everything drawn inside it)
//      by a constant 2px, and does NOT change where the TICK renders inside its OWN surface -- that
//      is a pure JS/CSS fact (shiftX + trackW), unrelated to any Python-side placement fudge. Using
//      the CORRECTED constant (105) as if it were this bar's own local tick position (as an earlier
//      pass of this fix did) UNDERSTATES the tick's real reach by exactly that 2px and clips it --
//      the true local tick-right is shiftX(104) + trackW(3) + MM_TICK_OVERHANG(3) == 110, not 108.
//      See V_PAD_XR_REM's own derivation below, which uses the PURE (uncorrected) value throughout.
const V_BOX_LEFT_REM = -34;                          // .mpv-backdrop's left
const V_BOX_TOP_REM = -80;                           // .mpv-backdrop's top
const V_BOX_W_REM = 46;                              // .mpv-backdrop's width (right edge only, trimmed -- see fact 3)
const V_BOX_H_REM = 360;                             // .mpv-backdrop's height
const V_CLIP_B_REM = 60;                             // backdrop bleed the SURFACE clips off the bottom
const V_PAD_X_REM = 133;                             // the LEFT X slack, decoupled from the backdrop
// THE SURFACE'S RIGHT (minimap-facing) PAD -- deliberately NOT V_PAD_X_REM's mirror, and a SEPARATE
// knob from the backdrop's own V_BOX_W_REM trim above: the backdrop trim shrinks what is DRAWN, this
// shrinks what is CLICK-BLOCKING (the surface, never drawn). Shrunk close to the minimum the TRACK's
// own ink needs on that side: the tick's cross-axis overhang past its own edge
// (domain/constants.MM_TICK_OVERHANG(_LARGE), the SAME term anchor_minimap's `x` formula already
// adds as clearance), plus a small, deliberate MARGIN (+2 logical/document px, flat, NOT xf-scaled
// -- see fact 5: this is a JS-local geometry decision, so it uses the PURE tick position, never
// PROGRESS_MM_TRACK_X's hand-corrected placement value) so the surface's own edge is never flush
// with the tick's -- a flush boundary is exactly the "rounding could shave a px and eat the ink"
// risk fact 5 exists to head off. Nothing for caption ink is needed on this side at all -- every
// caption here is anchored to the LEFT (see V_PAD_X_REM's own note), so the right side backs nothing
// but the (already-trimmed) backdrop's own remaining decorative bleed, which this pad now clips a
// little further, at the surface edge, rather than containing it (the same clip-not-contain pattern
// V_CLIP_B_REM already uses on the bottom).
// Solved directly against MoEBarTransient.applySize's own formula
// (viewW == round((boxW*xf + padX + padXR) * f)), using the PURE (uncorrected) tick position:
//   tick-right (Default, xf=f=1) == shiftX(104) + trackW(3) + MM_TICK_OVERHANG(3) == 110
//   Default:  viewW == 110 + 2 (margin) == 112  ->  padXR == 112 - V_BOX_W_REM(46) - V_PAD_X_REM(70) == -4
//   tick-right (Large, PRE-SIZE_F) == shiftX_pre_f(346/3) + trackW_large(4) + overhang_large_pre_f(4)
//                                  == 370/3 ~= 123.333 (renders at 123.333*SIZE_F ~= 154.167 device px)
//   Large:    viewW_pre_f == 370/3 + 2 == 376/3 ~= 125.333  ->  round(125.333 * SIZE_F) == 157
//     padXRLarge == 376/3 - boxW*xf(184/3) - V_PAD_X_REM(70) == -18/3 == -6 (exact)
// Both NEGATIVE: the surface's right edge sits a LITTLE further inside the backdrop's own (already
// trimmed) drawn rect than its own edge -- the box+left-pad sum (46+70==116 Default, 61.333+70==
// 131.333 pre-SIZE_F Large) was flush with the minimap at the ORIGINAL shared MM_GAP(8) (fact 3),
// so ANY margin (to the tick, or to the minimap) needed the surface a shade smaller still. This
// derivation (padXR/padXRLarge themselves) is UNCHANGED by the later gap move -- it is pure
// JS/CSS geometry, independent of where Python decides to place the window -- but the MARGIN it
// buys against the minimap moved WITH that gap. Resulting margins, both real and checked
// (tests/test_progress_surface_mirror.py::test_the_surface_clears_the_minimap_at_every_size_index
// / test_the_surface_does_not_clip_the_tick), at domain/constants.PROGRESS_MM_GAP(_LARGE) == 5/6:
// Default clears the minimap by 1px (was 4px at the original shared gap of 8) and the tick by
// 2px; Large by 1px (was 3px) and ~2.8px respectively -- none of it flush, none of it negative.
// padXRLarge is NOT padXR*SIZE_XF, for the same reason MM_TRACK_X_LARGE and MM_TICK_OVERHANG_LARGE
// are their own literals: the Large geometry (trackW_large, shiftX_large) is not a pure *SIZE_XF
// scale of the Default one once V_BOX_LEFT_REM's own fractional Large scaling is folded in, so
// neither is what clears it -- see the derivation above, computed directly, not scaled.
// GROWN (2026-08-10, in-client review) so the surface still reaches the minimap's 1px floor after
// the placement gap was RESTORED to 8 (domain/constants.PROGRESS_MM_GAP(_LARGE)). Solved directly
// against anchor_minimap's margin (== gap + overhang + edge_x - view_w). ADVANCED 4 logical px into
// the minimap (2026-08-12, in-client): the previous margin==1 cleared the minimap's DROP-SHADOW by
// 1px but left the backdrop 4px off the minimap's REAL visible edge -- the maintainer confirmed that
// 4px is the minimap's non-interactive frame margin and is safe to consume (the Ctrl-click area is
// further in). So the surface's right edge (and the flush strips) now sit at margin == -3 (3px into
// that frame margin), flush against the minimap itself:
//   Default: view_w == 8 + 3 + 168 - (-3) == 182 -> padXR == 182 - V_BOX_W(46) - V_PAD_X(133) == 3
//   Large:   view_w == 8 + 5 + 226 - (-3) == 242 -> padXRLarge == 242/SIZE_F - boxW*xf(61.333) - 133
//                                             == 193.6 - 194.333 == -0.733
//   (MoE-% passes: V_PAD_X 70 -> 116 -> 133 and PROGRESS_MM_TRACK_X 105 -> 151 -> 168 / 147 -> 205 ->
//   226 moved together, so Default padXR is unchanged at 3; Large's drifts by the 228-vs-227.917
//   rounding of the pure value.)
// The visible TRACK is unaffected -- gap/overhang/edge_x are unchanged; only view_w (this right pad)
// grew, which moves the surface's minimap-facing edge alone, not the track.
const V_PAD_XR_REM = 3;                              // the RIGHT (minimap-facing) X slack, Default
const V_PAD_XR_REM_LARGE = -0.733;                   // ...and Large -- its OWN literal, see above

// THE LIVE ORIENTATION PROFILE -- the three things the render path cares about, all rewritten
// together by goVertical() below and never touched again.
//   PFX   the class prefix every selector and every toggled class in this file is written in. The
//         source spells everything as "mp-..." and ns() rewrites it, so the literals stay greppable.
//   AX    the property a marker's position is written to: `left` along a horizontal axis, `bottom`
//         along a vertical one (0% at the BOTTOM -- see the stylesheet's axis note).
//   GROW  the property the fill grows along: `width` vs `height`.
//   CAP_C_AX  the axis the BOTTOM-CENTRE caption tracks, or null if it does not move. On the
//         horizontal bar capC rides the proj tick; on the vertical one it is a STATIC cap below the
//         track's bottom end and capP (the pre caption) is the only caption that moves. That is the
//         tuner's tuned layout, not an omission -- see MoEProgressVertical.css's .mpv-capC.
let PFX = "mp";
let AX = "left";
let GROW = "width";
let CAP_C_AX = "left";

// Rewrite a class name or a selector from the source's .mp-* spelling into the LIVE prefix. A no-op
// while horizontal, so the shipped path costs one string compare per call and nothing else. The
// two prefixes are DISJOINT by design (see the vertical stylesheet's header), which is the whole
// reason a blanket token rewrite is safe here.
function ns(s) { return PFX === "mp" ? s : s.replace(/\bmp-/g, PFX + "-"); }

// THE HORIZONTAL COMPOSITION'S MARKUP (the vertical one is V_MARKUP below; ensureRoot builds this
// one and goVertical replaces it, which is why they are two constants and not one branch inside the
// builder). Markup shape is the tuner's stage: backdrop, the track with its
// four ticks, then THREE captions -- the tuner's fourth, .mp-capL, carried the axis FLOOR numeral
// and is gone (axisLo is the battle's starting projection, not a requirement, and the label said
// nothing the moving caption does not). Each caption is ONE flex row -- icon, value, and on capC the
// delta, whose PARENS are static text on the wrapper so they never glow (see the .mp-d / .mp-d-num
// split in the CSS). NO word labels anywhere: MoEBattle.ttf is a 19-glyph numeric subset
// (digits % ( ) + - , . / space) and a letter renders BLANK.
const MARKUP =
        // Per-caption dither strips (MoEProgress.css .mp-bd) -- one small box behind each caption,
        // z-index 0 at root so the captions (inside .mp-track's stacking context) paint over them.
        // capP/capC (.mp-bd-1/-2) are JS-tracked to their caption's `left`; capR (.mp-bd-3) is fixed.
        '<div class="mp-bd mp-bd-1"></div><div class="mp-bd mp-bd-2"></div>' +
        '<div class="mp-bd mp-bd-3"></div>' +
        '<div class="mp-track">' +
        '  <div class="mp-fill"></div>' +
        '  <div class="mp-tick mp-end mp-left"></div>' +
        '  <div class="mp-tick mp-pre"></div>' +
        '  <div class="mp-tick mp-proj"></div>' +
        '  <div class="mp-tick mp-end mp-right"></div>' +
        '  <div class="mp-cap up mp-capP"><i class="mp-ico dmgp"></i>' +
        '<span class="mp-v"></span></div>' +
        // THE MoE-% (.mp-pct) is OUT OF FLOW like the delta was, so the numeral alone stays on its
        // tick, and the DELTA IS RE-PARENTED INSIDE it so its own left:100% resolves off the %'s
        // right edge ("1,850 (73.84%) (+120)"). .mp-pct-t is the gated/faded text group: hiding THAT
        // (not .mp-pct) keeps the delta alive when the % is off. NOT .mp-v -- capV() is a first match.
        '  <div class="mp-cap dn mp-capC"><i class="mp-ico dmgc"></i><span class="mp-v"></span>' +
        '<span class="mp-pct"><span class="mp-pct-t">(<span class="mp-pct-num"></span>)</span>' +
        '<span class="mp-d">(<span class="mp-d-num"></span>)</span></span></div>' +
        // THE MARK PAIR MUST COME FIRST IN THIS ROW: capV() does a querySelector for the FIRST
        // .mp-v, so reordering these four nodes repoints the requirement writer at the count -- with
        // no error to catch it. The mark GLYPH no longer cares (setIco writes to the mount-cached
        // capMkIco, which the vertical composition's opposite order forced), but the numeral still
        // does. The requirement's glyph is the only one setIco ever rewrites; the battles glyph's
        // class is STATIC (paintStatic only toggles `none` on it), which is why it can safely share
        // the .mp-ico family here.
        '  <div class="mp-cap side mp-capR"><i class="mp-ico none"></i>' +
        '<span class="mp-v"></span><i class="mp-ico battles"></i>' +
        '<span class="mp-eta"></span></div>' +
        '</div>';

// ...and THE VERTICAL COMPOSITION'S markup, the tuner's own stage verbatim
// (tools/dev/gen_bar_tuner_vertical.ps1). FOUR structural differences from the horizontal template
// above, all of them the tuner's tuned layout and none of them free to "tidy":
//   * NUMERAL BEFORE ICON in every caption (the icon trails, away from the track). That is what
//     makes the shared right:100% anchor digit-count invariant -- the icon is the LAST in-flow
//     child, flush against a FIXED edge, so only the numeral grows, and leftward. Reversing it
//     re-introduces the exact defect that shipped once on the horizontal bar.
//   * the DELTA is ordered FIRST on capC (delta, numeral, icon), an in-flow flex child with a
//     margin gap -- never an out-of-flow box hanging off a content-dependent edge.
//   * capP lives INSIDE .mpv-track and capR / capC are its SIBLINGS, exactly as the tuner has them
//     (root and track are the same 3x200rem box, so every percentage resolves identically either
//     way; this only keeps the diff against the tuner readable).
//   * the two axis-end ticks are mpv-bottom / mpv-top, not mp-left / mp-right.
// capR is now TWO STACKED ROWS, not one (maintainer's call: "move the ETA on top of the next mark
// requirement"), ported here only -- the tuner's own stage keeps both numeral+icon groups on ONE
// row, untouched (see MoEProgressVertical.css's HAND-EDIT 6/6). `.mpv-capEta` (the eta numeral +
// battles glyph) sits directly ABOVE `.mpv-capR` (now JUST the requirement numeral + mark glyph),
// both anchored by the SAME right:100% mechanism (copied verbatim: same padding-right/transform/
// font-size/line-height) so both stay digit-count invariant independently. Because the mark icon
// is capR's ONLY icon now (no positional ambiguity to guard against any more, but the cache stays
// for the reason below), setIco() below still writes to a CACHED element captured at mount
// (capMkIco) rather than re-selecting a positional first match; capV()/capEtaIco/capEta stay
// class-filtered as they always were and do not care about which row they live in.
const V_MARKUP =
        '<div class="mpv-backdrop"></div>' +
        // Per-row dither strips (MoEProgressVertical.css .mpv-bd) -- one per number row, each flush
        // on the surface's minimap-facing edge. Positioned purely by CSS `top`; no JS drives them.
        '<div class="mpv-bd mpv-bd-1"></div><div class="mpv-bd mpv-bd-2"></div>' +
        '<div class="mpv-bd mpv-bd-3"></div><div class="mpv-bd mpv-bd-4"></div>' +
        '<div class="mpv-track">' +
        '  <div class="mpv-fill"></div>' +
        '  <div class="mpv-tick mpv-end mpv-bottom"></div>' +
        '  <div class="mpv-tick mpv-pre"></div>' +
        '  <div class="mpv-tick mpv-proj"></div>' +
        '  <div class="mpv-tick mpv-end mpv-top"></div>' +
        '  <div class="mpv-cap mpv-capP"><span class="mpv-v"></span>' +
        '<i class="mpv-ico dmgp"></i></div>' +
        '</div>' +
        '<div class="mpv-cap mpv-capEta"><span class="mpv-eta"></span><i class="mpv-ico battles"></i></div>' +
        '<div class="mpv-cap mpv-capR"><span class="mpv-v"></span><i class="mpv-ico none"></i></div>' +
        // The MoE-% sits IMMEDIATELY BEFORE the numeral (after the delta), in flow: "(+12) (73.84%) 1,850".
        // Never .mpv-v -- capV() is a first-match querySelector.
        '<div class="mpv-cap mpv-capC"><span class="mpv-d">(<span class="mpv-d-num"></span>)</span>' +
        '<span class="mpv-pct">(<span class="mpv-pct-num"></span>)</span>' +
        '<span class="mpv-v"></span><i class="mpv-ico dmgc"></i></div>';

function ensureRoot() {
    let root = document.getElementById("moe-bar-root");
    if (root) return root;
    root = document.createElement("div");
    root.id = "moe-bar-root";
    root.innerHTML = MARKUP;
    document.body.appendChild(root);
    return root;
}

const root = ensureRoot();
// `let`, not `const`, because goVertical() re-builds the root's contents under the .mpv- prefix and
// every one of these has to be re-queried against the new nodes. Under a single orientation nothing
// rewrites them.
let fill = root.querySelector(".mp-fill");
let tPre = root.querySelector(".mp-pre");
let tProj = root.querySelector(".mp-proj");
let capP = root.querySelector(".mp-capP");
let capC = root.querySelector(".mp-capC");
let capR = root.querySelector(".mp-capR");
// capP's backdrop strip (VERTICAL only) -- it must sit BEHIND capP, which rides the pre tick along
// the axis (capP.style.bottom is rewritten every render), so a fixed CSS `top` can't stay behind it.
// goVertical caches it and JS-tracks it to capP's own `bottom`; null (and untouched) horizontally.
let capBd3 = null;
// capP's / capC's per-caption dither strips (HORIZONTAL only): both ride the axis (their caption's
// `left` is rewritten every render), so JS tracks each strip's `left` to its caption's. Queried here
// against MARKUP; goVertical() nulls them (V_MARKUP has .mpv-bd strips of its own instead).
let capPbd = root.querySelector(".mp-bd-1");
let capCbd = root.querySelector(".mp-bd-2");
// The 0%/floor axis-end tick (VERTICAL only: .mpv-end.mpv-bottom). It marks "no progress" and must
// show ONLY while the current value is 0 -- once the bar has any fill it reads as clutter under the
// fill's own bottom edge. goVertical caches it; null (and untouched) horizontally, where the axis-end
// ticks are mp-left/mp-right and carry no such rule.
let tBottom = null;
let capD = capC.querySelector(".mp-d");
let capDN = capC.querySelector(".mp-d-num");
// The MoE-% group (the node gated on `pct >= 0` and faded with capD) and its digits. Horizontally the
// gated node is .mp-pct-t INSIDE the out-of-flow .mp-pct (which also holds the delta); vertically it
// is .mpv-pct itself.
let capPct = capC.querySelector(".mp-pct-t");
let capPctN = capC.querySelector(".mp-pct-num");
// The remaining-battles pair on capR. Its own classes, NOT a second .mp-v / an .mp-ico index: see the
// mark-pair-comes-first note on the template above (horizontal only -- the vertical capR swaps the
// two groups; see V_MARKUP and capMkIco below).
let capEtaIco = capR.querySelector(".mp-ico.battles");
let capEta = capR.querySelector(".mp-eta");
// The ETA row's decorative backdrop strip -- null (and untouched) horizontally, where there are no
// .mpv-bd-* strips at all. Gated the same as capEtaIco/capEta below (see goVertical/paintStatic).
let capEtaBd = null;
// ...and the MARK glyph, the one icon setIco() ever rewrites -- CAPTURED HERE, ONCE, exactly like
// capEtaIco, because it is the only addressing that survives BOTH the two compositions' opposite DOM
// orders AND setIco's own wholesale className reassignment (which drops any marker class the moment
// the first glyph lands). `.none` is its markup-literal state in BOTH templates and nothing else
// carries that class at mount -- paintStatic only ever toggles `none` onto the BATTLES glyph, later.
// A CLASS-FILTERING SELECTOR IS NOT AN OPTION HERE, and that is engine fact, not preference:
// Coherent Gameface's selector engine (win64/cohtml.WindowsDesktop.dll) implements exactly
// :hover :active :root :host :nth-child :first-child :last-child :only-child :focus ::part ::slotted
// ::selection -- there is NO :not, in the pseudo-class table or anywhere else in the binary, and
// WG's own shipped Gameface corpus (614 JS, 515 CSS) does not use one either. A
// `querySelector(".mp-ico:not(.battles)")` is an "Invalid CSS selector (...) in QuerySelector!",
// and the unguarded `.className` write on its result threw out of paintStatic and blanked the whole
// bar. Keep any new lookup to plain class / compound-class selectors.
let capMkIco = capR.querySelector(".mp-ico.none");

// ADOPT THE VERTICAL COMPOSITION -- the bar's half of MoEBarTransient's onVertical hook (the
// shared module owns the surface, the rigid shift, the run-identity pair and the body scope class).
// Called ONCE, inside engine.whenReady, BEFORE the surface push and before the first render, so
// nothing downstream ever sees the horizontal DOM. A mid-battle Orientation change re-mounts this
// document (Python closes and reopens the window -- battle_bridge.apply_settings), which comes
// straight back through here; there is deliberately no live re-composition path.
function goVertical() {
    PFX = "mpv";
    AX = "bottom";
    GROW = "height";
    CAP_C_AX = null;                 // capC is a STATIC bottom cap here -- see the profile note
    root.innerHTML = V_MARKUP;
    fill = root.querySelector(".mpv-fill");
    tPre = root.querySelector(".mpv-pre");
    tProj = root.querySelector(".mpv-proj");
    capP = root.querySelector(".mpv-capP");
    // capP's strip: anchor it the SAME way capP is (bottom:% + translateY(50%)) so JS can drive its
    // `bottom` to capP's own value each render and it stays centred behind the number at both sizes.
    capBd3 = root.querySelector(".mpv-bd-3");
    if (capBd3) { capBd3.style.top = "auto"; capBd3.style.transform = "translateY(50%)"; }
    capPbd = null;                   // horizontal-only strips; the vertical bar uses .mpv-bd instead
    capCbd = null;
    tBottom = root.querySelector(".mpv-bottom");
    capC = root.querySelector(".mpv-capC");
    capR = root.querySelector(".mpv-capR");
    capD = capC.querySelector(".mpv-d");
    capDN = capC.querySelector(".mpv-d-num");
    capPct = capC.querySelector(".mpv-pct");
    capPctN = capC.querySelector(".mpv-pct-num");
    // capEtaIco/capEta now live in the SEPARATE .mpv-capEta row (stacked above capR), not inside
    // capR itself -- scoped off `root`, since both classes are unique across the whole document.
    capEtaIco = root.querySelector(".mpv-ico.battles");
    capEta = root.querySelector(".mpv-eta");
    capEtaBd = root.querySelector(".mpv-bd-1");
    capMkIco = capR.querySelector(".mpv-ico.none");
}

function capV(c) { return c.querySelector(ns(".mp-v")); }

// The mark glyph for the NEXT-MARK caption: k in 1..3 -> mk<k>; k=4 (3 marks held, no higher mark
// to chase) -> the general MoE glyph; k=0 -> no icon at all (.none is display:none).
// IT WRITES TO THE CACHED capMkIco AND NEVER RE-SELECTS -- .mp-capR holds TWO .mp-ico nodes and the
// two compositions order them oppositely, so a per-call positional lookup would silently overwrite
// the BATTLES glyph's class on the vertical bar (dropping `battles` entirely -- this reassigns
// className wholesale). See capMkIco for why the filtering cannot be done in the selector.
// NULL-GUARDED, per this codebase's fail-soft rule: a missing glyph must cost the glyph, never the
// whole bar -- an unguarded deref here threw out of paintStatic and blanked the composition.
// The k=0 arm is unreached from paintStatic today -- its only caller passes marks+1 or 4 -- but it
// stays, because without it a stray 0 would write the nonexistent class "mk mk0" and blank the
// glyph silently instead of hiding it.
// CAP-LEVEL mk1/mk2/mk3, SEPARATELY FROM THE ICON'S OWN CLASS: .mp-capR's own margin-left (the
// block<->bar gap, CSS's "block-gap" knob) now varies per mark too, and unlike the icon there is
// no OTHER class on the caption to key a compound selector off, so capR gets its own copy of the
// same mk<k> marker. classList.toggle, not a wholesale className rewrite: capR carries its own
// "mp-cap side mp-capR" (horizontal) / "mpv-cap mpv-capR" (vertical) classes permanently and only
// the mark marker should move. Ungated by capMkIco's null-guard on purpose -- the caption's own
// classing must stay correct even on the rare tick capMkIco failed to resolve.
function setIco(k) {
    if (capR) {
        capR.classList.toggle("mk1", k === 1);
        capR.classList.toggle("mk2", k === 2);
        capR.classList.toggle("mk3", k === 3);
    }
    if (!capMkIco) return;
    capMkIco.className = ns("mp-ico") + (k === 0 ? " none" : k === 4 ? " moe" : " mk mk" + k);
}

// --- the pushed state ---------------------------------------------------------------------
// `cur` is the latest push; `last` is the previous one, and comparing the two IS the
// change-detect (there is deliberately no `rev` counter on ProgressVM -- the battle window is a
// private, always-compositing view and has never needed the garage's cold-mount signal).
// `last === null` means "no baseline yet": the FIRST push after mount (and after any re-show) is
// recorded silently so the bar does not appear at battle start.
let cur = { marks: 0, axisLo: 0, axisHi: 0, preAvg: 0, projAvg: 0, eta: -1 };
let last = null;

// This bar's OWN animation state, all of it about VALUES rather than the run: `swapped` = the bottom
// numeral currently shows proj_avg (not pre_avg); `swapT` is the pending swap timer -- ALWAYS
// cleared before starting anything, or an aborted run's swap fires into the new one. The run state
// itself (showing / peeking / the plateau clock / the surface settle) lives in the shared transient.
let swapped = true;
let swapT = null;

// PRE_AXIS_STOP_PCT -- the bar-width % the career pre-battle average (`preAvg`) is remapped onto.
// Same piecewise-linear equal-quarters trick MoECalculator.js's barX() spreads PCT_STOPS over
// BAR_STOPS with (and battle_builder.efficiency_bar_x mirrors again for the Damage Efficiency
// bar): there the stops are a fixed table; here they are per-battle [axisLo, preAvg, axisHi] --
// but preAvg is FIXED for the whole battle (the career average does not move mid-battle), so it
// is just as good a stop as any of barX's percentiles, and only `cd` (via projAvg) travels
// through the remap.
//
// WHY: at EWMA_K, the raw proportional share of the [axisLo, preAvg] segment is
// k*preAvg/(axisHi-axisLo) -- ~1.42% for a realistic tank, indistinguishable from the width of
// the preAvg tick itself, so the pre/cur markers overlap at battle start and the bar barely moves
// early. A .mp-tick is 2rem wide with a `0 0 6rem` glow, ~14rem of footprint on the 200rem track
// (~7%), so 8% is the smallest slice that clears the glow overlap. Tune by eye.
const PRE_AXIS_STOP_PCT = 8;

function axisPct(v) {
    const w = cur.axisHi - cur.axisLo;
    if (w <= 0) return 0;
    const val = Math.max(cur.axisLo, Math.min(cur.axisHi, v));
    const pre = cur.preAvg;
    // Degenerate preAvg (missing/0, at or below the floor, at or above the ceiling) leaves no
    // usable middle stop -- collapse to the plain single-segment map rather than divide by a
    // zero-width segment or invert the axis.
    if (!(pre > cur.axisLo && pre < cur.axisHi)) {
        return (val - cur.axisLo) / w * 100;
    }
    const V_STOPS = [cur.axisLo, pre, cur.axisHi];
    const P_STOPS = [0, PRE_AXIS_STOP_PCT, 100];
    for (let i = 1; i < V_STOPS.length; i++) {
        if (val <= V_STOPS[i]) {
            const t = (val - V_STOPS[i - 1]) / (V_STOPS[i] - V_STOPS[i - 1]);
            return P_STOPS[i - 1] + t * (P_STOPS[i] - P_STOPS[i - 1]);
        }
    }
    return 100;
}

// Position the fill, the moving tick and its caption. anim=false SNAPS (transition:none) -- used
// to rewind to the resting value before a cold show. The 600ms transition DELAY lives in the CSS
// (.mp-fill, .mp-proj, .mp-capC), so JS sets the target once and lets CSS time it.
// THE AXIS IS A PAIR OF PROPERTY NAMES, not two code paths: GROW is the fill's growth property
// (`width` horizontally, `height` vertically -- 0% at the BOTTOM) and AX the marker's position
// property (`left` / `bottom`). CAP_C_AX is null on the vertical composition, where capC is a static
// cap below the track's bottom end and does not track the proj tick at all; the transition writes
// stay unconditional because suppressing a transition an element never declares costs nothing.
function setPos(v, anim) {
    const p = axisPct(v).toFixed(3) + "%";
    const t = anim ? "" : "none";
    fill.style.transition = t;
    tProj.style.transition = t;
    capC.style.transition = t;
    fill.style[GROW] = p;
    tProj.style[AX] = p;
    if (CAP_C_AX) capC.style[CAP_C_AX] = p;
    if (capCbd) capCbd.style.left = p;   // keep capC's dither strip behind the moving number
}

// The bottom-centre numeral shows pre_avg while the bar fades + slides IN, then swaps to proj_avg
// at VALUE_SWAP_MS -- the same instant the fill/tick begin moving -- so the number never claims a
// gain the bar has not shown yet. The delta arrives WITH that swap.
//
// THE SIGN COLOUR DURING THE ENTRY IS THE *PREVIOUS COMMITTED* ONE -- AN EXPLICIT MAINTAINER
// DECISION, NOT DRIFT, verbatim: "Before the sign class lands, applied color must resemble previous
// state. E.g., when the bar was red and dealt damage moves it into green, it must appear red and
// then turn green after recalculation lands. If it was and will remain red, it must always show
// red." So the sw==false path (the cold damage entry) writes the numeral back to pre_avg and hides
// the delta but DELIBERATELY DOES NOT TOUCH .mp-up/.mp-down: whatever the last showVal(true)
// committed stays applied for the whole 600ms entry, and a NEW sign is only claimed once it lands at
// the swap. The was-red-stays-red case therefore shows NO colour change whatever -- which is the
// whole point; an earlier build stripped both classes here and flashed the neutral fill on every
// single cold entry. Holding a class across coldShow's suppress -> reflow -> armRun sequence
// interpolates nothing: .mp-fill transitions width only, .mp-proj / .mp-capC left only, and no
// .mp-up/.mp-down rule declares a transition at all (see the CSS).
//
// sw==true is the ONLY path that ever REMOVES a class, and it has to stay that way -- it is what
// clears the sign when a transition lands on a rounded-zero delta. So the neutral colour is
// reserved for exactly two states: nothing committed yet (the first show of a battle) and a
// rounded-zero delta. Only this bottom caption (plus the fill and the tick it rides) ever takes
// .mp-up/.mp-down; the two requirement captions and the top-centre pre_avg caption stay plain
// white (see the CSS's "WHO GLOWS" note).
function showVal(sw) {
    const d = cur.projAvg - cur.preAvg;
    capV(capC).textContent = fmt(sw ? cur.projAvg : cur.preAvg);
    capD.style.opacity = sw ? "1" : "0";
    // The MoE-% belongs to projAvg like the delta, so it fades in with it. Its TEXT and visibility
    // are written in paintStatic (every render), so a settings flip -- which moves neither projAvg
    // nor anything in the change-detect -- still lands without a replay.
    capPct.style.opacity = sw ? "1" : "0";
    // SIGN + MAGNITUDE ONLY. The remaining-battles count used to be appended here as "/NN"; it now
    // lives on .mp-capR beside the requirement it is a countdown to, with a glyph of its own (see
    // paintStatic). Do not re-append it: it was the single term that pushed capC's reach to 74rem.
    capDN.textContent = (d > 0 ? "+" : d < 0 ? "-" : "") + fmt(Math.abs(d));
    if (!sw) return;         // the entry window keeps the PREVIOUS committed sign -- see above
    // THE CLASSES KEY OFF THE ROUNDED VALUE, PRECISELY SO GLYPH AND GLOW CAN NEVER DISAGREE. `d`
    // is a raw float but the text above is rounded by fmt(), so an unrounded test glowed GREEN on
    // a displayed "(+0)" (any 0 < d < 0.5 -- routine at EWMA_K, and the "(-0)"-shows-red twin
    // equally so). The CSS says the intent outright: "a sub-precision change never reads as a
    // win". Tested on the MAGNITUDE, exactly as fmt() rounds it (half away from zero) -- NOT
    // Math.round(d), which is -0 for d == -0.5 while the text already reads "(-1)".
    const glows = Math.round(Math.abs(d)) !== 0;
    // capEta rides the SAME test as the delta -- no inversion. d > 0 is a better-than-average
    // battle, which LOWERS battles_to_axis_hi (fewer repeats still needed), so "d > 0 -> green"
    // already reads correctly on the countdown too. The intuitive-but-wrong instinct is "more
    // battles remaining is worse, so invert" -- resist it; there is no separate battles-count
    // delta to test against, only this one d.
    // capPct (the MoE-% text group) rides the SAME sign: the CSS gives it the numeral's glow, and a
    // sibling selector cannot (it precedes .mpv-v vertically), so the class goes on the node itself.
    [capV(capC), capDN, fill, tProj, capEta, capPct].forEach(function (e) {
        e.classList.toggle(ns("mp-up"), glows && d > 0);
        e.classList.toggle(ns("mp-down"), glows && d < 0);
    });
}

// Everything that does NOT animate: the axis-end captions + their mark glyphs, the static pre_avg
// tick and caption, and the met-requirement gold. Safe to re-run on every push.
function paintStatic() {
    capV(capR).textContent = fmt(cur.axisHi);
    setIco(cur.marks >= 3 ? 4 : cur.marks + 1);         // 3 marks -> the general MoE glyph
    // THE REMAINING-BATTLES COUNT, second pair of the same row -- moved here off the delta because it
    // is a countdown to THIS requirement, and because on the delta it cost 15.18rem of the clipping
    // budget (see the header's re-derivation).
    // SUPPRESSION COLLAPSES THE BOX, IT DOES NOT JUST BLANK THE ART: `.mp-ico.none` is
    // `display: none` (MoEProgress.css), so a suppressed glyph takes NO width and NOT the shared
    // 1rem gap either -- verified in the stylesheet before reusing the variant, because a
    // background-only blank would have left a 14rem hole mid-row. The class is toggled, never
    // rewritten: setIco() reassigns className wholesale and would drop `battles`, which is why the
    // family class is static in the template. The TEXT has to be cleared too -- a live count beside a
    // collapsed glyph is exactly the state this suppression exists to avoid.
    // WHEN: >= 1 only. 0 means the requirement is already met (.mp-full's gold says so, and
    // battles_to_axis_hi returns 0 on precisely the same proj_avg >= axis_hi test), -1 is the no-data
    // sentinel, and `>= 1` on a Number() of a possibly-ABSENT field is NaN-false -- so a pre-push
    // frame or an older harness fixture renders no count rather than a bogus one.
    const showEta = cur.eta >= 1;
    capEtaIco.classList.toggle("none", !showEta);
    capEta.textContent = showEta ? fmt(cur.eta) : "";
    if (capEtaBd) capEtaBd.classList.toggle("none", !showEta);
    // THE MoE-% (VM `curPercent`): Python folds the "Show MoE %" setting AND no-data into the -1.0
    // sentinel, so the ONE `>= 0` test covers both; an ABSENT field is NaN, also false.
    capPct.style.display = cur.pct >= 0 ? "" : "none";
    capPctN.textContent = pctText(cur.pct);
    // THE DELTA "(+N)" (VM `showDelta`): a FEATURE switch, `!== false` so an ABSENT field stays shown.
    // display:none takes no space; independent of the % gate above (.mp-d is nested in .mp-pct).
    capD.style.display = cur.showDelta !== false ? "" : "none";
    capV(capP).textContent = fmt(cur.preAvg);
    const pre = axisPct(cur.preAvg).toFixed(3) + "%";
    tPre.style[AX] = pre;
    capP.style[AX] = pre;
    if (capBd3) capBd3.style.bottom = pre;   // keep capP's backdrop strip behind the moving number
    if (capPbd) capPbd.style.left = pre;     // horizontal twin of the above (tracks capP's `left`)
    // The floor tick shows ONLY at zero progress (vertical only; null-guarded == no-op horizontally).
    if (tBottom) tBottom.style.display = cur.projAvg > 0 ? "none" : "";
    root.classList.toggle(ns("mp-full"), cur.projAvg >= cur.axisHi);
}

// Schedule the numeral/delta/sign commit for VALUE_SWAP_MS from now -- the same delay the
// fill/tick transitions carry, so number and bar commit together.
function scheduleSwap() {
    clearTimeout(swapT);
    swapT = setTimeout(function () { swapped = true; showVal(true); }, VALUE_SWAP_MS);
}

// COLD SHOW: the bar is not up -> play the whole mp-life transient.
// The REWIND idiom (transition:none -> write the resting value -> force a reflow -> hand the
// transition back) is what lets a run start from pre_avg even if a previous run was aborted
// part-way; the same treatment cancels a half-finished delta fade. Clearing the pending swap
// FIRST is not optional. Ported from the tuner's replay() (gen_bar_tuner.ps1:921-930).
//
// `atCurrent` (falsy by default -- the DAMAGE-EVENT entry, unchanged) picks which VALUES the run
// opens with; the MOTION is identical either way (armRun(SEEK_NONE), the tuned 600ms fade + 20rem
// slide). Falsy = the rewind above: the FILL/TICK open at axisLo (the true axis floor, 0%) while
// the NUMERAL opens on pre_avg with the delta hidden, then both climb to proj_avg on the
// 600ms-delayed transitions and the numeral swaps at VALUE_SWAP_MS. That floor->current climb
// IS the widget when a damage event pulls the bar up, so it must stay.
// TRUE (only peekOn's Alt entry): open ALREADY committed -- fill/tick/caption snapped to proj_avg,
// numeral + delta + sign already showing -- because Alt is a "show me the state now" request and
// the 0-600ms pre-battle frames read as stale info. No scheduleSwap: there is nothing left to
// commit. The transitions still have to be suppressed and flushed (void root.offsetWidth) BEFORE
// armRun re-adds the run class, or the 600ms-delayed width/left transitions animate anyway and the
// stale flip comes back through the back door; likewise capD's transition is off while opacity
// goes to 1, or the delta fades in over 600ms instead of being simply present.
// This is the transient's onRewind hook: it runs INSIDE a cold show, before the run is armed.
// `atCurrent` is the shared coldShow's `!fromDamage`, i.e. true exactly for peekOn's Alt entry.
function coldRewind(atCurrent) {
    clearTimeout(swapT);
    capD.style.transition = "none";
    capPct.style.transition = "none";
    swapped = !!atCurrent;
    showVal(swapped);
    T.disarm();
    void root.offsetWidth;
    setPos(swapped ? cur.projAvg : cur.axisLo, false);
    void root.offsetWidth;
    capD.style.transition = "";
    capPct.style.transition = "";
}

// ...and this is its onCommit hook: the pre->current climb, run after the transient arms a DAMAGE
// cold show and after every warm re-trigger.
//
// WARM RE-TRIGGER: a change arrived while the bar is ALREADY up, so the transient re-measures the
// DISAPPEARANCE rather than replaying the appearance (see its warmShow). NOTE the one place the
// phase-1 plan does NOT apply: we deliberately do NOT rewind the fill/tick to their resting values
// there. They stay where they are so the bar animates from its CURRENT position to the new target --
// the rewind above is for cold shows only. For the same reason the bottom numeral is left showing
// the PREVIOUS proj_avg until the scheduled swap, so number and bar still commit together.
//
// THE rAF IS COLD-ONLY AND THAT ASYMMETRY IS DELIBERATE: after a cold entry the run class was just
// added and coldRewind wrote a resting value, so the class change and the new target must land in
// DIFFERENT frames (the tuner does the same). A warm re-trigger rewound nothing and rearmed at the
// plateau, so it sets the target synchronously -- as this bar always has.
function commitClimb(cold) {
    if (cold) {
        requestAnimationFrame(function () { setPos(cur.projAvg, true); });
    } else {
        setPos(cur.projAvg, true);
    }
    scheduleSwap();
}

// The transient's onEnd hook -- the value half of its FORCE-SETTLE. mp-life is both-filled so the
// root rests at its 100% stop (opacity 0) with no help from JS, but a swap timer longer than the
// transient would otherwise leave the resting bar showing pre_avg forever, and a cancelled delta
// fade could strand part-way. showVal(true) sets both outright. Ported from
// gen_bar_tuner.ps1:931-940.
function settleValues() {
    clearTimeout(swapT);
    setPos(cur.projAvg, false);
    swapped = true;
    showVal(true);
}

// ...and its onIdle hook: the resting/hidden state. No showVal here -- the bar is invisible, and the
// next entry rewinds the values itself (coldRewind).
function idleValues() {
    clearTimeout(swapT);
    swapped = true;
}

// THE TRANSIENT. Everything shared with MoEEfficiency.js -- arming and its negative-delay debounce,
// the run clock, the ALT PEEK (play or keep mp-life and PAUSE it at the hold plateau, so the entry is
// the real fade+slide and the hold simply never ends; on release, mirror into the fade-out or RESUME
// an interrupted damage hold), the animationend-vs-timer end race, and the surface push +
// post-deadline re-assert. Read its header before touching any of it.
// This bar uses ALL FOUR hooks, because unlike the Damage Efficiency bar its cold entry has values to
// rewind and a pre->current climb to commit. Note peekOn's entry arrives as onRewind(atCurrent=true):
// the Alt entry opens on the CURRENT values, never the pre-battle rewind -- Python pushes a fresh
// compute in the same transaction as setAltHeld (battle_bridge._set_alt_held), so the VM is already
// current and the outdated first frames were purely that rewind.
const T = createTransient({
    root: root,
    boxLeft: BOX_LEFT_REM,
    boxTop: BOX_TOP_REM,
    boxW: BOX_W_REM,
    boxH: BOX_H_REM,
    pad: PAD_REM,
    clipB: CLIP_B_REM,
    onRewind: coldRewind,
    onCommit: commitClimb,
    onEnd: settleValues,
    onIdle: idleValues,
    // THE VERTICAL COMPOSITION. `cls` is the body scope class MoEProgressVertical.css hangs off AND
    // the key to that stylesheet's own re-trigger keyframe twin (MoEBarTransient's RUN_CLASSES_V);
    // `box` replaces the four box* arguments above. Adopted at mount iff the model's `vertical` is
    // true, which then calls goVertical below for the DOM half.
    vert: { cls: "mpv", box: [V_BOX_LEFT_REM, V_BOX_TOP_REM, V_BOX_W_REM, V_BOX_H_REM],
            clipB: V_CLIP_B_REM, padX: V_PAD_X_REM,
            padXR: V_PAD_XR_REM, padXRLarge: V_PAD_XR_REM_LARGE },
    onVertical: goVertical,
});

function render(model) {
    // Truthy guards, not `=== false`: a root VM whose flags are still undefined before Python's
    // first push must stay hidden, not paint a zero-width bar over the HUD. hasData false means
    // the per-tank threshold table gave no usable mark axis -- there is nothing to plot.
    if (!model || !model.visible || !model.hasData) {
        root.style.display = "none";
        T.reset();
        // Drop the change-detect baseline too, so a later re-show starts COLD and the next push
        // becomes a fresh silent one (a scoreboard opening and closing must not replay the bar).
        last = null;
        return;
    }
    root.style.display = "";
    // The pushed size mode (mod_settings.progress_bar_size). Idempotent in the transient, so this is
    // just "keep it in sync"; it owns the root-font write, the .mp-lg body class and the re-derived
    // surface. Nothing in THIS file measures px, so there is nothing else to scale here (contrast
    // MoEEfficiency.js's capClampPct, which mixes offsetWidth with rem literals).
    T.size(Number(model.barSize) === 1);
    // The pushed TRANSITION switches (mod_settings.progress_transitions_events / _manual, with the
    // Transitions master already ANDed in Python -- there is no master field to read here). The
    // transient only records them; the arming path decides per run. Passed RAW, deliberately: the
    // transient reads an ABSENT field as animated (see applyAnim), which is the fail-soft direction --
    // a `!!` here would turn a missing prop into "instant" instead.
    T.anim(model.transEvents, model.transManual);
    // The pushed HOLD DURATION (mod_settings.progress_hold_seconds * 1000). Passed RAW for the same
    // reason as the two switches: the transient reads an absent / non-positive field as the baked
    // 5000ms (see applyHold), which is the fail-soft direction -- a `|| 0` here would mean no hold.
    T.hold(model.holdMs);
    // The pushed CTRL key state (battle_bridge._ctrl_held): the drag-to-reposition gesture, which
    // opens the input hit rect and holds the bar up for as long as the key is down. Passed RAW like
    // the three above -- the transient tests it with `=== true`, so an absent field reads as NOT
    // held, which is the fail-soft direction HERE (an open hit rect would steal HUD input). Ahead
    // of T.peek() below, which ORs this state in.
    T.ctrl(model.ctrlHeld);

    cur = {
        marks: Number(model.marks) || 0,
        axisLo: Number(model.axisLo) || 0,
        axisHi: Number(model.axisHi) || 0,
        preAvg: Number(model.preAvg) || 0,
        projAvg: Number(model.projAvg) || 0,
        // NO `|| 0` here, deliberately: 0 is a MEANINGFUL value (requirement met) and an absent
        // field must not collapse into it. Number(undefined) is NaN, which paintStatic's `>= 1` reads
        // as "render no count" -- the fail-soft direction for a brand-new VM field.
        eta: Number(model.etaBattles),
        // The MoE % (-1.0 == off / no data). BARE, NO `|| 0`, for the same reason as eta: 0.0 is a
        // real percentile and an absent field must not collapse into it. NOT in the change-detect.
        pct: Number(model.curPercent),
        // The per-bar show-delta switch, RAW (`!== false` in paintStatic). NOT in the change-detect.
        showDelta: model.showDelta,
    };
    paintStatic();

    // CHANGE-DETECT, JS-side: replay only when a pushed value actually MOVED. Python re-pushes on
    // every efficiency tick with no dirty check, so without this the bar would replay constantly.
    const changed = last !== null && (
        cur.projAvg !== last.projAvg || cur.preAvg !== last.preAvg ||
        cur.axisLo !== last.axisLo || cur.axisHi !== last.axisHi ||
        cur.marks !== last.marks);
    const first = last === null;
    last = cur;

    // THE SHOW TRIGGER IS GATED ON T.settled(); THE SILENT BASELINE BELOW IS NOT. Before the
    // re-assert the surface is the engine's 256x256 fallback: the bar would come up cropped and
    // ~142px too high (see the shared module's SURFACE_REASSERT_MS). The baseline shows nothing, so
    // it costs nothing to let it run -- and it MUST run, or `last` never gets recorded and the first
    // real change plays a bogus pre->proj climb. T.show() picks warm-vs-cold off its own `showing`.
    //
    // THE SHOW TRIGGER IS ALSO GATED ON `showEvents` (mod_settings.progress_show_events, with
    // "Always" already folded in Python -- there is no master field to read here). `!== false`, NOT
    // `!!`: a model that does not carry the field at all (a pre-push frame, a harness fixture) must
    // degrade to the SHIPPED behaviour, which is "an event raises the bar". The other two visibility
    // switches need no branch -- "Alt Press" and "Always" both arrive folded into `altHeld` below.
    if (first) {
        // Silent baseline: settle the bar at its resting values without showing anything.
        setPos(cur.projAvg, false);
        swapped = true;
        showVal(true);
    } else if (changed && model.showEvents !== false && T.settled()) {
        T.show();
    }

    // Alt is handled AFTER the value change so a push that carries both (Python re-pushes on every
    // Alt transition) gets the new target AND the peek hold. An Alt held BEFORE the surface settled
    // is not lost: the settle re-renders the current model, which arrives here with altHeld still
    // true and peeks then.
    T.peek(!!model.altHeld);
}

// The rigid translation into the surface, the surface push + its post-deadline re-assert, then the
// model subscription and the first render -- all in T.mount (see the shared module).
T.mount(observer, render);
