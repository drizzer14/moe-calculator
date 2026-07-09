// 14th_ua's MoE Calculator -- in-battle overlay. This JS is the front-end of a
// STANDALONE OpenWG-registered Gameface view (MoEBattleView.html, registered via
// mods/configs/res_map/MoEBattleView.json) that the Python side opens as a
// full-screen, input-transparent top-layer window OVER the battle HUD
// (bridge/battle_view.py). The battle HUD has no shared full-screen Gameface
// document to inject a position:fixed overlay into (each WG battle Gameface view is
// composited by Flash at its own placeId), so we host our own window instead.
//
// Because this is a registered view, OUR data model (BattleMoEVM) IS the view's own
// root ViewModel -- we read it with a root ModelObserver() (no feature name) and read
// the fields DIRECTLY off the root (model.combinedDamage, ...), NOT via a nested
// `moeBattleData` submodel.
//
// LOOK: mirrors WG's own personal-efficiency panel (damage dealt / blocked / assisted)
// -- a left-aligned vertical stack of [icon] [white value] rows over a soft
// dark->transparent gradient, NO text labels, NO frame. See dmg_panel reference.
//   row 1: live combined damage  /  projected avg combined dmg      (icon: damage)
//          -> the live damage is RED when below the projected average, WHITE when
//             equal, GREEN when above (are you out-performing your own projection?).
//   row 2: projected MoE percent  (signed delta vs pre-battle standing)  (icon: mark)
//          -> the delta is RED when negative, WHITE at zero, GREEN when positive.
//
// pointer-events:none throughout -- the overlay is pure HUD info and must never
// intercept battle input. See the wotmod-gameface-widget harness skill for the
// DOM/CSS conventions + Coherent quirks; mirrors MoECalculator.js.
import { ModelObserver } from "../../libs/model.js";

// Icon art now lives in MoEBattle.css: the glyph is painted on `.mb-ico::after` (per-row class
// `dmg`/`pct`, img:// background-image) so the gold glow can sit BEHIND it on `.mb-ico::before`
// (an element's own background always paints below its pseudos). Swap the glyph art in the CSS.

// No feature name -> observe this view's OWN root model (window.model == BattleMoEVM).
const observer = ModelObserver();

// Group an integer with thousands separators: 2910 -> "2,910".
function thousands(n) {
    n = Math.max(0, Math.round(Number(n) || 0));
    return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// Truncate toward zero to 2 decimals -- the shared display precision for both the percent
// and the delta. A sub-precision magnitude (e.g. 0.004) collapses to exactly 0 so it never
// carries a misleading sign or colour that its "0%" text contradicts.
function trunc2(p) {
    p = Number(p) || 0;
    const mag = Math.floor(Math.abs(p) * 100) / 100;
    return p < 0 ? -mag : mag;
}

// Percentile float -> "84.73%" (two decimals, TRUNCATED not rounded); <=0 at precision -> "0%".
// Truncate so the readout never overstates progress toward a mark threshold.
function pctText(p) {
    const v = trunc2(p);
    if (v <= 0) return "0%";
    return v.toFixed(2) + "%";
}

// Signed delta NUMBER -> "+0.41%" / "-1.20%"; zero AT DISPLAY PRECISION -> "0%". Two decimals,
// TRUNCATED (matches pctText) so the delta never overstates a mark gain and a sub-precision
// value reads "0%" with no sign. The surrounding parens are STATIC markup (see ensureRoot) and
// stay white -- only this number carries the sign colour.
function signedPct(p) {
    const v = trunc2(p);
    if (v === 0) return "0%";
    return (v > 0 ? "+" : "-") + Math.abs(v).toFixed(2) + "%";
}

// Tri-state colour by sign: >0 green (mb-up), <0 red (mb-down), 0 white (neither class).
function colourBySign(el, sign) {
    el.classList.toggle("mb-up", sign > 0);
    el.classList.toggle("mb-down", sign < 0);
}

// Build the root element once and cache it.
function ensureRoot() {
    let root = document.getElementById("moe-battle-root");
    if (root) return root;
    root = document.createElement("div");
    root.id = "moe-battle-root";
    root.innerHTML =
        // Row 1: [dmg icon]  <live dmg> / <projected avg>
        '<div class="mb-row">' +
        '  <span class="mb-ico dmg"></span>' +
        '  <span class="mb-value mb-cd"></span>' +
        '  <span class="mb-sep">/</span>' +
        '  <span class="mb-value mb-avg"></span>' +
        '</div>' +
        // Row 2: [mark icon]  <projected %>  (<signed delta>)
        '<div class="mb-row">' +
        '  <span class="mb-ico pct"></span>' +
        '  <span class="mb-value mb-pct"></span>' +
        '  <span class="mb-delta">(<span class="mb-delta-num"></span>)</span>' +
        '</div>';
    document.body.appendChild(root);
    return root;
}

function render(model) {
    const root = ensureRoot();
    // In a registered view the observed model IS our BattleMoEVM root -- read fields
    // directly off it (no nested `moeBattleData` submodel, no unwrap needed for scalars).
    const data = model;

    // Hidden until Python confirms combat is live AND the per-tank threshold table is
    // loaded (metrics 2-4 need it; without it the readout is meaningless). Truthy guard so a
    // root VM whose visible/hasData are still undefined (before Python's first push) hides
    // rather than painting a "0 / 0 -- 0%" stub over the HUD.
    if (!data || !data.visible || !data.hasData) {
        root.style.display = "none";
        return;
    }
    root.style.display = "";

    const cd = data.combinedDamage || 0;
    // Live combined damage is ALWAYS meaningful -- even in a replay with no baseline -- so it
    // is shown exactly, no approximation indicator.
    const cdEl = root.querySelector(".mb-cd");
    cdEl.textContent = thousands(cd);
    const deltaNum = root.querySelector(".mb-delta-num");

    // Without a CAREER baseline (replay / relogin straight into battle -- the garage dossier
    // was never read; BUG B) the projected avg, percent and delta are all collapsed and
    // meaningless. Dash them out and drop the sign colours, keeping only the live CD. An absent
    // flag (older Python push) is treated as "baseline present" so the normal render is unchanged.
    if (data.hasBaseline !== false) {
        const avg = data.projAvgDamage || 0;
        root.querySelector(".mb-avg").textContent = thousands(avg);
        // Live damage vs your own projected average: red below, white at par, green above.
        colourBySign(cdEl, cd - avg);

        root.querySelector(".mb-pct").textContent = pctText(data.curPercent || 0);
        // Truncate to display precision FIRST so the sign, colour and text all agree: a
        // sub-precision delta reads "0%" in white, never a green "+0.00%".
        const delta = trunc2(Number(data.pctDelta) || 0);
        // Colour only the number; the parens on .mb-delta stay white.
        deltaNum.textContent = signedPct(delta);
        // Delta vs pre-battle standing: green improves, red drags, white unchanged.
        colourBySign(deltaNum, delta);
    } else {
        const DASH = "-";                    // hyphen: value unknown without a baseline (the
                                             // subset MoEBattle.ttf has "-" but no em-dash)
        root.querySelector(".mb-avg").textContent = DASH;
        colourBySign(cdEl, 0);                    // nothing to compare CD against -> white
        root.querySelector(".mb-pct").textContent = DASH + "%";
        deltaNum.textContent = DASH;
        colourBySign(deltaNum, 0);                // no sign -> white
    }
}

engine.whenReady.then(() => {
    observer.onUpdate(render);
    observer.subscribe();
    render(observer.model);
});
