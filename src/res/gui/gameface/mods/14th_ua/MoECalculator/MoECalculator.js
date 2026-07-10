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

// Flat (nation-agnostic) mark glyph: mark_1/2/3 = the 1/2/3-mark UI dashes. We use
// these for every tick rather than the nation gun-barrel decals (tk.icon) -- the
// decals carry flag backgrounds + detail that mush at tick size.
const FLAT_MARK = "img://gui/maps/icons/library/marksOnGun/mark_%d.png";

// Combined-damage glyph for the tooltip's current-damage row -- the same personal-
// missions "battle condition: damage" art the top-left readout uses (see the .css).
const DMG_ICON = "img://gui/maps/icons/personal_missions_30/quest_type/128x128/icon_battle_condition_damage.png";

// Localized label bundle, pushed from Python as a JSON string on the model (`labels`).
// The JS renders whatever the model carries and hardcodes NO English (see the
// wotmod-gameface-widget Localization convention). Parsed missing-key-safe: a missing
// key degrades to "" rather than crashing or blanking the whole tooltip.
let LABELS = {};
function parseLabels(s) {
    try { return (s && JSON.parse(s)) || {}; } catch (e) { return {}; }
}
function L(key) { return (LABELS && LABELS[key]) || ""; }

// Group an integer with thousands separators: 2910 -> "2,910".
function thousands(n) {
    n = Math.max(0, Math.round(Number(n) || 0));
    return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// Percentile float -> "84.73%" (two decimals, TRUNCATED not rounded); 0 -> "0%".
// The game supplies 0.01 granularity (getDamageRating divides by 100), so 2 decimals is
// the natural non-spurious maximum. We truncate (floor) rather than round so the readout
// never overstates progress toward a mark threshold (e.g. 84.999 shows "84.99%", not "85").
function pctText(p) {
    p = Math.floor((Number(p) || 0) * 100) / 100;   // truncate to 2dp first
    if (p <= 0) return "0%";
    return p.toFixed(2) + "%";
}

// Piecewise axis: map a percentile (0..100) to a position along the bar (0..100 %).
// The bar spans the FULL width, divided into 4 EQUAL-WIDTH regions at the milestone
// boundaries -- below 65 | 65-85 | 85-95 | 95-100 -- each region an even quarter
// (25%) of the bar WIDTH. Equal quarters spread the crowded high-percentile marks
// (65/85/95) evenly (25%/50%/75%) instead of bunching them at the tail, while still
// filling the whole bar. PCT_STOPS = the percentile region boundaries; BAR_STOPS = their
// bar-width positions. Applied to BOTH the fill width and every tick's position so they
// stay consistent; the CSS boundary guides (.moe-tick-notch at 65/85/95, .moe-end at 100)
// are positioned to the same stops (ticks data-driven via barX).
const PCT_STOPS = [0, 65, 85, 95, 100];   // percentile region boundaries
const BAR_STOPS = [0, 25, 50, 75, 100];   // bar-width % (equal quarters)
function barX(percentile) {
    const p = Math.max(0, Math.min(100, Number(percentile) || 0));
    for (let i = 1; i < PCT_STOPS.length; i++) {
        if (p <= PCT_STOPS[i]) {
            const t = (p - PCT_STOPS[i - 1]) / (PCT_STOPS[i] - PCT_STOPS[i - 1]);
            return BAR_STOPS[i - 1] + t * (BAR_STOPS[i] - BAR_STOPS[i - 1]);
        }
    }
    return 100;
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
        '    <span class="moe-cur-icon"></span>' +
        '  </span>' +
        '</div>' +
        '<div class="moe-body">' +
        '  <div class="moe-track">' +
        '    <div class="moe-fill"></div>' +
        '    <div class="moe-end"></div>' +
        '    <div class="moe-end-label"></div>' +
        '    <div class="moe-cur-marker"></div>' +
        '    <div class="moe-cur-pct"></div>' +
        '    <div class="moe-ticks"></div>' +
        '  </div>' +
        '</div>';
    document.body.appendChild(root);
    return root;
}

function markIcon(count) {
    // Flat glyph for the given mark level (1/2/3, already clamped by the caller).
    return FLAT_MARK.replace("%d", String(count));
}

function renderTicks(ticksEl, ticks) {
    ticksEl.innerHTML = "";
    for (let i = 0; i < ticks.length; i++) {
        const tk = unwrap(ticks[i]);
        const el = document.createElement("div");
        const count = Math.max(1, Math.min(3, tk.markCount || 1));
        el.className = "moe-tick moe-tick-m" + count + (tk.reached ? " moe-tick-reached" : "");
        el.style.left = barX(tk.percent || 0) + "%";

        // Nation mark art ON TOP of the bar.
        const icon = document.createElement("div");
        icon.className = "moe-tick-icon";
        icon.style.backgroundImage = "url(" + markIcon(count) + ")";
        el.appendChild(icon);

        // A small notch sitting on the track at the milestone.
        const notch = document.createElement("div");
        notch.className = "moe-tick-notch";
        el.appendChild(notch);

        // Damage requirement BELOW the mark (blank when unknown -> table not loaded yet /
        // vehicle absent / estimator has no sample).
        const req = document.createElement("div");
        req.className = "moe-tick-req";
        req.textContent = (tk.damageRequired > 0) ? thousands(tk.damageRequired) : "";
        el.appendChild(req);

        ticksEl.appendChild(el);
    }
}

// Hover tooltip master switch. Off for now (WIP layout) -- flip to true to re-enable.
// When false, renderTooltip() bails early so the host node is never built and no hover
// listeners are bound (ensureTooltip is reached only through renderTooltip).
const TOOLTIP_ENABLED = false;

// Build the hover tooltip host ONCE (body-level, position:fixed so it escapes the root
// padding/frame) and bind the whole-widget hover on #moe-root. render() only updates the
// row text/classes -- it never rebuilds this node, which would drop an open tooltip
// mid-hover (see the harness Tooltips guidance). The tooltip stays pointer-events:none
// (CSS) so it never steals the hangar's drag-to-rotate.
function ensureTooltip() {
    let tip = document.getElementById("moe-tooltip");
    if (tip) return tip;
    tip = document.createElement("div");
    tip.id = "moe-tooltip";
    tip.innerHTML =
        '<div class="moe-tt-title"></div>' +
        '<div class="moe-tt-grid">' +
        '  <div class="moe-tt-grid-row"></div>' +
        '  <div class="moe-tt-grid-row"></div>' +
        '</div>' +
        '<div class="moe-tt-sep"></div>' +
        '<div class="moe-tt-foot">' +
        '  <span class="moe-tt-foot-dmg">' +
        '    <span class="moe-tt-foot-ico" style="background-image:url(' + DMG_ICON + ')"></span>' +
        '    <span class="moe-tt-foot-dmg-val"></span>' +
        '  </span>' +
        '  <span class="moe-tt-foot-pct"></span>' +
        '</div>';
    document.body.appendChild(tip);

    // The four requirement cells: three marks (65/85/95) + the 100% goalpost, laid out
    // 2x2 (two cells per grid row). Built once; render() fills glyph/text/classes.
    const gridRows = tip.querySelectorAll(".moe-tt-grid-row");
    for (let i = 0; i < 4; i++) {
        const cell = document.createElement("div");
        cell.className = "moe-tt-cell";
        cell.innerHTML =
            '<span class="moe-tt-cell-ico"></span>' +
            '<span class="moe-tt-cell-txt">' +
            '  <span class="moe-tt-cell-pct"></span>' +
            '  <span class="moe-tt-cell-dmg"></span>' +
            '</span>' +
            '<span class="moe-tt-cell-chk"></span>';
        gridRows[i < 2 ? 0 : 1].appendChild(cell);
    }

    const root = document.getElementById("moe-root");
    if (root) {
        root.addEventListener("mouseenter", function () {
            if (root.style.display === "none") return;
            tip.classList.add("moe-tt-open");
            positionTooltip(root, tip);
        });
        root.addEventListener("mouseleave", function () {
            tip.classList.remove("moe-tt-open");
        });
    }
    return tip;
}

// Fixed panel anchored to the widget: prefer above it, right-aligned to its edge, and
// edge-clamped inside the viewport so it never spills off-screen. Measured after the
// node is shown (a hidden node measures 0).
function positionTooltip(root, tip) {
    const r = root.getBoundingClientRect();
    // Match the tooltip's width to the widget's EXACT rendered width (px, box-sizing agnostic
    // -- #moe-tooltip is border-box, so this includes its frame). Set before measuring so the
    // height/edge-clamp below reflect the final width.
    tip.style.width = Math.round(r.width) + "px";
    const t = tip.getBoundingClientRect();
    const gap = 8;
    const vw = window.innerWidth || document.documentElement.clientWidth || 0;
    const vh = window.innerHeight || document.documentElement.clientHeight || 0;
    let top = r.top - t.height - gap;          // above the widget...
    if (top < gap) top = r.bottom + gap;        // ...or below if it would clip the top
    let left = r.right - t.width;               // right-aligned to the widget
    if (left + t.width > vw - gap) left = vw - gap - t.width;
    if (left < gap) left = gap;
    if (top + t.height > vh - gap) top = vh - gap - t.height;
    if (top < gap) top = gap;
    tip.style.left = Math.round(left) + "px";
    tip.style.top = Math.round(top) + "px";
}

function hideTooltip() {
    const tip = document.getElementById("moe-tooltip");
    if (tip) tip.classList.remove("moe-tt-open");
}

// Populate the tooltip from the model. The only text is the localized WG title (off the
// model's LABELS bundle -- no hardcoded English); everything else is language-neutral
// numbers, percentages, and the widget's own glyphs (mark art + the damage icon).
function renderTooltip(root, data) {
    if (!TOOLTIP_ENABLED) return;
    const tip = ensureTooltip();
    tip.querySelector(".moe-tt-title").textContent = L("title");

    // 2x2 requirement grid. Cells 0..2 = the three marks (65/85/95%) with the flat mark
    // glyph; cell 3 = the 100% goalpost (glyph-less). Each shows its percentile + required
    // combined damage; a reached mark brightens and carries a check.
    const ticks = (data.ticks || []).map(unwrap);
    const cells = tip.querySelectorAll(".moe-tt-grid .moe-tt-cell");
    for (let i = 0; i < 3; i++) {
        const cell = cells[i];
        const tk = ticks[i];
        const count = tk ? Math.max(1, Math.min(3, tk.markCount || (i + 1))) : (i + 1);
        cell.querySelector(".moe-tt-cell-ico").style.backgroundImage =
            "url(" + FLAT_MARK.replace("%d", String(count)) + ")";
        cell.querySelector(".moe-tt-cell-pct").textContent =
            tk ? (Math.round(tk.percent || 0) + "%") : "";
        cell.querySelector(".moe-tt-cell-dmg").textContent =
            (tk && tk.damageRequired > 0) ? thousands(tk.damageRequired) : "";
        cell.querySelector(".moe-tt-cell-chk").textContent = (tk && tk.reached) ? "✓" : "";
        cell.classList.toggle("moe-tt-cell-reached", !!(tk && tk.reached));
    }
    // 100% goalpost cell (index 3): no mark glyph, percent "100%", the end goalpost damage.
    const end = data.endDamageRequired || 0;
    const goal = cells[3];
    goal.querySelector(".moe-tt-cell-ico").style.backgroundImage = "";
    goal.querySelector(".moe-tt-cell-pct").textContent = "100%";
    goal.querySelector(".moe-tt-cell-dmg").textContent = end > 0 ? thousands(end) : "";
    goal.querySelector(".moe-tt-cell-chk").textContent = "";
    goal.classList.remove("moe-tt-cell-reached");

    // Footer: current combined-damage (left) and current percentile (right), opposite corners.
    tip.querySelector(".moe-tt-foot-dmg-val").textContent = thousands(data.curAvgDamage || 0);
    tip.querySelector(".moe-tt-foot-pct").textContent = pctText(data.curPercent || 0);

    if (tip.classList.contains("moe-tt-open")) positionTooltip(root, tip);
}

function render(model) {
    const root = ensureRoot();
    const data = unwrap(model && model.moeData);

    if (!data) {
        // Model not attached yet -- keep the widget hidden rather than flashing a stub.
        root.style.display = "none";
        hideTooltip();
        return;
    }

    // Python pushes visible=false off the plain garage / while a tank-setup overlay is
    // open. An absent flag (older Python) is treated as visible.
    if (data.visible === false) { root.style.display = "none"; hideTooltip(); return; }
    root.style.display = "";

    // Localized tooltip labels ride on the model as a JSON bundle; parse missing-key-safe.
    LABELS = parseLabels(data.labels);

    // Responsive bottom offset: tag the root with the carousel geometry so the CSS can
    // lift the bar clear of a single / small-double / tall-double carousel.
    root.classList.toggle("moe-rows2", Number(data.carouselRows) === 2);
    root.classList.toggle("moe-small", !!data.carouselSmall);

    // Readout: current average combined damage (top-left, above the bar) + current mark
    // percentage (used as the last tick's top label, above the bar's 100% end).
    // A never-played tank genuinely reads 0 (synchronous dossier read, not the async
    // thresholds table), so show explicit 0 / 0% rather than a "—" placeholder-for-unknown.
    const dmg = data.curAvgDamage || 0;
    const pct = data.curPercent || 0;
    root.querySelector(".moe-cur-dmg").textContent = thousands(dmg);   // 0 -> "0"
    root.querySelector(".moe-cur-pct").textContent = pctText(pct);      // 0 -> "0%"

    // Fill to the current percentile, mapped through the piecewise axis (barX) so the
    // fill edge and the milestone ticks share the same split scale, and place the
    // leading-edge marker at the same spot (mimics the Battlepass in-chapter leading edge).
    const fill = Math.max(0, Math.min(100, Number(data.fill) || 0));
    root.querySelector(".moe-fill").style.width = barX(fill) + "%";
    root.querySelector(".moe-cur-marker").style.left = barX(fill) + "%";

    // 100% end-cap: the combined-damage goalpost for the 100th percentile, shown to the
    // RIGHT of the bar's end (not below, where it would overlap the 95% mark number).
    // Blank when the external table hasn't supplied it yet.
    const endReq = data.endDamageRequired || 0;
    root.querySelector(".moe-end-label").textContent = endReq > 0 ? thousands(endReq) : "";

    renderTicks(root.querySelector(".moe-ticks"), (data.ticks || []));

    // Hover tooltip: full localized stats breakdown (updates in place; kept open if the
    // user is already hovering when a re-push arrives).
    renderTooltip(root, data);
}

engine.whenReady.then(() => {
    observer.onUpdate(render);
    observer.subscribe();
    render(observer.model);
});
