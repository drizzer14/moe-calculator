// 14th_ua's MoE Calculator -- in-battle centre-screen DAMAGE EFFICIENCY bar. Front-end of a
// STANDALONE registered Gameface view (MoEEfficiencyView.html, declared in
// gui/gen_resources/com.14th_ua.moe_calculator.json) that bridge/efficiency_view.py opens as a
// CONTENT-SIZED (NOT full-screen), input-transparent window centred over the battle HUD. Do NOT
// re-add full-screen sizing / width:100% -- see bridge/battle_view.py for the Ctrl+click/hover
// input-steal that cost us.
//
// THIS IS THE RADIO ALTERNATIVE to the Moving Average bar (MoEProgress.js): Python opens exactly
// ONE of the two, which is the only reason both stylesheets can own #moe-bar-root and the .mp-*
// prefix. Never <link> both in one document.
//
// TWO ORIENTATIONS, ONE DOCUMENT, and that is NOT a contradiction of the line above: this document
// DOES <link> a second stylesheet, MoEEfficiencyVertical.css, whose prefix (.mev-*) is disjoint from
// .mp-* by construction -- so the only selectors that can collide are `body`, `#moe-bar-box` and
// `#moe-bar-root`, and those three are the only ones the vertical sheet scopes under its `body.mev`
// class. Which composition draws comes from mod_settings' progress_bar_orientation, pushed as the
// VM's `vertical`, as a MOUNT-TIME branch (goVertical) -- NOT a second registered layout. The PLACEMENT half is Python's and already
// orientation-aware (bridge/bar_window._resolve).
//
// Because this is a registered view, OUR data model (EfficiencyVM) IS the view's own root
// ViewModel: a bare ModelObserver() with NO feature name, fields read DIRECTLY off the root
// (model.damage, ...). No nested submodel and NO unwrap dance -- that is only the garage's
// nested-model path.
//
// WHAT THE BAR SHOWS: THIS battle's combined damage plotted against all FOUR of the tank's mark
// requirements at once -- five damage stops [0, r65, r85, r95, r100] mapped onto four visually
// EQUAL quarters. The four requirement ticks/captions are pinned at 25/50/75/100 % in the CSS;
// only the fill, the current tick and its caption are positioned from here.
//
// AND THE AXIS ARITHMETIC IS NOT DONE HERE. Unlike MoEProgress.js (which derives its position from
// the pushed axis ends), Python pushes `barX` (0..100 % of the bar) and `band` (0..4, the highest
// requirement PASSED, `>=` INCLUSIVE) as finished values -- domain/battle_builder.efficiency_bar_x
// and efficiency_band. Do NOT recompute either here: the inclusive-boundary rule must live in
// exactly one place, and it is unit-tested there. The four r* props are for the CAPTION NUMERALS
// only. `.met` on a requirement tick likewise comes off `band` (stop i is met iff i <= band), not
// off a damage comparison.
//
// THE LOOK IS THE TUNER'S AND NOT NEGOTIABLE: MoEEfficiency.css is tools/dev/eff_bar_tuner.html's
// emit verbatim (reproducible with `node tools/dev/emit_eff_css.js`) plus two marked hand-added
// blocks, and this file is a port of that tuner's own preview pass (apply / showDelta / replay)
// crossed with MoEProgress.js's proven transient machinery. Every number below is mirrored from
// that stylesheet's trailing JSON `meta` block. The battle window has NO hot-reload (it pins its
// resources at client launch), so every tweak here costs a full client relaunch: tune in the
// browser, not in the client.
//
// pointer-events:none throughout (in the CSS) -- pure HUD info, never an input target.
import { ModelObserver } from "../../libs/model.js";
// The transient machinery -- arming, the negative-delay debounce, the Alt peek's pause/seek, the
// end race and the surface re-assert -- is SHARED with MoEProgress.js. Every behaviour in there cost
// a client relaunch to find; read its header before changing anything that touches timing.
// Separate documents, so this module is instantiated twice with no cross-talk.
import { createTransient, fmt, pctText, SIZE_F, SIZE_XF } from "./MoEBarTransient.js";

// No feature name -> observe this view's OWN root model (window.model == EfficiencyVM).
const observer = ModelObserver();

// meta.deltaHoldMs -- the delta's OWN, SHORTER window, this bar's only timing of its own. It is not
// tied to the transient at all (that is the tuned intent: the increment is a flash, the bar is a 5s
// readout), so it fades on .mp-d's own 500ms opacity transition well before the bar leaves.
const DELTA_HOLD_MS = 1600;

// --- the axis / clamp contract, also from `meta` ----------------------------------------------
// The bar's own width (#moe-bar-root), which every percentage resolves against and which the cap
// clamp works in. meta.capClamp is the corridor the current caption may not leave, in the SAME
// document-rem coordinates: the box is the 300rem track plus 45rem of pad each side (box re-cut for
// edge-drag, was 80), minus the tuned 4rem end inset, i.e. [-41, 341].
const BAR_W_REM = 300;
const CLAMP_L_REM = -41;             // meta.capClamp.leftRem
const CLAMP_R_REM = 341;             // meta.capClamp.rightRem
// The icon's gap to the numeral, which rides in .mp-ico's transform (translate(-1rem, -50%)) and
// so is NOT part of its offsetWidth -- the clamp has to add it back, exactly as the tuner does.
const ICO_GAP_REM = 1;
// The MoE-% caption's DELTA gap (the delta's translate off the %'s right edge -- the 0.35em idiom at
// 12rem == 4.2rem, an x-length like the icon's, so capClampPct scales it by SIZE_XF). The %'s own
// gap is .mp-pct-t's margin-left, which w(".mp-pct") already measures.
const PCT_GAP_REM = 4.2;
// band -> the ONE class that goes on #moe-bar-root, in meta.bands order (white/green/teal/violet/
// gold). Python's `band` indexes straight into this.
const BAND_CLASSES = ["mp-b-w", "mp-b-g", "mp-b-t", "mp-b-v", "mp-b-au"];

// The pushed LARGE size mode (VM `barSize`), mirrored here because capClampPct needs it -- it is the
// one place on either bar that mixes a MEASURED px width with rem literals, so the 1rem == 1 logical
// px identity it rests on breaks under the large mode's 1.25x root font. The transient owns everything
// else about the flag (see its SIZE_F / SIZE_XF).
let large = false;

// --- the surface, and the rigid shift into it ----------------------------------------------
// A Gameface view PUSHES its own size to C++ through the `viewEnv` global
// (viewEnv.resizeViewRem(w, h), rem == logical px); a view that never calls it gets the engine's
// "default view size" fallback after a `Size calculation timeout` -- a flat 256x256 logical px.
// There is NO Python-side and NO resource-declaration lever for this (see bridge/efficiency_view.py), and
// pushing the size is not sufficient on its own: the engine ALSO tries to measure the document and
// ITS FALLBACK RUNS LAST AND WINS. See SURFACE_REASSERT_MS.
//
// The composition's bounding box, document origin at (0,0) and 1rem == 1 logical px, IS
// .mp-backdrop -- left -45rem / top -35rem / 390 wide / 66 tall (MoEEfficiency.css; the emitted
// value, asserted by tools/dev/check_eff_css.js). Everything else fits inside it with
// room to spare, measured against the emit rather than guessed:
//   * TOP: the .mp-cap.up numeral's box bottom sits at -12rem (bottom:100% of the 3rem track, then
//     translateY(-12rem)), so at a 16rem font with its pinned 20.5rem line box its top is ~-32.5
//     and its 6rem band glow reaches ~-38.5. Its out-of-flow glyph and the current tick's 6rem glow
//     are shallower still.
//   * BOTTOM: .mp-cap.dn tops out at 15rem (top:100% + margin-top:12rem) and its pinned 15.5rem
//     line box reaches ~30.5 -- its .mp-d delta (translate(4.2, 2.5)) hangs deeper still, to ~33.
//   * SIDES: .mp-cap.r4 sits at 100 % (x == 300) and the current caption's delta hangs off its
//     right edge, reaching ~375 at four digits -- which is precisely why meta.capClamp's right
//     bound is 376. The clamp below keeps it there whatever the digits do.
//   * MoE-% (.mp-pct "(73.84%)", out of flow at left:100% of the numeral, the delta re-parented
//     INSIDE it). THE % IS THE DAMAGE NUMERAL'S SIZE (16rem / 20.5rem, no Y offset -- so no height
//     moved): "(100.00%)" is 2*0.3008 + 5*0.4932 + period 0.2471 + percent 0.7734 == 4.0881em ==
//     65.41rem at 16rem, so the right overhang becomes 4.2 + 65.41 + 4.2 + the delta
//     (capClampPct measures it) and the clamp pulls the wider caption inward -- the ink stays in the
//     corridor, so the box is UNCHANGED. The width-fixed .mp-bd-5 strip (centred on the numeral)
//     stays 90 -> 150 (Large 120 -> 200, as at the 12rem %): +-75 vs numeral/2 + 4.2 + 65.41 ==
//     87.37, so the rare 100.00% overhangs the dither by a few rem (accepted). setPos() re-centres the strip so its
//     own left edge never crosses the surface's (BOX_LEFT*xf - PAD == -55), so a numeral near the
//     axis start leaves the strip to the right of it: its right edge still clears the % ink.
// So the surface is that box plus PAD_REM of slack on all four sides, and the whole composition is
// rigidly translated by that much so NOTHING sits at a negative coordinate -- an origin overflow
// is clipped no matter how big the surface is.
//
// NOT A THIRD COPY: MoEProgressView.html's sizing shim is sized to that bar's surface, but THIS
// document's #moe-bar-box is 460x51rem straight out of the tuner's emit (the bar plus its two
// caption rows). Leave it emitted -- the box provably does not stop the size timeout anyway, so
// its exact value buys nothing, and hand-editing it would be silent drift from the emit.
// These five ARE this bar's surface contract and stay HERE, per bar. MoEBarTransient derives the
// rest from them (its box*/pad arguments), exactly as this file used to:
//   VIEW_W_REM = BOX_W_REM + 2 * PAD_REM == 410     SHIFT_X_REM = PAD_REM - BOX_LEFT_REM == 55
//   VIEW_H_REM = BOX_H_REM + 2*PAD_REM - CLIP_B_REM == 78   SHIFT_Y_REM = PAD_REM - BOX_TOP_REM == 45
// SHIFT_Y_REM is MIRRORED (negated) in Python as
// domain/constants.EFFICIENCY_ANCHOR_Y_SHIFT, so changing BOX_TOP_REM or PAD_REM moves the bar on
// screen until that constant follows. The hit padding and the re-assert timing live in the shared
// module (its HIT_MAGIC / SURFACE_REASSERT_MS -- both LOAD-BEARING, read its header).
// SEED (FIRST CUT, box re-cut for edge-drag): with the whole-bar backdrop gone, the surface is
// re-derived from the ACTUAL visible composition (track + captions + per-caption .mp-bd shadow
// strips). The prose ABOVE predates this re-cut (old 460x96) -- these four consts are the truth.
// WIDTH shrank (460->390): the surface must stay SYMMETRIC about the 300rem track (no X term in
// anchor_centred -- test_the_backdrop_brackets_the_track_symmetrically), so BOX_W == 300 - 2*BOX_LEFT.
// The moving .mp-bd-5 (capC's strip, +-45) swings to root-x -45..345 == 45 clearance each side, so
// clearance dropped 80->45 (boxPad/bdBleedX in eff_bar_tuner.html both moved to 45).
// HEIGHT (iter 3): FIX A restored the CURRENT-DAMAGE strip (.mp-bd-5, the .up caption) to a taller
// 26rem re-centred on the numeral (the shared 16rem left it too thin); the mark strips (.mp-bd-1..4)
// stay at 16. The current-damage strip is the TOP one here, so it grows the box UP: topmost is now
// .mp-bd-5's top (-35); bottommost is the r-caption strips' box bottom (base top 15 + 16 == 31).
// BOX_TOP -35 .. bottom 31 == 66.
// FIX B (reach the bottom screen edge): PAD_REM stays 10 (top/sides do no harm at 10; the current-
// damage sign-glow is now INSIDE the box). The BOTTOM alone is trimmed by CLIP_B_REM (shared module
// clipB: viewH = boxH + 2*PAD - clipB), which shortens the surface bottom WITHOUT moving the
// composition (clipB never enters shiftY). Bottom pad becomes PAD_REM - CLIP_B_REM == 2rem: the
// r-caption strips end at box bottom 31 and their numerals carry only a 1rem drop (no 6rem glow),
// so the deepest bottom ink is ~28.6 -- 2rem inside the strip box, nothing clips.
const BOX_LEFT_REM = -45;                            // leftmost edge (== -clearance; symmetric)
const BOX_TOP_REM = -35;                             // topmost edge (.mp-bd-5's taller strip top)  [was -30]
const BOX_W_REM = 390;                               // track 300 + 2*45 clearance (== meta.boxWRem)
const BOX_H_REM = 66;                                // seed: bounds the strips (bd-5 now 26 tall)  [was 61]
const PAD_REM = 10;                                  // slack for the shadow/glow bleed
// BOTTOM-only surface trim (iter 3). Effective bottom pad == PAD_REM - CLIP_B_REM == 2rem. Y-length,
// scales with SIZE_F in applySize; never enters shiftY, so the domain Y-shift constants are unchanged
// by IT (they move this round only because FIX A raised BOX_TOP).
const CLIP_B_REM = 8;

// --- THE VERTICAL ORIENTATION (mod_settings.progress_bar_orientation, pushed as the VM's
// `vertical`) ------------------------------------------------------------------------------------
// A SECOND COMPOSITION IN THE SAME DOCUMENT, not a restyle of this one: its own stylesheet
// (MoEEfficiencyVertical.css, <link>ed alongside MoEEfficiency.css from MoEEfficiencyView.html),
// its own namespace-disjoint prefix (.mev-*), its own DOM order (numeral BEFORE icon, delta LEFT of
// the numeral) and its own surface. NO second registered layout: orientation is a MOUNT-TIME
// branch.
//
// V_BOX_* IS .mev-backdrop, exactly as BOX_* above is .mp-backdrop. Note it is NOT a transpose of
// these four -- the vertical tuner's own tuned lengths -- but its TOP and HEIGHT are IDENTICAL to
// the vertical Moving Average bar's (-80 / 360), which is why the two share ONE Python shift
// constant where their horizontal siblings need -50 and -44 apiece:
//   V_VIEW_W_REM = V_BOX_W_REM + V_PAD_X_REM        V_SHIFT_X_REM = V_PAD_X_REM - V_BOX_LEFT_REM == 154
//               + V_PAD_XR_REM == 171 (a SPLIT pad now -- see both constants' own notes below)
//   V_VIEW_H_REM = V_BOX_H_REM + 2 * PAD_REM
//                               - V_CLIP_B_REM == 318 V_SHIFT_Y_REM = PAD_REM - V_BOX_TOP_REM  == 90
// THE X AXIS IS NOT box + PAD_REM EITHER -- SAME DEFECT THE MOVING AVERAGE BAR ALREADY FIXED
// (MoEProgress.js's V_PAD_X_REM note carries the mechanism in full; only the numbers differ here).
// Every caption here is RIGHT-ANCHORED (`right: 100%`, MoEEfficiencyVertical.css's .mev-cap) and
// grows LEFTWARD from a fixed edge, same as the sibling bar's captions, so "left" is the overflow
// direction for every one of the maintainer's nudges below.
// THIS WENT THROUGH TWO CORRECTIONS TO THE SAME BUG, because the first one watched only one
// caption family:
//   PASS 1 (14rem): the per-mark gap pass (icon_gap_tuner.html) pushed mark_2/mark_3 far enough
//     that PAD_REM's flat 10rem no longer covered them. But that pass's own re-derivation used the
//     WRONG icon width for the mark rows (13rem, the shared base `.mev-ico` box) instead of the
//     16rem `.mev-ico.mk` override the mark icons actually render at (CSS specificity: `.mev-ico.mk`
//     beats bare `.mev-ico`), AND it never checked `.mev-cap.bt` (the current-damage + delta row) at
//     all -- exactly the "a gate that only watches one caption" mistake the Moving Average bar's own
//     capC-is-the-extreme derivation already exists to warn against.
//   PASS 2 (52rem, this one): re-derives EVERY row, worst case, 4-digit+comma numerals throughout
//     (font-size / icon width / icon margin-left all read from the shipped CSS, never transcribed):
//       r1 (mk1, tx -2):  2 + 16(.mev-ico.mk) + (-1)(mk shared margin) + 26.64(numeral) + 1(halo) == 44.64
//       r2 (mk2, tx -4):  4 + 16 + 0.5 + 26.64 + 1 == 48.14
//       r3 (mk3, tx -6):  6 + 16 + 3.0 + 26.64 + 1 == 52.64
//       tp (bm, tx -3+7=4, AFTER the maintainer's "move the top block left 4px" nudge, was tx 8):
//         -4 + 14(.mev-ico.bm) + 1.253 + 26.64 + 1 == 38.89
//       bt (dmg, tx -3+6=3, AFTER the maintainer's "move the bottom block left 7px" nudge, was
//         tx 10): the BARE signed delta (no parens, unlike the sibling bar's) sits LEFT of the
//         numeral via its own translate(-4.2rem, ...), so it -- not the numeral -- is the worst
//         point:
//         -3 + 16(.mev-ico.dmg) + 1(shared margin) + 35.52("3,050" at 16rem) + 4.2(delta gap)
//           + 32.56("+2,970" at 12rem, sign+4digits+comma, no parens) + 1(halo) == 87.28
//     .bt IS THIS FILE'S EXTREME (87.28 > 52.64 > 48.14 > 44.64 > 38.89), exactly as .mpv-capC is
//     for the Moving Average bar's sheet -- and by the SAME margin (each grew its own V_PAD_X_REM
//     by exactly its own nudge's device-px count and landed on ~4.5rem of margin, not a coincidence,
//     just two rows with the same shape being pushed by the same kind of nudge):
//       V_PAD_X_REM == 92 + V_BOX_LEFT_REM == 92 - 40 == 52   (allowance 92, reach 87.28, margin 4.72)
//     THE MoE-% CAPTION: V_MARKUP puts an in-flow .mev-pct "(73.84%)" between the delta and the
//     numeral, adding 65.41 ("(100.00%)" at the NUMERAL'S 16rem -- the % matches the damage numeral's
//     size, same 20.5rem line box and Y nudge, so the row's height did not move: 2 parens + 5 digits +
//     period 0.2471 + percent 0.7734) + the gap (ABSOLUTE 4.2rem) to the .bt row. THE TEST IS THE
//     AUTHORITY for the sum (it reads every term, incl. the row's translateX/margins, off the CSS): it
//     measures .bt at 149.89rem and wants >= 4rem spare, so the allowance had to reach 153.89:
//       V_PAD_X_REM == 154 + V_BOX_LEFT_REM == 154 - 40 == 114   (was 98 at the 12rem %, 52 pre-%;
//       allowance 154, 4.11 spare)
//     (the 87.28 above is the PRE-% figure; EFFICIENCY_MM_TRACK_X(_LARGE) grew by the same amount.)
// tests/test_efficiency_surface_mirror.py::test_the_vertical_captions_fit_inside_the_surface is
// the GATE on all of this, re-deriving every row (not just the mark rows) from the stylesheet
// rather than trusting this note.
// GROWING THIS MOVES THE TRACK INSIDE THE SURFACE, so domain/constants.EFFICIENCY_MM_TRACK_X(
// _LARGE) had to grow with it by the exact same amount (in logical px, i.e. *SIZE_F under Large)
// or the visible bar would slide RIGHT into the minimap -- see that constant's own comment.
// V_SHIFT_Y_REM is MIRRORED (negated) in Python as domain/constants.VERTICAL_ANCHOR_Y_SHIFT (-90,
// -113 for Large == -round(90 * SIZE_F)). #moe-bar-box in MoEEfficiencyVertical.css is sized to the
// derived surface -- and unlike the horizontal file's box (left at the tuner's own emitted 460x55,
// deliberately not a surface copy) that one IS a third copy: keep it in lockstep.
//
// THE SURFACE IS THE ONLY SIDE THAT IS NOT box + PAD_REM, AND THAT IS THE WHOLE POINT (V_CLIP_B_REM).
// Read the sibling MoEProgress.js's own V_CLIP_B_REM note first -- the mechanism, the engine clamp it
// works around and the Large-mode reasoning are IDENTICAL and are written out once, there. Only the
// two numbers differ, because the two vertical tuners' bottom gaps differ:
//   V_CLIP_B_REM == (V_BOX_H_REM + 2*PAD_REM) - (V_SHIFT_Y_REM + barLen + bottomGap)
//                == 380 - (90 + 200 + 28) == 62
// `bottomGap` 28 is THIS bar's tuned value (tools/dev/eff_bar_tuner_vertical.html:470), against the
// Moving Average tuner's 30 -- a difference that used to be UNOBSERVABLE (both were below the shared
// 90 of slack, so the clamp flushed either to the same place) and is observable now, which is exactly
// why domain/constants' single MM_GAP_BOTTOM is split per bar in the same change.
// The surface's below-the-track slack becomes 318 - 290 == 28 == the tuned gap exactly (290 is
// V_SHIFT_Y_REM + barLen == domain/constants.MM_TRACK_Y, which this does NOT move). Under Large the
// pushed surface is round(318 * SIZE_F) == 398 against MM_TRACK_Y_LARGE 363, i.e. 35 of slack ==
// 28 * SIZE_F exactly -- so the fixed 28 is unreachable there and the engine's flush delivers the
// scaled gap, which is the sibling's 30 -> 37 case with this bar's own two numbers.
// WHAT IT COSTS, DERIVED FROM THE SHIPPED CSS, is 3.5rem of clearance on the bottom caption's ink and
// nothing else. .mev-cap.bt (MoEEfficiencyVertical.css) is `top: 100%` + `margin-top: 3rem` off the
// track's bottom end and its flex row is `line-height: 20.5rem` tall (the numeral's line box beats its
// 16rem .dmg icon; the delta is position:absolute and contributes no height at all), so its box ends
// 3 + 20.5 == 23.5rem below the track; the numeral's 1rem dark-drop text-shadow radius reaches 24.5,
// the icon's translateY(0.5rem) + its ::before 106% glow (3% of 16rem) reaches 22.2, and the delta --
// `top: 0` + translate(_, 1.5rem), 15.5rem tall, + 1rem of drop -- reaches 21.0. So the deepest ink is
// 24.5 against 28 of slack. The ONLY thing past the edge is the band glow's soft tail (the 6rem blur
// on .mev-cap.bt .mev-v under every #moe-bar-root.mev-b-* band, reaching ~29.5), which the tuner clips
// at its own stage bottom at the same 28.
// THE 256x256 SIZE-TIMEOUT FALLBACK STILL RUNS LAST AND STILL WINS here, and the vertical surface is
// pushed and RE-ASSERTED after the deadline by the same shared machinery (MoEBarTransient's
// SURFACE_REASSERT_MS); each push round-trips back as onSizeChanged -> bar_window._place, which is
// what makes the placement agree with the surface.
// FOUR DURABLE FACTS, established by reading the source rather than assuming (a maintainer once
// saw the minimap's first column "covered by a dark panel" and the fix took four rounds to land):
//   1. THE BACKDROP IS NOT MEANT TO COVER THE RIGHT-ANCHORED CAPTIONS -- only V_PAD_X_REM (above)
//      was ever sized for their ink. .mev-backdrop is a SEPARATE rectangle, drawn for the
//      shadow/glow bleed around the TRACK, and r1-r3/tp/bt already reach far past it by design (see
//      the V_PAD_X_REM derivation above -- 38.89 to 87.28rem, against a 40rem backdrop bleed). Do
//      not "fix" a clip by widening the backdrop; that is V_PAD_X_REM's job, on the SURFACE, which
//      is never drawn.
//   2. THE VERTICAL BAR'S BACKDROP HAS NO SYMMETRY CONTRACT. The symmetry test in this repo
//      (`test_the_large_backdrop_stays_symmetric_about_the_track`) covers ONLY the HORIZONTAL bar's
//      `.mp-backdrop`, because `anchor_centred_reduced`'s `max_x // 2` has no X term and only
//      centres the BAR by centring the SURFACE -- true for the Damage Log (horizontal) anchor.
//      Fixed+Vertical resolves through `anchor_minimap` instead (bar_window._resolve), whose
//      `x = space_x - mm_size - gap - overhang - edge_x` reads `edge_x` (EFFICIENCY_MM_TRACK_X) and
//      NOTHING about the backdrop's own width or left. Trimming `.mev-backdrop` asymmetrically
//      (this file's own V_BOX_W_REM, leaving V_BOX_LEFT_REM alone) moves nothing the placement math
//      depends on.
//   3. THE BACKDROP TRIM (V_BOX_W_REM 96 -> 54) WAS REAL WORK -- KEEP IT. A maintainer report of
//      the backdrop "sitting well clear of the minimap" turned out to describe a DIFFERENT panel;
//      measured live on the sibling Moving Average bar (same mechanism, same minimap edge), this
//      bar's own backdrop right edge (V_PAD_X_REM + V_BOX_W_REM == 52+54==106) landed EXACTLY on
//      the minimap's own left edge (EFFICIENCY_MM_TRACK_X + MM_GAP + MM_TICK_OVERHANG ==
//      95+8+3==106) -- zero overlap, by design, at the tuned 54, AT THE TIME (the shared MM_GAP
//      was 8). Reverting to 96 (right edge 148) would reopen a real 42rem overlap. Do not touch
//      V_BOX_W_REM again without a live measurement to justify it.
//      SINCE THEN, PLACEMENT MOVED CLOSER TO THE MINIMAP (domain/constants.EFFICIENCY_MM_GAP
//      (_LARGE), 3/3, replacing the shared MM_GAP(8) for this bar's own anchor) -- the backdrop's
//      own DRAWN right edge no longer sits flush with the minimap's now-closer left edge. Not a
//      regression: fact 4 below already established the DRAWN backdrop is not what clears the
//      minimap, the invisible SURFACE is (V_PAD_XR_REM/_LARGE), and the surface still clears it
//      with a real, checked margin at the new gap -- see V_PAD_XR_REM's own derivation below.
//   4. THE ACTUAL CULPRIT WAS THE INVISIBLE SURFACE'S OWN RIGHT PAD, NEVER UPDATED TO MATCH. The
//      backdrop trim shrank the DRAWN rect; nothing shrank the SURFACE (the mouse-hit-blocking rect
//      per this file's header) on that side, so it stayed the OLD symmetric V_PAD_X_REM(52) past
//      the ALREADY-TRIMMED backdrop -- see MoEBarTransient.js's `padXR`/`padXRLarge` arg notes for
//      the fix (a SEPARATE, smaller right pad, V_PAD_XR_REM/_LARGE below) and V_PAD_XR_REM's own
//      derivation, mirroring the sibling Moving Average bar's live-measured diagnosis exactly.
//      Because the fix only shrinks the RIGHT pad and V_PAD_X_REM (the LEFT side, where the caption
//      ink and the track itself both live) is untouched, `shiftX` and therefore
//      EFFICIENCY_MM_TRACK_X(_LARGE) -- both pure functions of the LEFT side alone -- need no
//      correction, and the bar does not move on screen.
const V_BOX_LEFT_REM = -40;                          // .mev-backdrop's left
const V_BOX_TOP_REM = -80;                           // .mev-backdrop's top
const V_BOX_W_REM = 54;                              // .mev-backdrop's width (right edge only, trimmed -- see fact 3)
const V_BOX_H_REM = 360;                             // .mev-backdrop's height
const V_CLIP_B_REM = 62;                             // backdrop bleed the SURFACE clips off the bottom
const V_PAD_X_REM = 114;                             // the LEFT X slack, decoupled from the backdrop -- see above
// THE SURFACE'S RIGHT (minimap-facing) PAD -- see the sibling MoEProgress.js's own V_PAD_XR_REM note
// for the full mechanism; only the numbers differ here, and it is a SEPARATE knob from the backdrop's
// own V_BOX_W_REM trim above: that trim shrinks what is DRAWN, this shrinks what is CLICK-BLOCKING
// (the surface, never drawn).
// UNLIKE THE MOVING AVERAGE BAR, EFFICIENCY_MM_TRACK_X CARRIES NO HAND CORRECTION ("pure derivation,
// no correction" -- domain/constants.py's own comment), so it IS this bar's true local tick position
// and needs no re-derivation the way the sibling file's fact 5 does. Solved against
// MoEBarTransient.applySize's own formula (viewW == round((boxW*xf + padX + padXR) * f)) for the
// tick's own visible right edge PLUS a small, deliberate MARGIN (+2 logical/document px, flat, NOT
// xf-scaled) -- a flush boundary (viewW == tick-right exactly, zero margin) is the "rounding could
// shave a px and eat the ink" risk the margin exists to head off, mirroring the sibling file's fact 5:
//   Default (xf=f=1):  tick-right == 95 + 3 == 98  ->  viewW == 98 + 2 == 100  ->
//     padXR == 100 - V_BOX_W_REM(54) - V_PAD_X_REM(52) == -6
//   Large:  tick-right_pre_f == 137/SIZE_F... computed directly, not via the rounded PX constant:
//     shiftX_large_pre_f(316/3) + trackW_large(4) + overhang_large_pre_f(4) == 340/3 ~= 113.333
//     (renders at 113.333*SIZE_F ~= 141.667 device px) -> viewW_pre_f == 340/3 + 2 == 346/3 ~= 115.333
//     -> round(115.333 * SIZE_F) == 144 -> padXRLarge == 346/3 - boxW*xf(72) - V_PAD_X_REM(52) ==
//     -26/3 ~= -8.667
// Both NEGATIVE: the box+left-pad sum (54+52==106 Default, 72+52==124 pre-SIZE_F Large) was flush
// with the minimap at the ORIGINAL shared MM_GAP(8) (fact 3), so ANY margin (to the tick, or to
// the minimap) needed the surface a shade smaller still -- the surface's right edge sits a little
// further inside the backdrop's own (already trimmed) drawn rect than its own edge. This
// derivation (padXR/padXRLarge themselves) is UNCHANGED by the later gap move -- pure JS/CSS
// geometry, independent of where Python places the window -- but the MARGIN it buys against the
// minimap moved WITH that gap. Resulting margins, both real and checked
// (tests/test_efficiency_surface_mirror.py::test_the_surface_clears_the_minimap_at_every_size_index /
// test_the_surface_does_not_clip_the_tick), at domain/constants.EFFICIENCY_MM_GAP(_LARGE) == 3/3:
// Default clears the minimap by 1px (was 6px at the original shared gap of 8) and the tick by
// 2px; Large by 1px (was 6px) and ~2.3px respectively.
// ADVANCED 4 logical px into the minimap (2026-08-12, in-client): the previous margin==1 cleared the
// minimap's DROP-SHADOW but left the backdrop 4px off the minimap's REAL edge -- that 4px is the
// minimap's non-interactive frame margin, maintainer-confirmed safe to consume (Ctrl-click area is
// further in). Surface right edge (and the flush strips) now at margin == -3, flush to the minimap:
//   Default: view_w == 8 + 3 + 157 - (-3) == 171 -> padXR == 171 - V_BOX_W(54) - V_PAD_X(114) == 3
//   Large:   view_w == 8 + 5 + 214 - (-3) == 230 -> padXRLarge == 230/SIZE_F - boxW*xf(72) - 114
//                                             == 184 - 186 == -2.0
//   (MoE-% passes: V_PAD_X 52 -> 98 -> 114 and EFFICIENCY_MM_TRACK_X 95 -> 141 -> 157 / 137 -> 194 ->
//   214 moved together, so Default padXR is unchanged at 3 and Large's stays -2.0 (214 vs the pure
//   214.167).)
const V_PAD_XR_REM = 3;                              // the RIGHT (minimap-facing) X slack, Default
const V_PAD_XR_REM_LARGE = -2;                       // ...and Large -- its OWN literal, see above

// THE LIVE ORIENTATION PROFILE -- see the sibling MoEProgress.js for the same three-value shape.
//   PFX      the class prefix every selector and toggled class here is written in. The source spells
//            everything "mp-..." and ns() rewrites it, so the literals stay greppable.
//   AX       the property a marker's position is written to: `left` / `bottom` (0% at the BOTTOM).
//   GROW     the property the fill grows along: `width` / `height`.
//   CAP_C_AX the axis the CURRENT caption tracks, or null if it does not move. It is null on the
//            vertical composition, where the current value + delta are a STATIC readout below the
//            track's bottom end and only the current TICK follows the fill -- which also retires
//            capClampPct entirely there (a static caption cannot overflow the corridor).
let PFX = "mp";
let AX = "left";
let GROW = "width";
let CAP_C_AX = "left";

function ns(s) { return PFX === "mp" ? s : s.replace(/\bmp-/g, PFX + "-"); }

// THE HORIZONTAL COMPOSITION'S MARKUP (the vertical one is V_MARKUP below; ensureRoot builds this
// one and goVertical replaces it). Markup shape is the tuner's stage verbatim
// (eff_bar_tuner.html:333-351): backdrop, then the track carrying the fill, the four FIXED
// requirement ticks, the one moving current tick, the four requirement captions (three marksOnGun
// glyphs + the barrel_mark at 100 %) and the current caption with its BARE signed delta -- no
// parens on this bar, unlike the Moving Average one. The .mp-d / .mp-d-num split stays anyway: the
// wrapper carries the gap, size and fade, the inner numeral is what JS writes the digits into (see
// the CSS). NO word labels anywhere: MoEBattle.ttf is a 19-glyph numeric subset
// (digits % ( ) + - , . / space) and a letter renders BLANK.
const MARKUP =
        // Per-caption dither strips (MoEEfficiency.css .mp-bd) -- one small box behind each caption,
        // z-index 0 at root so the captions (inside .mp-track's stacking context) paint over them.
        // r1..r4 (.mp-bd-1..4) are fixed at the quarter marks; capC (.mp-bd-5) is JS-tracked to its left.
        '<div class="mp-bd mp-bd-1"></div><div class="mp-bd mp-bd-2"></div>' +
        '<div class="mp-bd mp-bd-3"></div><div class="mp-bd mp-bd-4"></div>' +
        '<div class="mp-bd mp-bd-5"></div>' +
        '<div class="mp-track">' +
        '  <div class="mp-fill"></div>' +
        '  <div class="mp-tick mp-req r1"></div>' +
        '  <div class="mp-tick mp-req r2"></div>' +
        '  <div class="mp-tick mp-req r3"></div>' +
        '  <div class="mp-tick mp-req r4"></div>' +
        '  <div class="mp-tick mp-cur"></div>' +
        '  <div class="mp-cap dn r1"><i class="mp-ico mk mk1"></i>' +
        '<span class="mp-v"></span></div>' +
        '  <div class="mp-cap dn r2"><i class="mp-ico mk mk2"></i>' +
        '<span class="mp-v"></span></div>' +
        '  <div class="mp-cap dn r3"><i class="mp-ico mk mk3"></i>' +
        '<span class="mp-v"></span></div>' +
        '  <div class="mp-cap dn r4"><i class="mp-ico bm"></i>' +
        '<span class="mp-v"></span></div>' +
        // THE MoE-% (.mp-pct) is OUT OF FLOW like the delta was, so the numeral alone stays on its
        // tick, and the DELTA IS RE-PARENTED INSIDE it so its own left:100% resolves off the %'s
        // right edge ("1,850 (73.84%) +120"). .mp-pct-t is the gated text group: hiding THAT (not
        // .mp-pct) keeps the delta alive when the % is off. NOT .mp-v -- capV() is a first match.
        '  <div class="mp-cap up mp-capC"><i class="mp-ico dmg"></i><span class="mp-v"></span>' +
        '<span class="mp-pct"><span class="mp-pct-t">(<span class="mp-pct-num"></span>)</span>' +
        '<span class="mp-d"><span class="mp-d-num"></span></span></span></div>' +
        '</div>';

// ...and THE VERTICAL COMPOSITION'S markup, tools/dev/eff_bar_tuner_vertical.html's stage verbatim.
// FOUR structural differences from the horizontal template above, all of them the tuner's tuned
// layout and none free to "tidy":
//   * NUMERAL BEFORE ICON in every caption (the icon trails, away from the track), and the DELTA
//     FIRST on the current caption. That ordering is what makes the shared right:100% anchor
//     digit-count invariant: the icon is the LAST in-flow child, flush against a FIXED edge, so only
//     the numeral grows and it grows leftward. Reversing it re-introduces the exact defect that
//     shipped once on the horizontal Moving Average bar.
//   * the four requirement captions split by ROLE, not one `dn` class: r1-r3 are `lf` (each beside
//     its own 25/50/75% tick) and r4 is `tp` (a static cap above the track's TOP end), because a
//     vertical axis has no single "below the track" side to share.
//   * the current caption is `bt mev-capC` -- a static cap below the BOTTOM end. It keeps mev-capC
//     purely so the ref lookup below is one selector for both orientations.
//   * every caption is a SIBLING of .mev-track rather than a child, exactly as the tuner has them
//     (root and track are the same 3x200rem box, so every percentage resolves identically; this
//     only keeps the diff against the tuner readable).
const V_MARKUP =
        '<div class="mev-backdrop"></div>' +
        // Per-row dither strips (MoEEfficiencyVertical.css .mev-bd) -- one per number row, each
        // flush on the surface's minimap-facing edge. Positioned purely by CSS `top`.
        '<div class="mev-bd mev-bd-1"></div><div class="mev-bd mev-bd-2"></div>' +
        '<div class="mev-bd mev-bd-3"></div><div class="mev-bd mev-bd-4"></div>' +
        '<div class="mev-bd mev-bd-5"></div>' +
        '<div class="mev-track">' +
        '  <div class="mev-fill"></div>' +
        '  <div class="mev-tick mev-req r1"></div>' +
        '  <div class="mev-tick mev-req r2"></div>' +
        '  <div class="mev-tick mev-req r3"></div>' +
        '  <div class="mev-tick mev-req r4"></div>' +
        '  <div class="mev-tick mev-cur"></div>' +
        '</div>' +
        '<div class="mev-cap lf r1"><span class="mev-v"></span><i class="mev-ico mk mk1"></i></div>' +
        '<div class="mev-cap lf r2"><span class="mev-v"></span><i class="mev-ico mk mk2"></i></div>' +
        '<div class="mev-cap lf r3"><span class="mev-v"></span><i class="mev-ico mk mk3"></i></div>' +
        '<div class="mev-cap tp r4"><span class="mev-v"></span><i class="mev-ico bm"></i></div>' +
        // The MoE-% sits IMMEDIATELY BEFORE the numeral (after the delta), in flow: "+120 (73.84%) 1,850".
        // Never .mev-v -- capV() is a first-match querySelector.
        '<div class="mev-cap bt mev-capC"><span class="mev-d"><span class="mev-d-num"></span></span>' +
        '<span class="mev-pct">(<span class="mev-pct-num"></span>)</span>' +
        '<span class="mev-v"></span><i class="mev-ico dmg"></i></div>';

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
// `let`, not `const`, because goVertical() rebuilds the root's contents under the .mev- prefix and
// every ref has to be re-queried against the new nodes. Under a single orientation nothing rewrites
// them. `.mp-capC` (not the old `.mp-cap.up`) is the current caption's lookup on BOTH orientations:
// the vertical composition's equivalent role class is `bt`, not `up`, so the shared marker class is
// what makes one ns()-rewritten selector serve both.
let fill = root.querySelector(".mp-fill");
let tCur = root.querySelector(".mp-tick.mp-cur");
let reqTicks = [1, 2, 3, 4].map(function (i) { return root.querySelector(".mp-tick.r" + i); });
let reqCaps = [1, 2, 3, 4].map(function (i) { return root.querySelector(".mp-cap.r" + i); });
let capC = root.querySelector(".mp-capC");
let capD = capC.querySelector(".mp-d");
let capDN = capC.querySelector(".mp-d-num");
// The MoE-% group (gated on `pct >= 0`) and its digits. Horizontally the gated node is .mp-pct-t INSIDE
// the out-of-flow .mp-pct (which also holds the delta); vertically it is .mev-pct itself.
let capPct = capC.querySelector(".mp-pct-t");
let capPctN = capC.querySelector(".mp-pct-num");
// capC's per-caption dither strip (HORIZONTAL only): capC rides the axis, so JS tracks the strip's
// `left` to the caption's. goVertical() nulls it (V_MARKUP uses .mev-bd strips of its own instead).
let capCbd = root.querySelector(".mp-bd-5");

// ADOPT THE VERTICAL COMPOSITION -- the bar's half of MoEBarTransient's onVertical hook (the shared
// module owns the surface, the rigid shift, the run-identity pair and the body scope class). Called
// ONCE, inside engine.whenReady, BEFORE the surface push and before the first render, so nothing
// downstream ever sees the horizontal DOM. A mid-battle Orientation change re-mounts this document
// (Python closes and reopens the window -- battle_bridge.apply_settings) and comes straight back
// through here; there is deliberately no live re-composition path.
function goVertical() {
    PFX = "mev";
    AX = "bottom";
    GROW = "height";
    CAP_C_AX = null;                 // a STATIC bottom cap here -- see the profile note
    root.innerHTML = V_MARKUP;
    fill = root.querySelector(".mev-fill");
    tCur = root.querySelector(".mev-tick.mev-cur");
    reqTicks = [1, 2, 3, 4].map(function (i) { return root.querySelector(".mev-tick.r" + i); });
    reqCaps = [1, 2, 3, 4].map(function (i) { return root.querySelector(".mev-cap.r" + i); });
    capC = root.querySelector(".mev-capC");
    capD = capC.querySelector(".mev-d");
    capDN = capC.querySelector(".mev-d-num");
    capPct = capC.querySelector(".mev-pct");
    capPctN = capC.querySelector(".mev-pct-num");
    capCbd = null;                   // horizontal-only strip; the vertical bar uses .mev-bd instead
}

function capV(c) { return c.querySelector(ns(".mp-v")); }

// --- the pushed state ---------------------------------------------------------------------
// `cur` is the latest push; `last` is the previous one. `last === null` means "no baseline yet":
// the FIRST push after mount (and after any re-show) seeds the latch silently, so the bar does not
// appear at battle start. (There is deliberately no `rev` counter on EfficiencyVM -- the battle
// window is a private, always-compositing view and has never needed the garage's cold-mount signal.)
let cur = { damage: 0, barX: 0, band: 0, r: [0, 0, 0, 0], battleEpoch: 0 };
let last = null;

// --- THE DELTA LATCH (derived HERE; EfficiencyVM carries no damageDelta) --------------------
// `peak` is the HIGH-WATER mark of this battle's combined damage, deliberately NOT the previous
// push's value: combined damage SUBTRACTS team damage, so the total can move DOWN, and the latch
// must measure only the rise above the highest total already seen -- a friendly-fire dip followed
// by a hit reports the gain over the old peak, never the dip plus the hit. `delta` then PERSISTS
// until superseded, because an efficiency tick that moved nothing (a spot, a dip, an arena period
// change, an Alt press) must keep showing the increment the player is reading; 0 == none yet.
//
// A NEW HIGH-WATER MARK IS ALSO THE ONLY THING THAT MAY POP THE BAR OPEN (see `gained` in render).
// "The value changed" and "the player gained damage" are NOT the same event: team damage
// subtracting from the combined total changes the value, and re-showing the bar for it would
// re-flash an increment the player has already read, carrying no new information.
//
// `epoch` is the battleEpoch `peak`/`delta` belong to. Python bumps a monotonic counter once per
// battle mount (bridge/battle_bridge._battle_epoch) and pushes it on every efficiency tick, so a
// change in it IS the battle boundary -- there is no longer any inference from the total having
// restarted low (battle N+1's first tick can read higher than battle N's peak, and then an Alt peek
// early in N+1 rendered N's stale increment). It deliberately does NOT live in `last`: a hide drops
// that baseline mid-battle, while the latch has to survive one. 0 == the counter's value before the
// first battle, so the first push of the first battle resets an already-empty latch for free.
//
// NO COMPARISON MAY NAME `damage` ON ITS OWN LINE. tools/dev/check_efficiency_js.js scans the
// comment-stripped source for a comparison operator sharing a line with `damage` or an r* stop,
// because the rule it guards is that the `>=`-INCLUSIVE damage-vs-REQUIREMENT test lives in Python
// (domain.efficiency_band) and nothing here may re-derive it. This latch is damage-vs-damage and
// touches no requirement, so it reads the total into `total` first and compares THAT.
let peak = 0;
let delta = 0;
let epoch = 0;

// The delta's own fade-out timer -- this bar's ONLY animation state of its own. Everything else
// (arming, the run clock, the peek pause/seek, the end race, the surface settle) lives in the shared
// transient below.
let deltaT = null;

// The current caption may not leave the box: it is centred on its tick, but its glyph hangs off the
// left and its delta off the right, so at 100 % the delta would overflow. Reproduces the tuner's
// capLeft() (eff_bar_tuner.html:716-729) in meta.capClamp's rem corridor -- and .mp-cap's
// offsetWidth is the NUMERAL only (the icon and the delta are out of flow), which is why the larger
// of the two overhangs is added back, the icon's with its transform gap. A zero measured width
// (nothing laid out yet) simply degrades to no clamp.
//
// THE TWO SIZE FACTORS BOTH LAND HERE, and this is the ONE function on either bar where the
// 1rem == 1 logical px identity is load-bearing rather than incidental:
//   * every rem CONSTANT above is an x-length (the bar's width, the corridor's two bounds, the icon's
//     transform gap), so each takes SIZE_XF -- the corridor bounds included, since they are the
//     backdrop inset by an equal x-length each side and so scale with it;
//   * offsetWidth is MEASURED PX, and under the large mode's root font 1rem is SIZE_F px, so
//     every measurement is divided back into document rem. A caption's width in rem is unchanged by
//     the root font (its font-size is a rem too), which is exactly why this cannot be normalised
//     away: the corridor scales by SIZE_XF while the caption inside it does not.
function capClampPct(p) {
    const xf = large ? SIZE_XF : 1;
    const px = large ? SIZE_F : 1;
    const w = function (q) {
        const n = capC.querySelector(q);
        return ((n && n.offsetWidth) || 0) / px;
    };
    // The right overhang is the delta alone when the MoE-% is off (today's number), else the % box
    // plus the delta's gap and the delta hanging off the % (Option B: both out of flow). The %'s OWN
    // gap is NOT added here: it is .mp-pct-t's margin-left, so w(".mp-pct") already includes it (the
    // delta's gap is its translate, outside .mp-pct's box, so that one IS added).
    // `cur.pct >= 0` is the same gate paintStatic writes the display from.
    const right = cur.pct >= 0
        ? w(".mp-pct") + PCT_GAP_REM * xf + w(".mp-d")
        : w(".mp-d");
    // ASYMMETRIC: each bound reserves only the overhang on ITS side (icon on the left, % + delta on
    // the right). One shared max() let the % reach inflate the left bound and shoved the numeral
    // off its tick at low damage.
    const half = (capC.offsetWidth || 0) / 2 / px;
    const lo = CLAMP_L_REM * xf + half + w(".mp-ico") + ICO_GAP_REM * xf;
    const hi = CLAMP_R_REM * xf - half - right;
    let x = p / 100 * BAR_W_REM * xf;
    if (lo <= hi) x = Math.max(lo, Math.min(hi, x));
    return x / (BAR_W_REM * xf) * 100;
}

// Position the fill, the moving tick and its caption from the PUSHED barX (never recomputed here).
// No rewind/snap variant and no transition suppression, unlike MoEProgress.setPos: this bar has a
// single set of values, so the CSS's 400ms fill/left transitions may always run -- exactly what the
// tuner's own hit() does. On a cold entry they run under the 600ms fade-in and are invisible.
// THE AXIS IS A PAIR OF PROPERTY NAMES, not two code paths: GROW is the fill's growth property
// (`width` horizontally, `height` vertically -- 0% at the BOTTOM) and AX the current tick's position
// property (`left` / `bottom`). CAP_C_AX is null on the vertical composition, where the current
// caption is a static readout below the track's bottom end -- so capClampPct, whose whole job is
// keeping a MOVING caption inside a horizontal corridor, is not reached there at all.
function setPos(x) {
    const p = x.toFixed(3) + "%";
    fill.style[GROW] = p;
    tCur.style[AX] = p;
    if (CAP_C_AX) capC.style[CAP_C_AX] = capClampPct(x).toFixed(3) + "%";
    if (capCbd) {   // strip behind the moving caption
        // 150 backs the % (+-75; overhangs a few rem at 100.00%), 90 is the %-off width; both x-lengths (Large == SIZE_XF). The
        // centre never lets the strip's own edge cross the surface's left edge (BOX_LEFT*xf - PAD).
        const xf = large ? SIZE_XF : 1;
        const sw = (!(cur.pct >= 0) ? 90 : 150) * xf;
        const c = Math.max(capClampPct(x) / 100 * BAR_W_REM * xf, BOX_LEFT_REM * xf - PAD_REM + sw / 2);
        capCbd.style.width = sw + "rem";
        capCbd.style.left = (c / (BAR_W_REM * xf) * 100).toFixed(3) + "%";
    }
}

// Everything that does NOT animate: the four requirement numerals, which of them are met, the band
// class and the 100 % pulse, and the current numerals. Safe to re-run on every push.
// `.met` AND the band come off the PUSHED `band` index -- stop i (1-based) is met iff i <= band.
// That is not a shortcut: it is how the `>=`-inclusive rule stays in Python only.
function paintStatic() {
    for (let i = 0; i < 4; i++) {
        capV(reqCaps[i]).textContent = fmt(cur.r[i]);
        reqTicks[i].classList.toggle("met", i + 1 <= cur.band);
    }
    BAND_CLASSES.forEach(function (c, i) { root.classList.toggle(ns(c), i === cur.band); });
    // The pulse rule is #moe-bar-root.mp-b-au.mp-pulse .mp-track, so this class is inert off gold
    // anyway -- gate it on the band regardless, so the DOM says what it means.
    root.classList.toggle(ns("mp-pulse"), cur.band === 4);
    capV(capC).textContent = fmt(cur.damage);
    capDN.textContent = (delta > 0 ? "+" : "") + fmt(delta);
    // THE MoE-% (VM `damagePercent`), persistent -- unlike the delta's 1.6s flash. Python folds the
    // "Show MoE %" setting AND no-data into the -1.0 sentinel, so the ONE `>= 0` test covers both; an
    // ABSENT field is NaN, also false.
    capPct.style.display = cur.pct >= 0 ? "" : "none";
    capPctN.textContent = pctText(cur.pct);
    // THE DELTA "+N" (VM `showDelta`): FEATURE switch, `!== false` so an ABSENT field stays shown. Off
    // = display:none (no space, never flashes); independent of the % gate above.
    capD.style.display = cur.showDelta !== false ? "" : "none";
}

// The delta SNAPS in on a hit, holds for its own DELTA_HOLD_MS, then fades out on .mp-d's 500ms
// opacity transition. The snap is the shipped cancel idiom (transition:none -> set -> force a
// reflow -> hand the transition back) so the appearance is instant AND a half-finished fade from
// the previous hit can never bleed into this one. Ported from the tuner's showDelta()
// (eff_bar_tuner.html:736-741). Only a GAIN (a new high-water mark) calls this -- an Alt peek, a
// flat tick and a team-damage dip all show the latched numerals without re-flashing an increment
// that already had its moment.
function showDelta() {
    clearTimeout(deltaT);
    capD.style.transition = "none";
    capD.classList.add("on");
    void root.offsetWidth;
    capD.style.transition = "";
    deltaT = setTimeout(function () { capD.classList.remove("on"); }, DELTA_HOLD_MS);
}

// THE TRANSIENT. Everything shared with MoEProgress.js -- arming and its negative-delay debounce,
// the run clock, the Alt peek's pause/plateau-seek/resume, the animationend-vs-timer end race, the
// surface push + re-assert. This bar needs only ONE of the hooks: a tail on endRun/reset to drop the
// delta, so a hold longer than the transient cannot leave it showing on the next entry.
// NO onRewind and NO onCommit: unlike the Moving Average bar this one has a single set of values, so
// there is nothing to rewind before a cold entry and nothing to commit after it -- the CSS's 400ms
// fill/left transitions may always run, exactly as the tuner's own hit() does (see setPos).
const T = createTransient({
    root: root,
    boxLeft: BOX_LEFT_REM,
    boxTop: BOX_TOP_REM,
    boxW: BOX_W_REM,
    boxH: BOX_H_REM,
    pad: PAD_REM,
    clipB: CLIP_B_REM,
    onEnd: dropDelta,
    onIdle: dropDelta,
    // THE VERTICAL COMPOSITION. `cls` is the body scope class MoEEfficiencyVertical.css hangs off AND
    // the key to that stylesheet's own re-trigger keyframe twin (MoEBarTransient's RUN_CLASSES_V);
    // `box` replaces the four box* arguments above. Adopted at mount iff the model's `vertical` is
    // true, which then calls goVertical above for the DOM half.
    vert: { cls: "mev", box: [V_BOX_LEFT_REM, V_BOX_TOP_REM, V_BOX_W_REM, V_BOX_H_REM],
            clipB: V_CLIP_B_REM, padX: V_PAD_X_REM,
            padXR: V_PAD_XR_REM, padXRLarge: V_PAD_XR_REM_LARGE },
    onVertical: goVertical,
});

function dropDelta() {
    clearTimeout(deltaT);
    capD.classList.remove("on");
}

function render(model) {
    // Truthy guards, not `=== false`: a root VM whose flags are still undefined before Python's
    // first push must stay hidden, not paint a zero-width bar over the HUD. hasData false means the
    // per-tank threshold table gave no usable five-stop axis -- there is nothing to plot. (Note the
    // documented asymmetry: the battle path has no offline estimator fallback, so on a tank whose
    // WG fetch failed this stays blank while the garage bar still draws. Not a bug here.)
    if (!model || !model.visible || !model.hasData) {
        root.style.display = "none";
        T.reset();
        // Drop the change-detect baseline too, so a later re-show starts COLD and the next push
        // becomes a fresh silent one (a scoreboard opening and closing must not replay the bar).
        // `peak` / `delta` deliberately SURVIVE -- render()'s first-push branch re-seeds them.
        last = null;
        return;
    }
    root.style.display = "";
    // The pushed size mode (mod_settings.progress_bar_size), BEFORE setPos: capClampPct reads it. The
    // transient owns the rest of the flag (the root-font write, the .mp-lg body class, the re-derived
    // surface) and is idempotent, so this is just "keep it in sync".
    large = Number(model.barSize) === 1;
    T.size(large);
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
        damage: Number(model.damage) || 0,
        barX: Number(model.barX) || 0,
        // Clamped defensively to the classes that exist -- an out-of-range index would otherwise
        // leave the root with NO band class and an unstyled (invisible) fill.
        band: Math.max(0, Math.min(BAND_CLASSES.length - 1, Number(model.band) || 0)),
        r: [Number(model.r65) || 0, Number(model.r85) || 0,
            Number(model.r95) || 0, Number(model.r100) || 0],
        battleEpoch: Number(model.battleEpoch) || 0,
        // The MoE % this battle's damage alone is worth (-1.0 == off / no data). BARE, NO `|| 0`:
        // 0.0 is a real percentile and an absent field must not collapse into it.
        pct: Number(model.damagePercent),
        // The per-bar show-delta switch, RAW (`!== false` in paintStatic).
        showDelta: model.showDelta,
    };

    const first = last === null;
    last = cur;

    // The latch (see `peak`), run BEFORE paintStatic because that is what writes the numeral. The
    // two reset cases are told apart by the PUSHED epoch, not inferred from the total:
    //   * a re-show MID-BATTLE (a scoreboard closing, hasData arriving) -- same epoch, so the mark
    //     is re-seeded off the current total (nothing is claimed for damage dealt while this
    //     document was not watching) and the latched increment survives, exactly as the Python
    //     latch survived a hide;
    //   * a NEW BATTLE -- a different epoch, so the previous battle's increment is dropped, which is
    //     what _on_mount_refresh used to do. Deliberately 0 and not "the whole accumulated total as
    //     one increment": the first tick of a battle is not a hit.
    // `gained` is the SHOW/FLASH trigger and only a new high-water mark sets it -- a flat push or a
    // dip repaints below (paintStatic/setPos always run) but must not pop the bar or re-flash.
    const total = cur.damage;
    const newBattle = cur.battleEpoch !== epoch;
    epoch = cur.battleEpoch;
    let gained = false;
    if (newBattle) delta = 0;
    if (first || newBattle) {
        peak = total;
    } else if (total > peak) {
        delta = total - peak;
        peak = total;
        gained = true;
    }

    paintStatic();
    setPos(cur.barX);

    // THE SHOW TRIGGER IS GATED ON T.settled(); the silent baseline above is NOT. Before the
    // re-assert the surface is the engine's 256x256 fallback: the bar would come up cropped and
    // badly mis-placed (see the shared module's SURFACE_REASSERT_MS). The baseline shows nothing, so
    // it costs nothing to let it run -- and it MUST run, or `last` never gets recorded and the first
    // real hit is missed. T.show() picks warm-vs-cold off its own `showing`.
    //
    // ALSO GATED ON `showEvents` (mod_settings.progress_show_events, with "Always" already folded in
    // Python). `!== false`, NOT `!!`: a model without the field (a pre-push frame, a harness
    // fixture) must degrade to the SHIPPED behaviour, which is "a hit raises the bar". The delta
    // caption rides the same gate -- with the bar staying down there is nothing to flash. "Alt
    // Press" and "Always" need no branch here: both arrive folded into `altHeld` below.
    if (gained && model.showEvents !== false && T.settled()) {
        if (cur.showDelta !== false) showDelta();
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
