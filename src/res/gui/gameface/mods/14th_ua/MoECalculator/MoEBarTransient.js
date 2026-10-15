// 14th_ua's MoE Calculator -- the SHARED transient machinery behind both centre-screen in-battle
// bars (MoEProgress.js = Moving Average, MoEEfficiency.js = Damage Efficiency). Everything in here
// was byte-identical in the two files; only the values each bar animates were ever different.
//
// The two bars are radio ALTERNATIVES -- Python opens exactly one -- but they are SEPARATE Gameface
// DOCUMENTS, so this module is instantiated twice with no cross-talk: every piece of state below is
// a closure local of createTransient(), never a module-level variable. (Both documents already
// import ../../libs/model.js, so module resolution across this directory is proven.)
//
// EVERY BEHAVIOUR HERE COST A CLIENT RELAUNCH TO FIND. Do not "simplify" any of them:
//   * the negative-`animation-delay` debounce (armRun's seek) -- mp-life bakes fade-in, hold and
//     fade-out into ONE both-filled keyframe, so its hold CANNOT be extended in place;
//   * holding a peek open by pausing `animationPlayState` and, on release, seeking -3600ms;
//   * ...and, for exactly that reason, the CONFIGURABLE hold is a CORRECTION to the keyframe's own
//     deadline (holdFrom), NEVER a replacement for it: at the default it does NOTHING, so the run
//     stays byte-for-byte the shipped one -- ONE identity, ended by its own animationend. Do NOT
//     "unify" that into always-pause-then-re-arm: that costs every ordinary auto-hide an extra
//     mp-run/mp-run-b flip mid-run (a flicker risk, and 11 red assertions in
//     tools/dev/check_progress_js.js). Do NOT scale `animation-duration` either -- mp-life's stops
//     are PERCENTAGES, so that stretches the fades too;
//   * deriving the peek phase from ELAPSED TIME (plateauAt + HOLD_MS), never from a `showing` flag
//     -- `showing` stays true through the whole fade-out, so a flag-based branch pins the bar at
//     partial opacity;
//   * the mp-run <-> mp-run-b identity alternation, so consecutive runs never share an
//     animation-name for the engine to coalesce a restart with -- and each VERTICAL composition
//     carries its own twin of that pair (mpv-run / mev-run, see RUN_CLASSES_V), because the two
//     vertical stylesheets are namespace-disjoint from the horizontal ones;
//   * the fallback end timer, without which one missing animationend wedges `showing` true forever
//     and the bar shows once and never again;
//   * the POST-DEADLINE surface re-assert -- the engine's default-view-size fallback runs LAST and
//     WINS, so only a late re-assert puts the surface right (see SURFACE_REASSERT_MS).
// The rewind before a COLD show, and the value commit after one, are the two things that DO differ
// between the bars: they are the onRewind / onCommit hooks, not flattened away. The ORIENTATION is
// the third: this module owns the surface/shift/run-identity half of the vertical composition
// (cfg.vert + goVertical) and the bar owns the DOM half (onVertical), because only the bar knows
// its own markup.
//
// The battle windows have NO hot-reload (they pin their resources at client launch), so every tweak
// here costs a full client relaunch: tune in the browser, not in the client.

// --- the transient's timings, from the bars' CSS trailing JSON `meta` blocks -------------------
// Kept as constants rather than read from the CSS: Gameface gives no reliable way to read a
// keyframe's stops, and these numbers ARE the contract with BOTH stylesheets (whose mp-life is
// identically tuned). If a timing changes in a tuner, change it here too.
// Declared as bare `const` and re-exported below so a plain `^const NAME = <int>;` scrape still
// finds them (the mirror tests and the dev harnesses read these out of the source text).
const FADE_IN_MS = 600;              // meta.fadeInMs == the 9.68% keyframe stop of mp-life
const HOLD_MS = 5000;                // meta.holdMs -- the BAKED hold. The LIVE one is the closure's
                                     // `holdMs` (see applyHold): user-configurable, JS-driven, and
                                     // defaulting to exactly this. HOLD_MS stays the keyframe's own
                                     // contract, so SEEK_FADE_OUT below is still the 90.32% stop.
const FADE_OUT_MS = 600;             // meta.fadeOutMs (== fadeInMs in both tuned JSONs)
const TOTAL_MS = FADE_IN_MS + HOLD_MS + FADE_OUT_MS;   // meta.totalMs == mp-life's own 6200ms

// How far to seek INTO mp-life, in ms, when arming a run (armRun turns these into a NEGATIVE
// animation-delay, which starts the animation already that far along without replaying its entry).
// Verified against the emitted keyframes (@keyframes mp-life): the stops are 0 / 9.68 / 90.32 / 100
// of a 6200ms animation, i.e. 0 / 600.16 / 5599.8 / 6200 ms.
//   600  == the 9.68% stop (within 0.2ms): opacity 1 and translateY(0rem) both COMPLETE, so the bar
//           sits exactly at the hold plateau and does not re-flash or re-slide.
//   5600 == the 90.32% stop: the instant the fade-out begins.
const SEEK_NONE = 0;
const SEEK_PLATEAU = FADE_IN_MS;
const SEEK_FADE_OUT = FADE_IN_MS + HOLD_MS;

// --- THE RE-ASSERT: LOAD-BEARING, DO NOT DELETE ---------------------------------------------
// Live-measured: the engine's size-calculation deadline expired ~2.2s after the view loaded
// (resizeViewRem at 04.8s; the `Size calculation timeout` + its "Set the default view size" action
// at 06.2s, clobbering the pushed size back to the 256x256 default -- THE FALLBACK RUNS LAST AND
// WINS, which is why pushing the size earlier can never help). A static in-flow #moe-bar-box does
// NOT satisfy the engine's measurement; that premise was tested and DISPROVEN. So this re-assert is
// the ONLY thing that puts the surface right, and it is permanent. 4000ms is comfortably past the
// observed ~2.2s.
// It is load-bearing TWICE: `settled` flips off the back of it, because the re-assert IS the event
// that makes the surface correct. Before it the surface is the 256x256 fallback -- which CLIPS the
// composition and, since Python's anchor_centred_reduced computes its term from the real surface
// height (domain/constants.*_ANCHOR_Y_SHIFT), places the bar far too high. Delete either half and
// the bug comes back.
const SURFACE_REASSERT_MS = 4000;
// Slack between the re-assert and letting the bar show. The resize round-trips through C++
// (Window._cResized -> onSizeChanged -> bridge/bar_window._place re-reads the movable extent), so
// the surface is only correct -- and the window only re-placed -- a beat AFTER the push. 250ms is
// far more than an engine callback needs and is not user-visible: it lands ~4.25s into a battle,
// inside a window where nothing shows anyway.
const SURFACE_SETTLE_MS = 250;

// --- THE COLD-MOUNT POLL: LOAD-BEARING, DO NOT REVERT TO A ONE-SHOT ---------------------------
// Live-measured (watcher log, fresh session's first battle): the Python push that flips
// `visible`/`hasData` true can land ~27s after mount -- long after SURFACE_REASSERT_MS +
// SURFACE_SETTLE_MS's one settle point (~4.25s) -- and observer.onUpdate(render) does NOT
// reliably re-deliver that late push to render() for this private always-composited battle
// window. A one-shot post-settle render can therefore fire, find the model still not ready
// (render()'s early return, before it ever reaches T.peek()), and then nothing re-renders again
// until the user presses Alt (which reveals the bar through a separate force-push path -- that is
// why Alt "fixes" it by hand). So the settle callback below polls the LIVE observer.model (which
// stays current even while onUpdate is dormant -- same premise as MoECalculator.js's garage
// cold-mount poll) until the bar actually reveals, instead of rendering it once and hoping.
// ponytail: a bounded, SELF-STOPPING poll -- COLD_POLL_MS interval, capped at
// COLD_POLL_CEILING_MS total (a `visible` that never arrives -- feature off, spectating, no data
// -- must not poll forever). Each battle window is its own short-lived document torn down with
// the window at arena teardown, so there is no separate unmount hook to also cancel this from;
// the ceiling is the only leak guard.
const COLD_POLL_MS = 500;
const COLD_POLL_CEILING_MS = 60000;

// Margin on the fallback end timer so it always LOSES to a working animationend (which fires at
// exactly the run's remaining duration). Not a tuned CSS value -- pure slack.
const END_MARGIN_MS = 250;

// THE SURFACE RECT IS THE MOUSE HIT RECT -- exactly why WindowFlags.WINDOW_FULLSCREEN was rejected
// for these windows (bridge/battle_view.py). A surface spanning most of screen centre would be an
// input-stealing strip, and these bars are purely decorative and must never take input. So collapse
// the input rect to nothing, PERMANENTLY -- this document needs no mouse input at ALL any more: the
// Ctrl+drag reposition is driven entirely from Python (adapter/battle_input samples the keys,
// bridge/bar_window re-places the window from the live cursor), so the rect that used to be OPENED
// for the gesture never opens again. Confirmed against WG's own JS wrapper (gui-part3.pkg
// battle/battle_notifier/BattleNotifierView/BattleNotifierView.js), against a LIVE decompile, not
// just this file's own memory of one:
//   * the order is (top, right, bottom, left, 15) -- CONFIRMED;
//   * WG's own wrapper passes FOUR EQUAL VALUES, always -- so arg order is MOOT there, and matters
//     here only if the four are NOT equal;
//   * an OVERSIZED padding is ACCEPTED, not rejected -- a real capture logged 240 accepted against a
//     92-tall surface. NEGATIVE values are what gets rejected, not an oversized positive one.
// ONE SHARED VALUE ACROSS ALL FOUR SIDES, per that recorded design -- NOT a per-axis pair. A prior
// revision of this file split hitPad into hitPadX/hitPadY on the theory that `Math.ceil(Math.max(
// viewW, viewH) / 2)` on all four sides "over-pads the smaller axis into a negative extent instead
// of the exact zero a real collapse needs" -- but per the CONFIRMED behaviour above, an oversized
// (or negative-implying) padding is exactly what WG's own wrapper already ships and the engine
// already accepts; the "exact zero" the split chased was never necessary, and splitting it
// reintroduced two risks the uniform value never had: sensitivity to the (top, right, bottom, left)
// ARGUMENT ORDER (moot when all four are equal, live when they differ) and sensitivity to WHICH
// AXIS'S size the pad happens to be derived from at push time. `Math.ceil(Math.max(viewW, viewH) /
// 2)` on all four sides collapses BOTH axes to nothing, is immune to the argument order, and is the
// smaller diff. Revert target if this file's hit collapse is ever found not to hold at runtime.
// HIT_MAGIC mirrors WG's constant (its own wrapper always passes this literal 15 too); its meaning
// is unknown, so the call is retried without it if the 5-argument form is rejected.
const HIT_MAGIC = 15;

// --- THE "LARGE" SIZE MODE (mod_settings.progress_bar_size, pushed as the VM's `barSize`) -----
// TWO factors, one per axis, and they are the only two numbers the whole feature has. Defined HERE,
// once, for both bars (Python's half is the two *_ANCHOR_Y_SHIFT_LARGE constants).
//
// SIZE_F IS DELIVERED BY THE ROOT FONT SIZE AND NOTHING ELSE. The rem->px factor in Gameface IS the
// root font size, and WG's own bootstrap (gui/gameface/js/index.js) ends by writing it from
// `self.onScaleUpdated` -- a bootstrap our REGISTERED views never load, which is exactly why every
// comment in this mod asserts 1rem == 1 logical px. So one write of `base * SIZE_F` re-lays the whole
// composition 1.25x larger, CRISPLY (a real reflow, not a bitmap upscale), and leaves every %, em,
// `contain`, gradient stop and derived icon background-size ratio correctly untouched: height, fonts,
// icon boxes, glow radii, vertical gaps and mp-life's slide all scale with NO CSS edit at all.
// SIZE_XF is what is left over: an x-length must reach 5/3 TOTAL, and the root font already gives it
// SIZE_F, so the stylesheets' one appended `.mp-lg` block re-declares ONLY the x-lengths, multiplied
// by this. 1.25 * 4/3 == 5/3 exactly (~1.667x -- was 1.5 * 4/3 == 2x before the Large mode was
// eased off a pure 1.5x/2x scale-up).
// THE ENGINE APIs ARE NOT AFFECTED BY OUR ROOT FONT: resizeViewRem / setHitAreaPaddingsRem are C++
// and take logical px, so their arguments carry BOTH factors (see applySize). The CSS `left`/`top`
// rigid shift stays in rem and self-scales, which is why shiftY needs no term at all.
const SIZE_F = 1.25;
const SIZE_XF = 4 / 3;



// Two interchangeable arming classes, each bound to its OWN identically-tuned @keyframes (the
// second is each stylesheet's marked HAND-ADDED mp-life-b block), so consecutive runs never share
// an animation-name and the engine has nothing to coalesce a restart with.
//
// THE VERTICAL COMPOSITIONS CARRY THEIR OWN PAIR, and it is PER BAR rather than one shared vertical
// pair: the two vertical stylesheets are namespace-disjoint from the horizontal ones by design
// (.mpv-* on MoEProgressVertical.css, .mev-* on MoEEfficiencyVertical.css -- the horizontal pair
// shares .mp-* only because each registered view is its own document), so each emits its own twin
// under its own prefix. Both orientations' keyframes are IDENTICALLY tuned -- same 6200ms, same
// four stops, same 20rem translateY slide -- which is why one set of timing constants above serves
// all four and no bar owes a second clock. The horizontal pair below is the shipped default; a bar
// supplies its vertical pair through cfg.vert.run / cfg.vert.life (see createTransient).
const RUN_CLASSES = ["mp-run", "mp-run-b"];
const RUN_NAMES = ["mp-life", "mp-life-b"];
// KEYED BY THE VERTICAL STYLESHEET'S OWN SCOPE CLASS (cfg.vert.cls), so a bar names its prefix
// exactly once and nothing here needs a second discriminator.
const RUN_CLASSES_V = { mpv: ["mpv-run", "mpv-run-b"], mev: ["mev-run", "mev-run-b"] };
const RUN_NAMES_V = { mpv: ["mpv-life", "mpv-life-b"], mev: ["mev-life", "mev-life-b"] };

// Group an integer with thousands separators: 2910 -> "2,910". The tuners' fmt() at their tuned
// `comma` separator (MoEBattle.ttf carries "," and space, so both were shippable).
function fmt(n) {
    n = Math.round(Number(n) || 0);
    const sign = n < 0 ? "-" : "";
    return sign + String(Math.abs(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// Percentile -> "73.84" + "%" (two decimals, TRUNCATED never rounded -- MoEBattle.js's trunc2 /
// pctText, so the readout never overstates). "" for the no-data sentinel (-1), NaN and an absent
// field alike: `!(p >= 0)` is the one test, so the callers' bare Number(model.x) needs no `|| 0`.
function pctText(p) {
    if (!(p >= 0)) return "";
    const v = Math.floor(p * 100) / 100;
    return v > 0 ? v.toFixed(2) + "%" : "0%";   // 0 -> "0%", exactly MoEBattle.js's pctText
}

// Build one bar's transient controller.
//
//   root                          the bar's #moe-bar-root element (mp-life animates ITS transform)
//   boxLeft/boxTop/boxW/boxH      the composition's bounding box in document rem (== .mp-backdrop)
//   pad                           slack for the shadow/glow bleed, on all four sides
//   padX                          OPTIONAL, default `pad`. The X-AXIS slack, when the ink reaches
//                                 further sideways than the box does and `pad` alone would clip it.
//                                 Only the vertical Moving Average bar needs one (its captions are
//                                 right-anchored and grow LEFTWARD past .mpv-backdrop by design --
//                                 the backdrop deliberately does not cover them), so it is supplied
//                                 as `vert.padX`; everything else leaves padX == pad and the
//                                 four-sided-uniform derivation is unchanged byte-for-byte.
//                                 IT IS ONE VALUE FOR BOTH SIDES, DELIBERATELY, and that is not a
//                                 simplification -- it is the guarantee. The centred (Damage Log)
//                                 anchor is `max_x // 2` in Python with NO x term at all
//                                 (positioning.anchor_centred_reduced), which centres the SURFACE
//                                 and therefore only centres the BAR while the surface brackets the
//                                 track evenly. A per-side pad would let a caller silently slide
//                                 every centred placement by half the asymmetry; this shape cannot
//                                 express that. Pay the unused slack on the other side instead --
//                                 the surface rect is invisible (the hit rect is collapsed to
//                                 nothing off `Math.max(viewW, viewH)`, unconditionally, regardless
//                                 of which axis padX widens), so a wider surface costs literally
//                                 nothing.
//                                 It is an X length like `pad` and, like `pad`, it does NOT carry
//                                 SIZE_XF: it is a rem-space allowance for rem-sized caption INK,
//                                 which the root font already scales by SIZE_F alone.
//   padXR/padXRLarge              OPTIONAL, default `padX`/`padXR`. The RIGHT-side twin of `padX`,
//                                 for a composition whose two sides need DIFFERENT slack -- so far
//                                 only the two VERTICAL, Minimap-anchored bars, whose left side
//                                 carries the caption ink (padX, above) while their right side faces
//                                 the minimap and needs only cover the TRACK's own tick overhang, not
//                                 the ink. Unlike `padX`, splitting this one is SAFE precisely because
//                                 it is never paired with the centred (Damage Log) anchor's `max_x //
//                                 2` (positioning.anchor_centred_reduced has no X term and needs the
//                                 surface symmetric to stay centred on the track -- see padX's own
//                                 note); the Minimap anchor (positioning.anchor_minimap) reads
//                                 `edge_x` off the LEFT side alone (padX, boxLeft, trackW) and has no
//                                 term for the surface's overall width at all, so shrinking the RIGHT
//                                 side moves nothing the placement math depends on and the bar does
//                                 not move on screen. May be NEGATIVE (and, for both shipped bars,
//                                 is): the composition's own backdrop bleeds further right than the
//                                 track needs, and a negative padXR clips that decorative bleed at the
//                                 surface edge exactly the way `clipB` already clips the bottom bleed
//                                 -- see domain/constants.py's *_MM_TRACK_X note and the bars' own V_
//                                 PAD_X_REM notes for the numbers. `padXRLarge` exists because the
//                                 target it has to hit (the Python-side `edge_x` it must clear) is
//                                 itself a hand-corrected, not purely `*SIZE_XF`-scaled, number at
//                                 Large -- so, like MM_TICK_OVERHANG_LARGE, it is its own literal.
//   clipB                         OPTIONAL, default 0. Rem of the box's BOTTOM that the surface
//                                 deliberately does NOT cover, i.e. how much backdrop bleed is
//                                 CLIPPED at the surface's bottom edge. The ONE asymmetry in an
//                                 otherwise four-sided-uniform `pad`, and it exists because the
//                                 engine clamps every window into [0, space - surface] in compiled
//                                 C++ (see bridge/bar_window's _extent, which DEPENDS on that
//                                 clamp): the surface's bottom edge can therefore never go below the
//                                 screen's, so the ONLY way to bring a bottom-anchored composition
//                                 closer to the screen's bottom edge is to make its surface shorter.
//                                 Both VERTICAL compositions use it (their tuners' approved look has
//                                 the backdrop's lower bleed hanging off the stage bottom); the
//                                 horizontal pair leaves it 0 and keeps the plain box + 2*pad.
//                                 It is a Y length, so it carries SIZE_F alone via applySize's `f`
//                                 and NEVER SIZE_XF. It never touches `shiftY`, so the composition
//                                 does not move inside its surface and the mirrored Python constants
//                                 (VERTICAL_ANCHOR_Y_SHIFT, MM_TRACK_Y) are UNCHANGED by it.
//   onRewind(atCurrent)           OPTIONAL. Called inside a cold show, BEFORE the run is armed, to
//                                 write the values the entry opens with (transitions suppressed).
//                                 `atCurrent` true == the Alt entry: open ALREADY committed.
//   onCommit(cold)                OPTIONAL. Called after a DAMAGE-driven cold show and after every
//                                 warm re-trigger, to retarget the animated values. `cold` says
//                                 which -- NOT cosmetic: after a cold show the run class was just
//                                 added and onRewind wrote a resting value, so the new target must
//                                 land in a LATER frame (requestAnimationFrame); a warm re-trigger
//                                 rewound nothing and sets it synchronously.
//   onEnd()                       OPTIONAL. endRun's force-settle tail.
//   onIdle()                      OPTIONAL. reset's tail (the resting/hidden state).
//   vert                          OPTIONAL. THE VERTICAL ORIENTATION'S composition, adopted once at
//                                 mount iff the model's `vertical` is true (see goVertical):
//                                   cls    the vertical stylesheet's scope class, put on the BODY
//                                          ("mpv" / "mev"); also the key into RUN_CLASSES_V above
//                                   box    [left, top, w, h] -- that composition's own bounding box
//                                          in document rem, replacing the horizontal box* args
//                                   clipB  OPTIONAL, that composition's own bottom clip (see the
//                                          `clipB` arg above), replacing the horizontal 0
//                                   padX   OPTIONAL, that composition's own X-axis slack (see the
//                                          `padX` arg above), replacing the horizontal `pad`
//                                   padXR/padXRLarge  OPTIONAL, that composition's own RIGHT-side
//                                          slack (see the `padXR`/`padXRLarge` arg above)
//                                 A bar without it is horizontal-only and reads `vertical` never.
//   onVertical()                  OPTIONAL, and only called if `vert` was adopted: the bar's own
//                                 half of the switch (rebuild the DOM under the vertical prefix,
//                                 repoint the cached element refs, flip its axis properties). Runs
//                                 AFTER the geometry is re-derived and the scope class is on the
//                                 body, but BEFORE the surface is pushed and before the first
//                                 render, so nothing downstream ever sees the horizontal DOM.
//
// Returns { mount, settled, show, peek, ctrl, size, anim, hold, reset, disarm }.
export function createTransient(cfg) {
    const root = cfg.root;
    const nop = function () {};
    const onRewind = cfg.onRewind || nop;
    const onCommit = cfg.onCommit || nop;
    const onEnd = cfg.onEnd || nop;
    const onIdle = cfg.onIdle || nop;
    const onVertical = cfg.onVertical || nop;

    // --- the surface, and the rigid shift into it ------------------------------------------
    // A Gameface view PUSHES its own size to C++ through the `viewEnv` global
    // (viewEnv.resizeViewRem(w, h), rem == logical px); a view that never calls it gets the
    // engine's default-size fallback (see SURFACE_REASSERT_MS). There is NO Python-side and NO
    // resource-declaration lever for this (bridge/bar_window.py). The surface is the composition's box plus
    // `pad` on all four sides MINUS `clipB` off the bottom (see the arg -- 0 for both horizontal
    // bars, non-zero for both vertical ones, and the ONE side that is not uniform), and the whole
    // composition is rigidly translated by `pad` so NOTHING sits at a negative coordinate -- an
    // origin overflow is clipped at ANY surface size. `clipB` deliberately does NOT enter shiftY:
    // the composition stays exactly where it is inside the surface and only the surface's BOTTOM
    // edge moves up, which is what makes the clip a pure clip and leaves every mirrored Python
    // constant alone.
    // `let`, not `const`, because of the large size mode (applySize re-derives the five that carry
    // a factor -- see it for the arithmetic) AND, for shiftY, because of the VERTICAL orientation:
    // goVertical swaps the whole composition box, and the vertical box is TALLER than it is wide
    // where the horizontal one is the reverse, so every one of these six moves. Under a single
    // orientation nothing rewrites them and they ARE the six expressions below.
    // NORMALISED ONCE, HERE, so every later `cfg.clipB` / `cfg.padX` read is a number: the
    // horizontal pair passes neither, and `2 * cfg.pad - undefined` is NaN, which would push a NaN
    // surface size. `padX` falls back to `pad`, which is what keeps `2 * padX` identical to the
    // `2 * pad` it replaces everywhere except the one composition that supplies its own.
    cfg.clipB = cfg.clipB || 0;
    cfg.padX = cfg.padX || cfg.pad;
    // `padXR`/`padXRLarge` default to symmetric (== padX / padXR), which is BYTE-IDENTICAL to the
    // old `2 * cfg.padX` for every composition that supplies neither -- see the arg note above.
    cfg.padXR = cfg.padXR || cfg.padX;
    cfg.padXRLarge = cfg.padXRLarge || cfg.padXR;
    let viewW = cfg.boxW + cfg.padX + cfg.padXR;
    let viewH = cfg.boxH + 2 * cfg.pad - cfg.clipB;
    let shiftX = cfg.padX - cfg.boxLeft;
    let shiftY = cfg.pad - cfg.boxTop;        // MIRRORED (negated) in Python as
                                              // domain/constants.*_ANCHOR_Y_SHIFT, and as
                                              // VERTICAL_ANCHOR_Y_SHIFT under cfg.vert
    // ONE SHARED PAD (see the header note above): half the LARGER of the two axes, on all four
    // sides -- an oversized value is accepted, not rejected, so this collapses both axes at once.
    let hitPad = Math.ceil(Math.max(viewW, viewH) / 2);

    // THE LIVE RUN IDENTITY PAIR. Horizontal by default; goVertical repoints both at the vertical
    // composition's own twin (see RUN_CLASSES_V / RUN_NAMES_V), which is what makes armRun's
    // alternation and the animationend name filter follow the orientation for free.
    let runCls = RUN_CLASSES;
    let runNames = RUN_NAMES;

    // THE LARGE SIZE MODE's state. `large` is the pushed flag; `baseFont` is the document's root
    // font-size as it was BEFORE we ever touched it, captured ONCE so repeated application cannot
    // compound (and never read back off our own inline write). 0 == not captured yet.
    let large = false;
    let baseFont = 0;

    // THE CTRL+DRAG's ONLY remaining state here: `ctrlHeld` is the pushed key state (VM `ctrlHeld`),
    // and all it does now is HOLD THE BAR UP while the key is down, so there is something on screen
    // to grab. The gesture itself is Python's end to end (adapter/battle_input +
    // bridge/bar_window.drag) -- this document has no mousedown/mousemove/mouseup listener, no
    // reverse command, and no delta to report.
    let ctrlHeld = false;

    // Animation state. `showing` = the bar is visibly up (running or peek-held). `peeking` = Alt is
    // held, so the bar is pinned at the hold plateau with no fade-out (`peekT` is that pause's
    // timer). `holdT` is a SEPARATE timer that only exists while a configured hold differs from the
    // keyframe's baked one -- see holdFrom, which is a no-op (and leaves this null) at the default.
    // `plateauAt` = the wall-clock
    // ms at which the running animation reaches (or reached) that plateau -- the ONLY thing the
    // peek needs to know about the animation's progress, since Gameface exposes no readable
    // playback position. `dmgPlateauAt` = the same instant for the most recent DAMAGE-driven show
    // (0 == none in flight). It is a RECORD, NOT A SECOND CLOCK: `plateauAt` stays the only run
    // clock, and this only says where the damage hold that a peek interrupted would have been, so
    // peekOff can RESUME it instead of truncating it. Only ever nonzero while `showing` is true --
    // both places that clear `showing` (endRun, reset) clear it too, or a release could resurrect a
    // show that already ended.
    // `settled` = the surface has been re-asserted and is the size we asked for, so the composition
    // is neither clipped nor mis-placed. Until then the bar must NOT be shown by ANY trigger.
    let settled = false;
    let peekT = null;
    let holdT = null;
    let showing = false;
    let peeking = false;
    let plateauAt = 0;
    let dmgPlateauAt = 0;

    // THE TRANSITION SWITCHES (mod_settings.progress_transitions_events / _manual, pushed as the
    // VM's transEvents / transManual -- the master is already ANDed in Python, so these two ARE the
    // effective flags). One per trigger AREA: an event show takes `animEvents`, an Alt peek takes
    // `animManual`. Default true == the shipped animated bar.
    //
    // `animated` is the LIVE RUN's copy, decided AT ARM TIME by the area that triggered it and then
    // kept for the whole run, so the EXIT follows the same switch as the entry (an event hold that a
    // peek interrupted still exits the event's way -- see peekOff's resume branch). Un-animated is
    // NOT a second code path: the entry simply arms at SEEK_PLATEAU (already opacity 1 and
    // translateY(0), so there is nothing left to play) and the exit simply ends the run at the end of
    // the hold, where disarm()'s base #moe-bar-root{opacity:0} applies in the same frame.
    let animEvents = true;
    let animManual = true;
    let animated = true;

    // THE HOLD DURATION in ms (mod_settings.progress_hold_seconds * 1000, pushed as the VM's
    // `holdMs`). Read by holdFrom at the moment a hold STARTS, so a live settings change lands on
    // the next show instead of truncating a hold in flight. Defaults to the keyframe's OWN baked
    // HOLD_MS, which is what makes holdFrom a no-op -- and therefore the whole feature inert -- for
    // an unpushed model, an old harness fixture, and every user who never moves the slider.
    let holdMs = HOLD_MS;

    // The live run's id, and the last id already ended. endRun is idempotent on this pair:
    // whichever of animationend / the fallback timer arrives first wins and the other becomes a
    // no-op, and a timer left over from a superseded run can never end a newer one.
    // armIdx starts at 1 -> the first armRun flips to 0, i.e. run #1 uses the emitted
    // .mp-run / mp-life pair.
    let armIdx = 1;
    let runId = 0;
    let endedId = 0;
    let endT = null;

    function disarm() {
        root.classList.remove(runCls[0]);
        root.classList.remove(runCls[1]);
    }

    // ADOPT THE VERTICAL COMPOSITION -- called ONCE, from mount, and only when the model's
    // `vertical` says so. Everything it touches is the geometry the surface push and the rigid
    // shift are derived from, plus the run identity pair, plus the body scope class the vertical
    // stylesheet hangs off; the DOM half is the bar's own (onVertical).
    //
    // WHY MOUNT AND NOT MODULE SCOPE: `observer.model` is a live getter over the engine's
    // `window.model`, and the first moment it is guaranteed populated is inside engine.whenReady --
    // which is also the last moment before the surface is pushed, so this is the ONE point where the
    // flag is both readable and still early enough to matter. WHY ONCE: the composition is a DOM +
    // surface + stylesheet-scope switch, not a style; a mid-battle Orientation change is handled by
    // Python CLOSING and REOPENING the window (battle_bridge.apply_settings), which re-mounts this
    // document and comes straight back through here.
    // `cfg` is MUTATED rather than shadowed because applySize re-derives the same four values from
    // it on every Large flip -- leaving the horizontal box in cfg would silently restore it there.
    function goVertical() {
        cfg.boxLeft = cfg.vert.box[0];
        cfg.boxTop = cfg.vert.box[1];
        cfg.boxW = cfg.vert.box[2];
        cfg.boxH = cfg.vert.box[3];
        cfg.clipB = cfg.vert.clipB || 0;
        cfg.padX = cfg.vert.padX || cfg.pad;
        cfg.padXR = cfg.vert.padXR || cfg.padX;
        cfg.padXRLarge = cfg.vert.padXRLarge || cfg.padXR;
        viewW = cfg.boxW + cfg.padX + cfg.padXR;
        viewH = cfg.boxH + 2 * cfg.pad - cfg.clipB;
        shiftX = cfg.padX - cfg.boxLeft;
        shiftY = cfg.pad - cfg.boxTop;
        hitPad = Math.ceil(Math.max(viewW, viewH) / 2);
        runCls = RUN_CLASSES_V[cfg.vert.cls] || RUN_CLASSES;
        runNames = RUN_NAMES_V[cfg.vert.cls] || RUN_NAMES;
        try {
            // ON THE BODY, exactly like .mp-lg and for the same reason: the sizing shim
            // #moe-bar-box is a body-level SIBLING of the JS-created root, so a class on the root
            // could never scope a rule for it.
            document.body.classList.add(cfg.vert.cls);
        } catch (e) { /* fail-soft */ }
        onVertical();
    }

    // Start (or restart) mp-life, seeking `seekMs` into it. THE single arming point -- coldShow,
    // warmShow, peekOn and peekOff all funnel through here, so the restart idiom exists in exactly
    // one place. Every run gets a FRESH animation identity (alternating .mp-run / .mp-run-b) rather
    // than trusting remove -> reflow -> re-add to restart the SAME animation, an idiom never proven
    // in Coherent; the engine has nothing to coalesce the new run with. The reflow is kept anyway:
    // it costs nothing where it works. The fallback timer is armed for this run's own remaining
    // duration and calls the SAME endRun.
    function armRun(seekMs) {
        armIdx = 1 - armIdx;
        runId += 1;
        const id = runId;
        disarm();
        root.style.animationPlayState = "";
        root.style.animationDelay = seekMs ? "-" + seekMs + "ms" : "0ms";
        void root.offsetWidth;
        root.classList.add(runCls[armIdx]);
        clearTimeout(endT);
        // For an ANIMATED run this is the FALLBACK end timer: the run's own remaining duration plus
        // slack, so a working animationend always wins it. For an UN-ANIMATED one it is the REAL end
        // and must WIN, so it carries no margin and fires at the END OF THE HOLD instead --
        // SEEK_FADE_OUT is the 90.32% stop (the instant the fade-out begins), so SEEK_FADE_OUT -
        // seekMs is exactly the ms left until it. endRun's disarm() drops the run class there and the
        // base #moe-bar-root{opacity:0} applies the same frame, so the fade-out never plays; the real
        // animationend arriving later is a no-op through the endedId guard.
        // BOTH of those instants assume the keyframe's OWN baked hold. A configured hold that
        // differs re-targets them -- see holdFrom, which is the one place that corrects this and
        // which is a NO-OP at the default, so this line stays the whole story for the shipped bar.
        endT = setTimeout(function () { endRun(id); },
                          animated ? TOTAL_MS - seekMs + END_MARGIN_MS
                                   : Math.max(0, SEEK_FADE_OUT - seekMs));
        // THE run clock, maintained in ONE place so every arming path agrees: the seek makes the
        // run start `seekMs` in, so it reaches the plateau FADE_IN_MS - seekMs from now (in the past
        // for a seek past it). Gameface exposes no readable playback position, so this is how the
        // peek knows where the run is -- see peekOn. Only meaningful while the run is NOT paused
        // (wall-clock keeps running, the animation does not).
        plateauAt = Date.now() + FADE_IN_MS - seekMs;
    }

    // THE CONFIGURABLE HOLD, as a CORRECTION to the run mp-life already bakes -- deliberately NOT a
    // replacement for it. mp-life bakes fade-in + a HOLD_MS hold + fade-out into ONE both-filled
    // keyframe, so every armed run already leaves its hold at `plateauAt + HOLD_MS` (which is also
    // where armRun's un-animated endT lands). All this does is move that one instant to
    // `plateau + holdMs`, and it is the ONLY thing in the module that knows the hold is
    // configurable.
    //
    // THAT FRAMING IS LOAD-BEARING, NOT STYLE. An earlier build drove the hold entirely from JS --
    // pause EVERY run at its plateau and release it with an explicit armRun(SEEK_FADE_OUT) -- which
    // works, but cost every ordinary auto-hide an EXTRA .mp-run/.mp-run-b identity flip mid-run that
    // the shipped single-run path never had (a live flicker risk on the most common path, and 11
    // red assertions in tools/dev/check_progress_js.js). As a correction instead, `want === baked`
    // at the default and this function RETURNS HAVING DONE NOTHING: the shipped run plays start to
    // finish on one identity, ends on its own animationend, and the whole feature is inert until the
    // user actually moves the slider. That is not a "default uses the baked hold" special case --
    // it is the fixed point of "move the deadline to where it already is".
    //
    // LONGER  -> the keyframe would fade out too early, so PAUSE the run at its plateau (opacity 1
    //            and the slide both COMPLETE, so the pause is invisible) and release it at `want`.
    // SHORTER -> nothing to pause; just release early.
    // Either way the release is peekOff's own proven idiom (releaseHold), so a re-arm -- and its one
    // identity flip -- happens ONLY on a hold the user actually changed away from 5s. Resuming a
    // pause IN PLACE would avoid even that, but `animationPlayState = ""` on a PAUSED animation is
    // unproven in Coherent (peekOff has always re-armed rather than resume), so it is not used.
    //
    // `plateau` is the wall-clock instant the hold STARTS, never a duration -- which is what lets
    // peekOff resume an interrupted event hold at its ORIGINAL deadline (dmgPlateauAt) rather than
    // granting it a fresh one. `baked` is read off plateauAt (armRun's clock) rather than assumed,
    // so it is correct for ANY seek the run was armed with, including peekOff's resume seek.
    // The runId capture makes a correction from a superseded run a no-op, exactly like endT.
    function holdFrom(plateau) {
        clearTimeout(holdT);
        const baked = plateauAt + HOLD_MS;      // when THIS run's keyframe leaves the hold
        const want = plateau + holdMs;          // ...and when the setting says it should
        if (want === baked) return;             // the keyframe IS the hold -- nothing to correct
        const id = runId;
        const release = function () { if (id === runId) releaseHold(); };
        if (want < baked) {
            holdT = setTimeout(release, Math.max(0, want - Date.now()));
            return;
        }
        holdT = setTimeout(function () {
            if (id !== runId) return;
            root.style.animationPlayState = "paused";
            clearTimeout(endT);                 // a paused run never reaches its own end
            // While Alt is held the pause simply has no expiry -- peekOff is then the release, and
            // its resume branch calls back in here to re-apply the correction.
            if (!peeking) holdT = setTimeout(release, Math.max(0, want - Date.now()));
        }, Math.max(0, plateauAt - Date.now()));
    }

    // Leave the hold the way the LIVE RUN's `animated` says. Shared by holdFrom's correction and by
    // peekOff, so "the configured hold ran out" and "Alt was released" are one exit.
    // `inLeft` is how much of the ENTRY was still owed, mirrored back BEFORE the 90.32% stop so the
    // fade-out starts at the opacity the bar is already at. It is 0 for a hold correction (which
    // fires at or past the plateau by construction) and only ever nonzero for a release that beat
    // the pause -- THE PEEK IS STRICTLY HOLD-TO-SHOW, including a sub-FADE_IN_MS tap. (An earlier
    // build bailed on `animationPlayState !== "paused"` instead, which re-armed nothing, so a tap
    // served the whole transient and read as a toggle-on with a 5s auto-hide.) COSMETIC,
    // DELIBERATELY NOT FIXED: the mirror is linear while both fade halves are ease-in, so a release
    // mid-fade-in can step opacity by up to ~0.2 -- only reachable on that same barely-visible tap.
    function releaseHold() {
        // Un-animated: end it outright rather than arming a fade-out. endRun does the disarm (base
        // opacity 0, same frame) plus the bookkeeping every other end does, and the endedId guard
        // makes any late real animationend a no-op.
        if (!animated) {
            endRun(runId);
            return;
        }
        const inLeft = Math.min(FADE_IN_MS, Math.max(0, plateauAt - Date.now()));
        armRun(SEEK_FADE_OUT + inLeft);
    }

    // COLD SHOW: the bar is not up -> play the whole mp-life transient. `fromDamage` distinguishes
    // the data-driven entry (which owns a hold an Alt peek may interrupt and must later resume)
    // from peekOn's own entry, which IS the peek -- and it also picks which VALUES the run opens
    // with, via onRewind. The MOTION is identical either way (armRun(SEEK_NONE), the tuned fade +
    // slide).
    function coldShow(fromDamage) {
        clearTimeout(peekT);
        // WHICH AREA IS ARMING THIS RUN -- the one place the run's `animated` is decided for an
        // entry, and it covers both cold entries (peekOn's own is fromDamage == false).
        animated = fromDamage ? animEvents : animManual;
        // An UN-ANIMATED entry must also SNAP THE VALUES: with no 600ms fade there is no window for
        // the pre->current climb to happen in, and VALUE_SWAP_MS / the cold rAF both assume one. So
        // reuse the Alt entry's existing "open ALREADY committed" rewind (onRewind(true)) and skip
        // onCommit entirely -- there is nothing left to commit. No second snap mechanism.
        onRewind(!fromDamage || !animated);
        // A cold show plays the entry in full (plateauAt too) -- unless it is un-animated, where
        // arming AT the plateau (opacity 1, translateY(0) both complete) IS the instant appearance.
        armRun(animated ? SEEK_NONE : SEEK_PLATEAU);
        holdFrom(plateauAt);        // ... and the hold this entry earns starts THERE, not now
        if (fromDamage) dmgPlateauAt = plateauAt;
        showing = true;
        if (fromDamage && animated) onCommit(true);   // cold: the target must land in a LATER frame
    }

    // WARM RE-TRIGGER (the debounce): a change arrived while the bar is ALREADY up. Do NOT replay
    // the appearance -- re-measure the DISAPPEARANCE from this event instead. mp-life bakes
    // fade-in, hold and fade-out into ONE both-filled keyframe, so its hold cannot be extended in
    // place; instead restart the animation but SEEK PAST the entry with a negative delay
    // (SEEK_PLATEAU, the 9.68% stop, where both the opacity fade and the slide have completed). The
    // bar stays visibly put and gets a fresh hold + fade-out.
    function warmShow() {
        // AN EVENT IS RE-ARMING THIS RUN, so the run's `animated` becomes the events switch -- the
        // entry itself is already the plateau seek and needs no branch, but the EXIT does (an
        // animated peek that a switched-off event re-triggers must now leave instantly).
        animated = animEvents;
        if (!peeking) {
            armRun(SEEK_PLATEAU);        // the seek lands us AT the plateau (armRun sets plateauAt)
            holdFrom(plateauAt);         // ... and this event's hold starts there, fresh
        }
        // THIS event's hold, remembered so an Alt release resumes it instead of discarding it
        // (peekOff). The peeking branch is the whole reason this is not just read off `plateauAt`:
        // while Alt is held we deliberately do NOT armRun (the pause must survive), so an event
        // landing mid-peek would otherwise get no hold at all and be wiped 600ms after the release.
        // Record the plateau the run WOULD have had -- SEEK_PLATEAU cancels FADE_IN_MS, so armRun's
        // clock makes that exactly now, which is also why the non-peek branch can read the
        // freshly-set plateauAt.
        dmgPlateauAt = peeking ? Date.now() : plateauAt;
        onCommit(false);                     // warm: nothing was rewound, so set the target NOW
    }

    // ALT PEEK (an ADDITIVE second show-trigger, not a gate -- the transient still fires on its own
    // when Alt is untouched). While Alt is held the bar must be pulled up and HELD with no
    // fade-out. Mechanism: play (or keep) mp-life and PAUSE it at the hold plateau, so the entry is
    // the real fade+slide and the hold simply never ends.
    function peekOn() {
        clearTimeout(peekT);
        if (!showing) {
            coldShow(false);            // full entry, then pause below once it lands
        } else if (!peeking && root.style.animationPlayState !== "paused"
                   && Date.now() >= plateauAt + HOLD_MS) {
            // NOT PAUSED is a cheap extra guard for the LONGER hold correction, which parks the run
            // at its plateau at full opacity: there the wall-clock test alone can read true mid-hold,
            // and a paused run is by definition already AT the plateau, so there is nothing to catch.
            // At the default (and for any SHORTER hold) nothing is ever paused here and this term is
            // constant, so the branch below is the shipped one.
            // ALT PRESSED DURING THE FADE-OUT -- `showing` stays true all the way through it (only
            // endRun clears it), so pausing here would pin the bar at partial opacity.
            // plateauAt + HOLD_MS is the 90.32% stop (== elapsed SEEK_FADE_OUT, see armRun's run
            // clock), so at/past it the run is already fading out and must be RE-ARMED, not paused.
            // SEEK_PLATEAU, not a cold entry: mp-life's 0% stop is opacity 0, so replaying the
            // entry from a partially-visible bar would visibly DIP it to nothing and fade up again
            // (reads as a flicker). Seeking to the plateau snaps it back to full opacity -- "caught
            // it". armRun also re-establishes the run identity, the runId guard and the endT
            // fallback, so the superseded run's animationend/timer cannot end this one.
            // ALT IS ARMING THIS RUN, so it takes the manual switch (the "caught it" seek IS already
            // instant either way -- what this decides is the exit).
            animated = animManual;
            armRun(SEEK_PLATEAU);
        }
        // ALT OWNS THE HOLD FROM HERE, so drop any pending hold CORRECTION -- peekOff's resume
        // branch re-applies it on release. This has to come AFTER the branch above, not before it:
        // the cold entry inside it goes through coldShow, which arms a correction of its OWN, so
        // clearing first left a SHORTER-than-baked hold free to release the bar out from under a
        // still-held Alt (measured: a 2s hold ended the peek 3.2s in, ignoring the key entirely).
        // A LONGER hold loses nothing by this -- peekT below is the pause that parks the bar anyway.
        clearTimeout(holdT);
        peeking = true;
        // Pause once the entry has completed -- pausing mid-fade-in would freeze the bar at partial
        // opacity. If the bar was already PAST the entry the wait is 0 and it pauses on this tick.
        peekT = setTimeout(function () {
            root.style.animationPlayState = "paused";
            // A paused hold NEVER ends, so the fallback timer must not end it either. peekOff
            // re-arms a fresh run (and a fresh timer) for the fade-out -- and it does so whether or
            // not this pause ever landed, so a release that beats it is still hold-to-show.
            clearTimeout(endT);
        }, Math.max(0, plateauAt - Date.now()));
    }

    // Alt released -> fade out NOW rather than serving the rest of the hold: releaseHold, which
    // unpauses and seeks straight to the 90.32% stop so only the fade-out plays (see it for the
    // sub-FADE_IN_MS tap mirror -- THE PEEK IS STRICTLY HOLD-TO-SHOW, and a release NEVER earns
    // another `holdMs`).
    //
    // EXCEPT when the peek interrupted a DATA-driven show that still has hold left: players hold
    // Alt near-constantly (extended markers), so fading out there would truncate an event's hold to
    // whatever was left of the peek. RESUME that hold instead, at its true elapsed position:
    // seeking (now - dmgPlateauAt) PAST the plateau makes armRun's clock re-derive
    // plateauAt == dmgPlateauAt, so the resumed run's fade-out starts at exactly the instant the
    // original hold would have -- not later. The pause is simply not credited back: the hold is
    // wall-clock, as it was before any Alt.
    // THE SEEK IS CAPPED AT THE BAKED HOLD, because that is all the keyframe HAS: past
    // SEEK_FADE_OUT it would land in (or beyond) the fade-out. Only reachable with a hold LONGER
    // than HOLD_MS, and holdFrom then carries the rest -- it re-derives `baked` off the seeked
    // plateauAt, so the capped seek plus the correction still add up to dmgPlateauAt + holdMs. At
    // the default the cap can never bind (the branch above requires elapsed < holdMs == HOLD_MS),
    // so this is the shipped seek exactly.
    function peekOff() {
        clearTimeout(peekT);
        if (!peeking) return;
        peeking = false;
        if (dmgPlateauAt + holdMs > Date.now()) {
            // The run being resumed is the EVENT's hold, so it exits the EVENT's way.
            animated = animEvents;
            armRun(SEEK_PLATEAU + Math.min(Date.now() - dmgPlateauAt, HOLD_MS));
            holdFrom(dmgPlateauAt);
            return;
        }
        // ...otherwise this release IS the exit of the run Alt armed, so it follows `animated`.
        releaseHold();
    }

    // FORCE-SETTLE, and the ONE place the "run is over" state is cleared. mp-life is both-filled so
    // the root rests at its 100% stop (opacity 0) with no help from JS; onEnd drops whatever else
    // a hold longer than the transient would have left showing.
    // `id` is the run being ended: an id that is not the live run (a timer from a superseded run) or
    // one already ended (the loser of the animationend/timer race) is ignored.
    function endRun(id) {
        if (id !== runId || id === endedId) return;
        endedId = id;
        clearTimeout(endT);
        clearTimeout(peekT);
        clearTimeout(holdT);
        disarm();
        showing = false;
        peeking = false;
        dmgPlateauAt = 0;                // the hold is over -- a later release must never resume it
        root.style.animationPlayState = "";
        onEnd();
    }

    // Only the CURRENTLY armed animation's end counts. Because armRun alternates the identity, the
    // cancel/end noise of the run it just superseded reports the OTHER name and is dropped here for
    // free. A pulse on an inner element (.mp-track) never reaches this listener.
    root.addEventListener("animationend", function (e) {
        if (e.animationName !== runNames[armIdx]) return;
        endRun(runId);
    });

    // Reset to the resting/hidden state, so a later re-show starts COLD. The caller additionally
    // drops its own change-detect baseline, so the next push becomes a fresh silent one (a
    // scoreboard opening and closing must not replay the bar).
    function reset() {
        clearTimeout(peekT);
        clearTimeout(holdT);
        clearTimeout(endT);
        endedId = runId;                 // no live run left for a late animationend to end
        disarm();
        // DROP THE HELD-CTRL FLAG HERE TOO. This is the "bar hidden" path (a scoreboard, a spectate,
        // the feature switched off mid-battle, a new battle), and it can land with Ctrl still down --
        // leaving the flag set would let the next peek() call pin a bar that was just reset. Ctrl
        // coming back up sets it again through the same one-line applyCtrl.
        applyCtrl(false);
        root.style.animationPlayState = "";
        root.style.animationDelay = "0ms";
        showing = false;
        peeking = false;
        dmgPlateauAt = 0;                // ditto endRun: no hold survives a hide / a new battle
        onIdle();
    }

    // Push the surface size and collapse the input rect. Feature-detected and fail-soft, like every
    // engine read in this codebase -- OpenWG's own libs/common.js touches the `viewEnv` global
    // directly and offers no resize wrapper, so this does too. Idempotent: called at mount and once
    // more after SURFACE_REASSERT_MS.
    function pushSurfaceSize() {
        if (typeof viewEnv === "undefined" || !viewEnv) return;
        try {
            // WG's own views freeze the texture across a resize (flicker, not sizing) -- e.g.
            // BattleNotifierView.js. Optional, so feature-detected like the rest.
            if (viewEnv.freezeTextureBeforeResize) viewEnv.freezeTextureBeforeResize();
        } catch (e) { /* fail-soft */ }
        try {
            if (viewEnv.resizeViewRem) viewEnv.resizeViewRem(viewW, viewH);
        } catch (e) { /* fail-soft: a clipped bar beats a dead one */ }
        pushHitArea();
    }

    // THE INPUT RECT, kept as its own function because it is the one engine call with a two-tier
    // argument fallback. It is ALWAYS the collapsing push now: the rect used to be OPENED (padding
    // 0, i.e. the whole surface rect live) while Ctrl was held, so the bar's own document could
    // receive the drag's mouse events -- and that opening was the HUD-input-stealing hazard the old
    // design had to manage on every path that could leave the gesture. Python owning the gesture
    // retires it: nothing in here needs a mouse event, so the rect never opens.
    function pushHitArea() {
        if (typeof viewEnv === "undefined" || !viewEnv) return;
        if (!viewEnv.setHitAreaPaddingsRem) return;
        // (top, right, bottom, left, magic) -- confirmed order (see the header note). FOUR EQUAL
        // VALUES, matching WG's own wrapper -- the order is moot when they cannot differ.
        try {
            viewEnv.setHitAreaPaddingsRem(hitPad, hitPad, hitPad, hitPad, HIT_MAGIC);
        } catch (e) {
            // The 5th argument's meaning is unknown -- if the binding rejects the 5-arg form, the
            // 4-arg one still collapses the rect.
            try {
                viewEnv.setHitAreaPaddingsRem(hitPad, hitPad, hitPad, hitPad);
            } catch (e2) { /* fail-soft */ }
        }
    }

    // THE ROOT FONT WRITE -- the whole SIZE_F half of the large mode (see the constant's note).
    // Captures the base ONCE and never reads back our own inline value, so applying it twice cannot
    // compound. Fail-soft like every other engine touch: no getComputedStyle / no documentElement
    // (a shim, a stripped document) simply leaves the size alone.
    //
    // THE CAPTURE IS GATED ON THE VIEW HAVING A SIZE, and that gate is load-bearing. For the first
    // frames of a mount the view has NO size (innerWidth/innerHeight are both 0 -- live-measured, in
    // the very first dump of every mount) and THE ENGINE HAS NOT WRITTEN ITS ROOT FONT YET, so
    // getComputedStyle hands back the UA default 16 instead of the engine's 1 (2 at interface scale
    // x2). Baking 16 in as the base multiplied every rem by 16: with Large enabled BEFORE launch --
    // the ONLY path where the very first applySize takes the large branch -- rootFontPx came out 24
    // and the 400rem track 9600px wide inside a 950px surface, i.e. drawn entirely outside the view
    // and INVISIBLE. Flipping to Large mid-session was always fine (the engine's root font is in
    // place by then), which is exactly what hid this until it shipped.
    // Untrusted means WRITE NOTHING -- not a guessed base, and not our own value read back: leaving
    // the inline style alone is what keeps the LATER read (mount's post-deadline re-assert calls this
    // again) the engine's own value.
    // The capture, kept as its own function: it is the ONE place a root-font read happens, and it is
    // ALSO the interface-scale signal setQuantClass gates on. That second use is MEASURED, not
    // assumed: a four-bit screenshot probe read this value BELOW 1.5 at interface scale 1 and at/above
    // 1.5 at scale 2, on the DEFAULT path, on fresh launches -- while devicePixelRatio and
    // innerWidth/viewW both read a constant 1 at either scale and innerHeight/viewH a constant ratio,
    // so none of those three is a signal. See tests/test_caption_anchor_quantisation.py.
    // Returns the base in px; 0 == not trustworthy yet, which means DO NOTHING.
    function captureBaseFont() {
        if (!baseFont && (window.innerWidth || window.innerHeight)) {
            baseFont = parseFloat(getComputedStyle(document.documentElement).fontSize) || 1;
        }
        return baseFont;
    }

    function setRootFont() {
        try {
            if (!captureBaseFont()) return;
            document.documentElement.style.fontSize = large ? (baseFont * SIZE_F) + "px" : "";
        } catch (e) { /* fail-soft: the shipped size beats a dead view */ }
    }


    // THE INTERFACE-SCALE GATE. The ONE class the caption-icon correction hangs off
    // (MoEEfficiency.css's HAND-ADDED BLOCK 4, which documents the correction itself; MoEProgress.css
    // deliberately carries no rule for it, so on the Moving Average bar this class is inert).
    //
    // A THRESHOLD, NEVER AN EXACT KEY: an exact match on an engine-reported number fails silently and
    // one whole build died on exactly that. It also never consults `large` -- the size mode is a
    // separate axis, and folding it in here is what made the correction depend on how Large was
    // reached.
    // THE POSITIVE LOWER BOUND IS THE TRUST GATE: captureBaseFont returns 0 while the view has no size
    // (see it), and an untrusted read must leave the class OFF, because the base cascade IS the render
    // the maintainer approved at interface scale 2. Every failure mode here -- no size yet, no
    // documentElement, a throwing getComputedStyle -- therefore lands on "no class, no correction,
    // nothing moves".
    // toggle(cls, force) both ADDS and REMOVES, which is what makes re-evaluating safe from anywhere.
    //
    // KNOWN, ACCEPTED DEFECT -- A LIVE INTERFACE-SCALE CHANGE LEAVES THE CLASS STALE UNTIL RELAUNCH.
    // Python DOES see one (settingsCore.interfaceScale.onScaleChanged -> battle_bridge's
    // _on_scale_changed -> *_view.apply_position()), but nothing carries it into this document: there
    // is no VM field for it, and `baseFont` is captured ONCE, so re-running the gate off a hook would
    // re-read the old value anyway (and re-capturing is not free -- under Large we have written our
    // own inline root font, which a naive re-read would compound). Minor, and deliberately NOT papered
    // over with a polling timer. A measurement taken ACROSS a live scale change is therefore not a
    // measurement of this gate.
    function setQuantClass() {
        try {
            const px = captureBaseFont();
            document.body.classList.toggle("mp-s1", px > 0 && px < 1.5);
        } catch (e) { /* fail-soft: the base cascade IS the approved render */ }
    }

    // Apply the pushed size flag. Idempotent (a no-op unless it actually FLIPPED), so the bars can
    // call it on every render. Order matters: the CSS side first, then the surface push, because the
    // engine round-trips the resize back into Python's _place.
    //   x-lengths     carry SIZE_XF in the stylesheet AND here (boxLeft / boxW are x-lengths)
    //   y/uniform     carry nothing here -- the root font does them
    //   engine args   carry SIZE_F on top, because resizeViewRem's rem is C++'s, not our document's
    function applySize(flag) {
        flag = !!flag;
        if (flag === large) return;
        large = flag;
        const xf = large ? SIZE_XF : 1;
        const f = large ? SIZE_F : 1;
        // ROUNDED, because 4/3 is not representable: (460 * 4/3 + 20) * 1.25 evaluates to
        // 791.6666666666665, and the engine takes whole logical px (a floor there would hand us a
        // 1px-narrow surface). Both factors are exact at the shipped size, so this is identity there.
        // `padX`/`padXR` do NOT carry `xf` -- see their arg notes: they are rem-space slack (ink
        // allowance on the left, a bleed CLIP on the right), which the root font's SIZE_F already
        // grows/shrinks. Large reads `padXRLarge` instead of `padXR * xf`: its target (the Python
        // `edge_x` it must clear) is a hand-corrected, not purely `*SIZE_XF`-scaled, number -- see
        // the arg note.
        viewW = Math.round((cfg.boxW * xf + cfg.padX + (large ? cfg.padXRLarge : cfg.padXR)) * f);
        // clipB is a Y length like boxH and pad, so it takes `f` alone with them and NEVER `xf` --
        // it stays INSIDE the parenthesis so the clip scales with the composition it clips (the
        // caption ink below the track scales too), rather than staying a fixed logical-px bite that
        // would eat into that ink under Large.
        viewH = Math.round((cfg.boxH + 2 * cfg.pad - cfg.clipB) * f);
        // rem, so it self-scales with the root font -- 3dp to match the stylesheet's own x-lengths,
        // which keeps shiftX + the .mp-lg backdrop's `left` exactly `pad`.
        shiftX = Math.round((cfg.padX - cfg.boxLeft * xf) * 1000) / 1000;
        hitPad = Math.ceil(Math.max(viewW, viewH) / 2);
        setRootFont();
        // THE SCALE GATE IS RE-EVALUATED ON EVERY FLIP, in BOTH directions, and is deliberately not
        // latched at mount. The shipped build computed it in ONE branch of the re-assert, so `.mp-s1`
        // and `.mp-lg` could only coexist by launching at Default and enabling Large mid-session --
        // i.e. the correction applied or not depending on HOW the user reached Large. It is also the
        // one place an engine-pushed scale can reach the gate: self.onScaleUpdated moves `baseFont`,
        // but only while large, so a flip BACK re-reads it. At the shipped size this re-reads the same
        // capture and is a no-op, which is the point -- it can only ever agree with the mount-time
        // evaluation.
        setQuantClass();
        try {
            // WG's own ancestor-class idiom (.mediaLargeWidth ...). It MUST go on the BODY: the
            // sizing shim #moe-bar-box is a body-level SIBLING of the JS-created root, so a class on
            // the root could never reach it.
            document.body.classList.toggle("mp-lg", large);
        } catch (e) { /* fail-soft */ }
        root.style.left = shiftX + "rem";
        pushSurfaceSize();
    }


    // The pushed transition switches (VM `transEvents` / `transManual`). Plumbed exactly like
    // applySize -- idempotent and safe on every render -- but it needs no flip guard and touches
    // nothing: it only records which switch the NEXT arming reads, so a live settings change lands on
    // the next show rather than mutating the run in flight.
    // ABSENT MEANS ANIMATED, which is why this is `!== false` and not `!!`: a model that does not
    // carry the field at all (a pre-push frame, a harness fixture, a marshal that dropped it) must
    // degrade to the SHIPPED behaviour, and `!!undefined` would silently degrade to instant instead --
    // the fail-soft direction every other read in this codebase takes. A real pushed false is the
    // only thing that turns a transition off.
    function applyAnim(events, manual) {
        animEvents = events !== false;
        animManual = manual !== false;
    }

    // The pushed HOLD DURATION (VM `holdMs`). Plumbed exactly like applyAnim -- idempotent, safe on
    // every render, and it only records what the NEXT hold reads (holdFrom), so a live settings
    // change lands on the next show rather than truncating a hold in flight.
    // ABSENT MEANS THE SHIPPED 5000, NEVER 0, which is why the test is `> 0` and not a bare cast: a
    // model that does not carry the field at all (a pre-push frame, an old harness fixture, a
    // marshal that dropped it) yields NaN, and `NaN > 0` is false -- so it degrades to the BAKED
    // hold, the same fail-soft direction applyAnim takes. A 0 would mean "no hold at all".
    function applyHold(ms) {
        const v = Number(ms);
        holdMs = v > 0 ? v : HOLD_MS;
    }

    // --- CTRL+DRAG TO REPOSITION: NOT IN THIS FILE ANY MORE -------------------------------
    // The gesture is Python's, end to end. adapter/battle_input samples Ctrl AND the left mouse
    // button off WG's own input dispatchers and reports start/move/end; bridge/bar_window re-places
    // the window ABSOLUTELY from GUI.mcursor().position on every movement. This document's only part
    // is `ctrlHeld` below, which holds the bar up so there is something to grab.
    //
    // WHAT WAS DELETED AND WHY IT CANNOT COME BACK. There used to be a document-level
    // mousedown/mousemove/mouseup drag here (`installDrag`) reporting a cursor DELTA through a
    // `setPosition` reverse command. Three structural failures, not three bugs:
    //   (1) the reported delta was DEVICE px while window.move takes LOGICAL px, so it needed a gain
    //       factor -- and interfaceScale, the obvious candidate, over-corrected;
    //   (2) each bar IS its own window and THE SURFACE RECT IS THE MOUSE HIT RECT, so mouse events
    //       only reached this document while the cursor stayed inside the bar-sized rect. Any gain
    //       error or round-trip lag let the cursor drift out; events stopped, then resumed, and the
    //       bar lurched ("jumps wildly near the edges of the bar"). Capture-phase listeners do NOT
    //       help -- that is DOM propagation inside a document, not the engine's hit test;
    //   (3) the JS -> Python -> engine round trip lags under battle load.
    // An ABSOLUTE mapping has no gain factor to get wrong and needs no mouse input in the document
    // at all, which is also why the hit rect is now permanently collapsed (see pushHitArea).
    // Re-introducing any delta protocol re-introduces all three.

    // The pushed CTRL state (VM `ctrlHeld`), read every render like applySize / applyAnim, and now
    // just a flag: `peek()` reads it back, so a held Ctrl pins the bar at its hold plateau exactly
    // like a held Alt.
    //
    // `=== true`, NOT `!== false`, and that is the OPPOSITE of the two switches above ON PURPOSE:
    // both rules say "fail soft toward the SHIPPED behaviour", and the shipped bar is NOT pinned up.
    // An absent field (a pre-push frame, an old harness fixture, a marshal that dropped it) must
    // therefore read as NOT HELD -- `!== false` would peek forever on any model that never carries
    // the flag, and the bar would never come down.
    function applyCtrl(held) {
        ctrlHeld = held === true;
    }

    // Wire the bar up, ONCE, on engine ready. FOUR parts, in this order:
    //
    //  (0) THE ORIENTATION, if the bar offers a vertical composition at all (cfg.vert). FIRST,
    //      because every one of the three parts below is derived from the composition it picks --
    //      the shift, the surface size, and the DOM the first render writes into. `=== true`, NOT
    //      `!== false`: this is a STATE bool, and the shipped bar is HORIZONTAL, so an absent field
    //      (a pre-push frame, an old harness fixture, a marshal that dropped it) must fail soft
    //      toward the shipped composition -- the same rule `ctrlHeld` follows and the OPPOSITE of
    //      the transition switches', which are feature switches whose shipped state is on.
    //  (1) THE RIGID TRANSLATION (unconditional -- an origin overflow is clipped at ANY surface
    //      size, so this must happen even without viewEnv). #moe-bar-root is
    //      position:absolute;left:0;top:0 in the CSS, and moving its origin carries the in-flow
    //      .mp-track AND the abspos .mp-backdrop with it -- relative geometry stays bit-for-bit
    //      identical and NO tuned value is touched. It has to be left/top and NOT a transform:
    //      mp-life animates the root's OWN transform and would clobber one. Python cancels the
    //      shift (*_ANCHOR_Y_SHIFT) so the bar does not move on screen.
    //  (2) THE SURFACE + INPUT RECT, pushed now and RE-ASSERTED after the engine's default-size
    //      deadline. The `settled` flip is NESTED in that callback on purpose: it is the re-assert
    //      that makes the surface correct, so the dependency is structural rather than a second
    //      timer that could outlive it. It then re-renders the model we already hold, so a
    //      STILL-HELD Alt takes effect immediately -- during PREBATTLE there may be no efficiency
    //      tick to re-push it, and the player is mid-peek. That render is no longer a ONE-SHOT: a
    //      short self-stopping poll keeps re-calling it in case the model's `visible`/`hasData` push
    //      is still to come (see COLD_POLL_MS above).
    //  (3) the model subscription and the first render.
    function mount(observer, render) {
        engine.whenReady.then(() => {
            if (cfg.vert && observer.model && observer.model.vertical === true) goVertical();
            root.style.left = shiftX + "rem";
            root.style.top = shiftY + "rem";
            pushSurfaceSize();
            // ROBUSTNESS ON THE ROOT FONT (the one unknown): we do not know from source whether the
            // engine also initialises / overwrites the root font per view. WG's bootstrap re-writes it
            // from this event, so if it reaches a registered view we take the PUSHED scale as the new
            // base and re-apply -- and if it never fires, the mount-time capture already stands.
            // Only while large: the shipped size never touches the root font at all.
            try {
                engine.on("self.onScaleUpdated", function (scale) {
                    if (!large) return;
                    baseFont = parseFloat(scale) || baseFont || 1;
                    setRootFont();          // guarded in there -- this runs in an engine callback
                });
            } catch (e) { /* fail-soft: the event is optional */ }
            setTimeout(function () {
                // THE DEFERRED ROOT FONT. A large flag pushed on the first render arrives while the
                // view still has no size, so setRootFont could not trust the computed base and wrote
                // nothing; the re-assert is the first moment the view is definitely sized, so this is
                // where that write actually lands. Gated on `large` for the same reason the scale
                // hook is: the shipped size never touches the root font at all.
                // THE SCALE GATE RUNS UNCONDITIONALLY, on BOTH paths, and the two lines are kept
                // adjacent so that stays visible: this is the first moment the view is definitely
                // sized, hence the first moment the capture can be trusted, and a launch straight
                // into Large must get the gate too. The shipped build ran it in the `else` alone,
                // which is how the correction became a function of how Large was reached (see
                // applySize, which re-evaluates it on every flip).
                if (large) setRootFont();
                setQuantClass();
                pushSurfaceSize();
                setTimeout(function () {
                    settled = true;
                    // The one immediate render this always did -- kept verbatim (see COLD_POLL_MS's
                    // header note above for why a bare one-shot here is not enough on its own).
                    render(observer.model);
                    // REVEALED ALREADY: an event fired inline (e.g. a still-held Alt in "Always"
                    // mode, data that was ready all along) -- `showing`/`peeking` are this closure's
                    // own state, set by the render() call just above, so no poll is needed.
                    if (showing || peeking) return;
                    // NOT YET REVEALED: poll observer.model until it is, or give up at the ceiling.
                    // A SELF-RESCHEDULING setTimeout, not setInterval -- this module already takes
                    // `setTimeout`/`clearTimeout`/`Date` as its only timing primitives (mirrored,
                    // fake-clock-driven, by tools/dev/lib/gf_check_shim.js's headless harness, which
                    // does NOT stub setInterval), so a setInterval here would fall through to a REAL
                    // timer under that harness -- ungated by the virtual clock's Date.now(), and
                    // therefore never satisfying its own stop predicate there.
                    const deadline = Date.now() + COLD_POLL_CEILING_MS;
                    (function tick() {
                        setTimeout(function () {
                            render(observer.model);
                            if (!(showing || peeking) && Date.now() < deadline) tick();
                        }, COLD_POLL_MS);
                    })();
                }, SURFACE_SETTLE_MS);
            }, SURFACE_REASSERT_MS);
            observer.onUpdate(render);
            observer.subscribe();
            render(observer.model);
        });
    }

    return {
        mount: mount,
        // THE SHOW TRIGGERS ARE GATED ON `settled`; a caller's SILENT BASELINE must not be. Before
        // the re-assert the surface is the engine's 256x256 fallback: the bar would come up cropped
        // and badly mis-placed. A baseline shows nothing, so it costs nothing to let it run -- and
        // it MUST run, or the change-detect never gets its first value.
        settled: function () { return settled; },
        show: function () {
            if (showing) warmShow();
            else coldShow(true);
        },
        // Alt is an ADDITIVE trigger, never a gate. Re-peeking while already peeking is a no-op, so
        // a re-push that merely carries altHeld again cannot restart the hold.
        //
        // CTRL RIDES THE SAME PEEK, deliberately reusing it rather than adding a hold path: the
        // reposition gesture needs the bar up and pinned for exactly as long as the key is down,
        // which IS what peekOn does (pause at the hold plateau, never end the run). So a held Ctrl
        // peeks like a held Alt, and releasing either one releases the peek only if the other is up
        // too. This is now the bar's ENTIRE part in the gesture -- Python does the rest.
        peek: function (held) {
            if (held || ctrlHeld) {
                if (!peeking && settled) peekOn();
            } else {
                peekOff();
            }
        },
        // The pushed Ctrl state (VM `ctrlHeld`): it holds the bar up for the reposition gesture and
        // does nothing else. Read every render, like size / anim / hold -- and BEFORE peek(), which
        // reads the flag back.
        ctrl: applyCtrl,
        // The pushed size flag (VM `barSize` == 1). Idempotent, so it is safe on every render; the
        // flag arrives AFTER the mount-time surface push, so the correct size lands on the
        // POST-DEADLINE re-assert -- which is fine precisely because `settled` hides the bar until
        // then (see SURFACE_REASSERT_MS).
        size: applySize,
        // The pushed transition switches (VM transEvents / transManual, master already folded in
        // Python). Read every render, like size.
        anim: applyAnim,
        // The pushed hold duration (VM holdMs). Read every render, like anim.
        hold: applyHold,
        reset: reset,
        disarm: disarm,
    };
}

export {
    fmt, pctText,
    SIZE_F, SIZE_XF,
    FADE_IN_MS, HOLD_MS, FADE_OUT_MS, TOTAL_MS,
    SEEK_NONE, SEEK_PLATEAU, SEEK_FADE_OUT,
    SURFACE_REASSERT_MS, SURFACE_SETTLE_MS, END_MARGIN_MS, HIT_MAGIC,
    RUN_CLASSES, RUN_NAMES, RUN_CLASSES_V, RUN_NAMES_V,
};
