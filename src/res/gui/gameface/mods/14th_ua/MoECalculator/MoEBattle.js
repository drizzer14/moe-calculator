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

// Percentile float -> "84.73%" (two decimals, TRUNCATED not rounded); 0 -> "0%".
// Truncate so the readout never overstates progress toward a mark threshold.
function pctText(p) {
    p = Number(p) || 0;
    if (p <= 0) return "0%";
    return (Math.floor(p * 100) / 100).toFixed(2) + "%";
}

// Signed delta NUMBER -> "+0.41%" / "-1.20%"; exactly 0 -> "0%". Two decimals, TRUNCATED
// (matches pctText) so the delta never overstates a mark gain. The surrounding parens are
// STATIC markup (see ensureRoot) and stay white -- only this number carries the sign colour.
function signedPct(p) {
    p = Number(p) || 0;
    if (p === 0) return "0%";
    const sign = p > 0 ? "+" : "-";
    return sign + (Math.floor(Math.abs(p) * 100) / 100).toFixed(2) + "%";
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
    // loaded (metrics 2-4 need it; without it the readout is meaningless).
    if (!data || data.visible === false || data.hasData === false) {
        root.style.display = "none";
        return;
    }
    root.style.display = "";

    const cd = data.combinedDamage || 0;
    const avg = data.projAvgDamage || 0;
    // Combined damage is shown exactly -- no approximation indicator.
    const cdEl = root.querySelector(".mb-cd");
    cdEl.textContent = thousands(cd);
    root.querySelector(".mb-avg").textContent = thousands(avg);
    // Live damage vs your own projected average: red below, white at par, green above.
    colourBySign(cdEl, cd - avg);

    root.querySelector(".mb-pct").textContent = pctText(data.curPercent || 0);
    const delta = Number(data.pctDelta) || 0;
    // Colour only the number; the parens on .mb-delta stay white.
    const deltaNum = root.querySelector(".mb-delta-num");
    deltaNum.textContent = signedPct(delta);
    // Delta vs pre-battle standing: green improves, red drags, white unchanged.
    colourBySign(deltaNum, delta);
}

engine.whenReady.then(() => {
    observer.onUpdate(render);
    observer.subscribe();
    render(observer.model);
});
