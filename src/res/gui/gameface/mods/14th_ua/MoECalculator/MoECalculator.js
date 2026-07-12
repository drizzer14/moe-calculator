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

// The big nation mark art for the tooltip header -- the client's own "huge icon"
// (getHugeIcon): marksOnGun 180x180 atlas, keyed by the vehicle's nation + mark count.
// Matches the client's MoE award tooltip. count clamps to 1..3; a 0-mark vehicle shows
// the 3-mark art (what you can earn), exactly as the client does (currentValue = 3 if 0).
function bigMarkIcon(nation, marks) {
    const count = (marks | 0) <= 0 ? 3 : Math.min(3, marks | 0);
    const suffix = count < 2 ? "mark" : "marks";
    return "img://gui/maps/icons/marksOnGun/180x180/" + (nation || "ussr") + "_" + count + "_" + suffix + ".png";
}

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

// Bare 2-decimal percentile figure (no "%"), truncated like pctText: "84.73".
function pctNum(p) {
    return (Math.floor((Number(p) || 0) * 100) / 100).toFixed(2);
}

// Build the tooltip's "current ratio" line from the localized WG template
// (#tooltips:achievement/marksOnGunCount). This engine has NO inline formatting -- ANY child
// element (span/font, any `display`) drops onto its own line; only flexbox lays boxes out
// horizontally (confirmed by live probe; see the sibling wgmod-research-progress note). So the
// ratio line is a flex-wrap row (see .moe-tip-ratio) and we emit ONE <span> PER WORD -- each a
// flex item that wraps like text -- with the word(s) inside the WG template's colour tags
// carrying `.moe-tip-hi` (white). Placeholders are filled as the client fills them: color_tag_*
// delimit the highlighted run (marked here with \x01/\x02 sentinels, stripped as we tokenize),
// `count` is the truncated percentile, `%%` a single `%`. The embedded newline + doubled spaces
// collapse first so the split yields clean words. Returns "" when the string is absent.
function ratioHtml(pct) {
    const tpl = L("ratio");
    if (!tpl) return "";
    const marked = tpl
        .replace("%(color_tag_open)s", "\x01")
        .replace("%(color_tag_close)s", "\x02")
        .replace("%(count)s", pctNum(pct))
        .replace(/%%/g, "%")
        .replace(/\s*\n\s*/g, " ")
        .replace(/\s{2,}/g, " ")
        .trim();
    const words = marked.split(" ");
    let hot = false, html = "";
    for (let i = 0; i < words.length; i++) {
        let w = words[i];
        if (w.indexOf("\x01") !== -1) { hot = true; w = w.replace(/\x01/g, ""); }
        let closeAfter = false;
        if (w.indexOf("\x02") !== -1) { closeAfter = true; w = w.replace(/\x02/g, ""); }
        if (w) html += "<span" + (hot ? ' class="moe-tip-hi"' : "") + ">" + w + "</span>";
        if (closeAfter) hot = false;
    }
    return html;
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

// Hover tooltip master switch. When false, renderTooltip() bails early so the host node
// is never built and no hover listeners are bound (ensureTooltip is reached only through
// renderTooltip).
const TOOLTIP_ENABLED = true;

// Hover-intent delay (ms) before a sustained hover reveals the tooltip, so a quick pass over
// the bar doesn't flash it (matches the client's own tooltip dwell). The pending timer is
// cleared on mouseleave and whenever the widget hides.
const TOOLTIP_DELAY_MS = 400;
let ttShowTimer = 0;

// Build the hover tooltip host ONCE (body-level, position:fixed so it escapes the root
// padding/frame) and bind the whole-widget hover on #moe-root. render() only updates the
// text/classes -- it never rebuilds this node, which would drop an open tooltip mid-hover
// (see the harness Tooltips guidance). The tooltip stays pointer-events:none (CSS) so it
// never steals the hangar's drag-to-rotate.
//
// Layout mirrors the client's native MoE award tooltip: the big nation mark art beside the
// title + current-ratio line, then the description, a divider, and the condition rules.
function ensureTooltip() {
    let tip = document.getElementById("moe-tooltip");
    if (tip) return tip;
    tip = document.createElement("div");
    tip.id = "moe-tooltip";
    // Reuse the shared `.wg-tooltip` / `.wg-tip-*` tooltip component (the same class
    // vocabulary the sibling wgmod-research-progress mod uses -- both mods render identically,
    // but each ships its OWN standalone copy of the CSS, scoped to its root). Text column
    // (title + ratio + description) inside .wg-tip-main, with the mark art pinned to the
    // top-RIGHT out of flow (.wg-tip-icon). The divider + condition span full width below.
    // MoE-local hooks: .moe-tip-ratio / .moe-tip-descr (JS targets; both styled by the shared
    // .wg-tip-effect body row); condition bullets are shared .wg-tip-effect rows too.
    tip.className = "wg-tooltip";
    tip.innerHTML =
        '<div class="wg-tip-main wg-tip-main-mark">' +
        '  <div class="wg-tip-text">' +
        '    <div class="wg-tip-name"></div>' +
        '    <div class="wg-tip-effect moe-tip-ratio"></div>' +
        '  </div>' +
        '  <div class="wg-tip-icon wg-tip-icon-mark"></div>' +
        '</div>' +
        // The description is a FULL-WIDTH paragraph OUTSIDE .wg-tip-main -- it sits below the
        // mark art, so it must not be squeezed into the icon's reserved right column; as a
        // top-level block it uses the whole tooltip width like the divider + conditions.
        '<div class="wg-tip-effect moe-tip-descr"></div>' +
        '<div class="wg-tip-div"></div>' +
        '<div class="wg-tip-cond"></div>';
    document.body.appendChild(tip);

    const root = document.getElementById("moe-root");
    if (root) {
        root.addEventListener("mouseenter", function () {
            if (root.style.display === "none") return;
            clearTimeout(ttShowTimer);
            ttShowTimer = setTimeout(function () {
                if (root.style.display === "none") return;   // widget hid during the delay
                tip.classList.add("moe-tt-open");
                positionTooltip(root, tip);
            }, TOOLTIP_DELAY_MS);
        });
        root.addEventListener("mouseleave", function () {
            clearTimeout(ttShowTimer);
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
    // Match the tooltip's width to the widget's EXACT rendered px width (box-sizing:border-box,
    // so this includes the frame). Set before measuring so the height/edge-clamp reflect it.
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
    clearTimeout(ttShowTimer);   // drop any pending delayed-show so it can't fire off-widget
    const tip = document.getElementById("moe-tooltip");
    if (tip) tip.classList.remove("moe-tt-open");
}

// Populate the tooltip from the model -- the client's own MoE award tooltip. All text is
// localized off the model's LABELS bundle (no hardcoded English); the mark art is the
// vehicle's own nation icon. Title/description are keyed by the current mark count
// (title0..3 / descr0..3): at 0 marks the blurb tells you how to earn the 1st, at 3 it
// reads "maximum obtained" -- exactly as the client does.
function renderTooltip(root, data) {
    if (!TOOLTIP_ENABLED) return;
    const tip = ensureTooltip();
    const marks = Math.max(0, Math.min(3, Number(data.marks) || 0));

    const iconEl = tip.querySelector(".wg-tip-icon");
    iconEl.style.backgroundImage = "url(" + bigMarkIcon(data.nation, marks) + ")";
    // 0 marks: dim the (aspirational 3-mark) art -- the client shows an unearned mark faint
    // in its own statistics/awards tooltip.
    iconEl.classList.toggle("wg-tip-icon-unearned", marks === 0);
    tip.querySelector(".wg-tip-name").textContent = L("title" + marks);
    tip.querySelector(".moe-tip-descr").textContent = L("descr" + marks);

    // Current-ratio line: shown only when the client would (a real percentile > 0), matching
    // the native tooltip's localizedValue (empty at damageRating <= 0). Plain inline text.
    const ratio = tip.querySelector(".moe-tip-ratio");
    const pct = Number(data.curPercent) || 0;
    if (pct > 0) {
        ratio.innerHTML = ratioHtml(pct);
        ratio.classList.remove("moe-tip-empty");
    } else {
        ratio.innerHTML = "";
        ratio.classList.add("moe-tip-empty");
    }

    // Condition rules: one localized '\n'-separated block -> one line per bullet, each a
    // shared .wg-tip-effect body row (same rhythm as the ratio + description above).
    const cond = tip.querySelector(".wg-tip-cond");
    cond.innerHTML = "";
    const lines = (L("condition") || "").split("\n");
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;
        const el = document.createElement("div");
        el.className = "wg-tip-effect";
        el.textContent = line;
        cond.appendChild(el);
    }

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

/* Match the widget's size to WG's bottom-bar slot boxes (crew/equip/directive/ammo/
   consumables). Those boxes scale with the VIEWPORT (like the carousel), while the widget is
   sized in rem (= interfaceScale px). interfaceScale is power-of-two gated, so at 1440p (x1,
   taller viewport) the rem widget is too SHORT vs the boxes. We rescale the whole widget by
       k = innerHeight / (SIZE_REF * scale)
   The boxes are a BLEND of scale and viewport (pure-viewport over-grows the widget at 1440p),
   so the rescale is
       k = 1 + GROWTH * (vp/scale - SIZE_REF) / SIZE_REF ,   vp/scale = innerHeight / (1rem px)
   which is EXACTLY 1.0 at 4K (vp/scale = 2160/2 = 1080) and 1080p (1080/1) -- where the rem
   design already matches the boxes -- and grows for taller viewports at the same scale (1440p:
   vp/scale = 1440). GROWTH picks how much of that viewport growth to follow: 0 = pure rem
   (too short at 1440p), 1 = pure viewport (too tall). GROWTH=0.625 was calibrated LIVE at
   1440p against the slot boxes (k=1.208). Anchored at the bottom-right corner (transform-origin)
   so the calibrated `bottom`/`right` anchor holds; the box grows up and to the left. SIZE_REF=
   1080 is fixed by "widget matches boxes at 4K" (also the exact-match point at 1080p). */
var SIZE_REF = 1080;
var GROWTH = 0.625;
function widgetScale(remPx) {
    return 1 + GROWTH * (window.innerHeight / remPx - SIZE_REF) / SIZE_REF;
}
function applyWidgetScale() {
    var root = document.getElementById("moe-root");
    if (!root) return;
    var remPx = parseFloat(getComputedStyle(document.documentElement).fontSize) || 1;
    root.style.transformOrigin = "100% 100%";
    root.style.transform = "scale(" + widgetScale(remPx) + ")";
}
engine.whenReady.then(function () {
    applyWidgetScale();
    window.addEventListener("resize", applyWidgetScale);
});
