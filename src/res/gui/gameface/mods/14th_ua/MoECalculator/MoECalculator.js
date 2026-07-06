// 14th_ua's MoE Calculator widget. Injected into the hangar document by OpenWG. Reads
// our data model (exposed as `moeData` on the host sub-view's model) via ModelObserver
// and renders a Marks-of-Excellence progress bar: a percentile axis (0..100) with three
// milestone ticks at 65/85/95 (= 1/2/3 marks) drawn with the vehicle's nation mark art
// ON TOP of the bar and the combined-damage requirement BELOW each, plus a top-left
// readout of the current average combined damage + current mark percentage.
//
// Style mimics the garage's top-right Battlepass chapter-progress widget. See the
// wotmod-gameface-widget harness skill for the DOM/CSS conventions + Coherent quirks.
import { ModelObserver } from "../../libs/model.js";

const observer = ModelObserver("MoECalculator");

// wulf exposes nested viewmodels / array elements wrapped as { value: ... }.
function unwrap(x) {
    return x && x.value !== undefined ? x.value : x;
}

// Generic (nation-agnostic) mark glyph, used when the nation art url is empty.
const GENERIC_MARK = "img://gui/maps/icons/library/marksOnGun/mark_%d.png";

// Group an integer with thousands separators: 2910 -> "2,910".
function thousands(n) {
    n = Math.max(0, Math.round(Number(n) || 0));
    return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// Percentile float -> "84.7%" (one decimal); 0 -> "0%".
function pctText(p) {
    p = Number(p) || 0;
    if (p <= 0) return "0%";
    return p.toFixed(1) + "%";
}

// Build the root element once and cache it on the document.
function ensureRoot() {
    let root = document.getElementById("moe-root");
    if (root) return root;
    root = document.createElement("div");
    root.id = "moe-root";
    root.innerHTML =
        '<div class="moe-head">' +
        '  <span class="moe-cur">' +
        '    <span class="moe-cur-dmg"></span>' +
        '    <span class="moe-cur-sep"></span>' +
        '    <span class="moe-cur-pct"></span>' +
        '  </span>' +
        '  <span class="moe-title"></span>' +
        '</div>' +
        '<div class="moe-body">' +
        '  <div class="moe-track">' +
        '    <div class="moe-fill"></div>' +
        '    <div class="moe-cur-marker"></div>' +
        '    <div class="moe-ticks"></div>' +
        '  </div>' +
        '</div>';
    document.body.appendChild(root);
    root.querySelector(".moe-title").textContent = "MARKS OF EXCELLENCE";
    return root;
}

function markIcon(tk) {
    const url = tk.icon || "";
    if (url) return url;
    const count = Math.max(1, Math.min(3, tk.markCount || 1));
    return GENERIC_MARK.replace("%d", String(count));
}

function renderTicks(ticksEl, ticks) {
    ticksEl.innerHTML = "";
    for (let i = 0; i < ticks.length; i++) {
        const tk = unwrap(ticks[i]);
        const el = document.createElement("div");
        el.className = "moe-tick" + (tk.reached ? " moe-tick-reached" : "");
        el.style.left = (tk.percent || 0) + "%";

        // Nation mark art ON TOP of the bar.
        const icon = document.createElement("div");
        icon.className = "moe-tick-icon";
        icon.style.backgroundImage = "url(" + markIcon(tk) + ")";
        el.appendChild(icon);

        // A small notch sitting on the track at the milestone.
        const notch = document.createElement("div");
        notch.className = "moe-tick-notch";
        el.appendChild(notch);

        // Damage requirement BELOW the mark (blank when unknown -> external table
        // not loaded yet / vehicle absent from it).
        const req = document.createElement("div");
        req.className = "moe-tick-req";
        req.textContent = (tk.damageRequired > 0) ? thousands(tk.damageRequired) : "";
        el.appendChild(req);

        ticksEl.appendChild(el);
    }
}

function render(model) {
    const root = ensureRoot();
    const data = unwrap(model && model.moeData);

    if (!data) {
        // Model not attached yet -- keep the widget hidden rather than flashing a stub.
        root.style.display = "none";
        return;
    }

    // Python pushes visible=false off the plain garage / while a tank-setup overlay is
    // open. An absent flag (older Python) is treated as visible.
    if (data.visible === false) { root.style.display = "none"; return; }
    root.style.display = "";

    // Responsive bottom offset: tag the root with the carousel geometry so the CSS can
    // lift the bar clear of a single / small-double / tall-double carousel.
    root.classList.toggle("moe-rows2", Number(data.carouselRows) === 2);
    root.classList.toggle("moe-small", !!data.carouselSmall);

    // Top-left readout: current average combined damage + current mark percentage.
    const dmg = data.curAvgDamage || 0;
    const pct = data.curPercent || 0;
    root.querySelector(".moe-cur-dmg").textContent = dmg > 0 ? thousands(dmg) : "—";
    root.querySelector(".moe-cur-sep").textContent = dmg > 0 ? "·" : "";
    root.querySelector(".moe-cur-pct").textContent = dmg > 0 ? pctText(pct) : "";

    // Fill to the current percentile on the fixed 0..100 axis, and place the leading-edge
    // marker at the same spot (mimics the Battlepass in-chapter leading edge).
    const fill = Math.max(0, Math.min(100, Number(data.fill) || 0));
    root.querySelector(".moe-fill").style.width = fill + "%";
    root.querySelector(".moe-cur-marker").style.left = fill + "%";

    renderTicks(root.querySelector(".moe-ticks"), (data.ticks || []));
}

engine.whenReady.then(() => {
    observer.onUpdate(render);
    observer.subscribe();
    render(observer.model);
});
