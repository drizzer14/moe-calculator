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

// Reverse-channel command names -- mirror bridge/view_models.py MoEVM commands.
const CMD = { SET_POSITION: "setPosition" };

// Invoke a reverse-channel command on our MoEVM (exposed as `moeData` on the host model).
// Wulf surfaces a ViewModel command as a callable on the model; whether it lives on the
// wrapped proxy or its unwrapped value can differ across builds, so try both. Wulf commands
// take a single MAP argument (a raw scalar is rejected as "not a map"); a map arg (setPosition's
// {x, y, w, h}) passes through as-is, a scalar is wrapped {value:...}, and a no-arg call passes {}.
function invokeCommand(name, arg) {
    try {
        const vm = observer.model && observer.model.moeData;
        let host = null;
        if (vm && typeof vm[name] === "function") host = vm;
        else {
            const inner = unwrap(vm);
            if (inner && typeof inner[name] === "function") host = inner;
        }
        if (!host) { console.error("[moe] command missing: " + name); return; }
        if (arg === undefined || arg === null) host[name]({});
        else if (typeof arg === "object") host[name](arg);
        else host[name]({ value: arg });
    } catch (e) {
        console.error("[moe] invokeCommand failed: " + name, e);
    }
}

// Current Gameface viewport (px). setPosition records this alongside the pinned px so a later
// resolution / UI-scale change rescales the position proportionally (see applyPosition).
function currentVP() {
    return { w: window.innerWidth || 0, h: window.innerHeight || 0 };
}

// --- Drag-to-reposition: pin-state anchor helpers ----------------------------------
// The widget has TWO anchor modes (see the plan / .css). AUTO: the CSS bottom-right anchor
// (right/bottom + transform-origin 100% 100%), no inline left/top -- resolution-relative,
// re-derived every viewport. PINNED: a top-LEFT anchor (transform-origin 0 0, right/bottom
// cleared, inline left/top px) -- with origin 0 0 the scaled box's top-left equals left/top,
// so drag math + clamping stay predictable under the transform:scale(k). We store the top-left.
// _moePinned drives applyWidgetScale's transform-origin so a scale re-arm keeps the right anchor.

function enterPinAnchor(root, left, top) {
    root._moePinned = true;
    root.style.transformOrigin = "0 0";
    root.style.right = "auto";
    root.style.bottom = "auto";
    root.style.left = Math.round(left) + "px";
    root.style.top = Math.round(top) + "px";
}

function clearPinAnchor(root) {
    root._moePinned = false;
    root.style.transformOrigin = "100% 100%";
    // clear the inline overrides so the resolution-relative CSS bottom-right anchor re-derives.
    root.style.left = "";
    root.style.top = "";
    root.style.right = "";
    root.style.bottom = "";
}

// Measure the AUTO-anchor top (px) for the CURRENT carousel state without disturbing the pin:
// momentarily clear the pin (restore right/bottom + origin 100% 100%, drop inline left/top),
// force a reflow, read getBoundingClientRect().top, then restore the exact prior inline styles.
// Synchronous (no paint between), so it never flickers. Used for the Follow-Carousel nudge.
function measureAutoTop(root) {
    const s = root.style;
    const savedLeft = s.left, savedTop = s.top, savedRight = s.right,
          savedBottom = s.bottom, savedOrigin = s.transformOrigin;
    s.left = ""; s.top = ""; s.right = ""; s.bottom = "";
    s.transformOrigin = "100% 100%";
    void root.offsetHeight;   // force reflow so the CSS anchor is applied before we measure
    const top = root.getBoundingClientRect().top;
    s.left = savedLeft; s.top = savedTop; s.right = savedRight;
    s.bottom = savedBottom; s.transformOrigin = savedOrigin;
    return top;
}

// Apply the user's dragged position (px, top-left), or fall back to the CSS default. posX/posY
// are the top-left px, both 0 == "auto". PINNED (posX/posY > 0): the stored px were captured at
// data.posW x data.posH; if the current viewport differs, rescale proportionally, apply, and
// echo the rescaled px + new capture size back so it converges (the next push carries posW/posH
// == the current viewport). A pin with NO recorded capture size (typed into the steppers, or a
// pre-fix save) adopts the current viewport so a LATER change can rescale it. AUTO (0/0): clear
// the inline override so the resolution-relative CSS default re-derives. Never fights an
// in-progress drag; a no-op for an older Python build that doesn't push posX.
function applyPosition(root, data) {
    if (root._moeDragging) return;
    if (!data || data.posX === undefined) return;
    const vp = currentVP();
    const x = data.posX | 0;
    const y = data.posY | 0;
    if (x > 0 && y > 0) {
        let ax = x, ay = y;
        const rw = data.posW | 0, rh = data.posH | 0;
        if (rw && rh && vp.w && vp.h && (rw !== vp.w || rh !== vp.h)) {
            ax = Math.round(x * vp.w / rw);
            ay = Math.round(y * vp.h / rh);
            invokeCommand(CMD.SET_POSITION, { x: ax, y: ay, w: vp.w, h: vp.h });
        } else if ((!rw || !rh) && vp.w && vp.h) {
            invokeCommand(CMD.SET_POSITION, { x: x, y: y, w: vp.w, h: vp.h });
        }
        enterPinAnchor(root, ax, ay);
        // Baseline for the Follow-Carousel nudge: the auto top in the CURRENT carousel state.
        // Set on every apply so the first post-mount carousel toggle has a correct reference.
        root._moeLastAutoTop = measureAutoTop(root);
        return;
    }
    clearPinAnchor(root);
    root._moeLastAutoTop = undefined;   // auto follows the carousel via CSS -- no nudge baseline
}

// Ctrl+drag to reposition the widget. Ctrl-gated so a normal hover/click can't move it. On
// mousedown we switch to the top-left anchor at the current on-screen top-left (no visual jump),
// then track the cursor; Shift locks to the dominant axis (re-evaluated every move). On release
// we report the final top-left px to Python via setPosition (a BARE map), which persists it and
// re-pushes; applyPosition then re-applies the same coords. Hidden tooltip + _moeDidDrag guard
// the trailing synthetic click / reopen.
//
// The drag-start listener lives on `document` in the CAPTURE phase, NOT on #moe-root in bubble.
// Reason (cross-mod collision): OpenWG injects several mods into the SAME hangar document as
// body siblings at similar z-index, and any number of them may be independently draggable.
// Capturing on document lets our handler run for EVERY mousedown, so `e.target` is the true
// hit-tested topmost pointer-events:auto element under the cursor -- and ownership is decided by
// `root.contains(e.target)`: we claim the drag ONLY when the mousedown actually landed on OUR
// widget's DOM subtree, and we NEVER stopImmediatePropagation for anyone else's mousedown. That
// is what makes this coexist with ANY number of other draggable mods (not just one known
// sibling) and be INDEPENDENT of listener registration / mount order -- a rect hit-test can't do
// this, because two overlapping widgets' rects can both contain the point and the first-
// registered capture listener would win nondeterministically.
//
// It works because of our pointer-events layering (MoECalculator.css): #moe-root is
// pointer-events:auto on its footprint while every overhanging child (ticks, markers, end
// labels) is pointer-events:none -- so `e.target` resolves to our root only when the pointer is
// genuinely over our interactive footprint, and any interactive child still lives under
// #moe-root so contains() covers it. Where our visible footprint overlaps another equal-z
// widget's transparent overhang, #moe-root's z-index:9001 (one above the 9000 baseline) makes
// OUR footprint the topmost painted element there, so hit-testing matches the visual stacking.
let _moeDragBound = false;   // idempotent: the document listener must be added exactly once
function installDrag() {
    if (_moeDragBound) return;   // ensureRoot()/mount may run repeatedly; never stack listeners
    _moeDragBound = true;
    document.addEventListener("mousedown", function (e) {
        const root = document.getElementById("moe-root");
        // Ownership: bail (plain return, NO stopImmediatePropagation) unless the widget exists,
        // is shown, Ctrl is held, AND the mousedown landed inside OUR DOM subtree. Target-based
        // hit-test (root.contains) -- the true topmost pointer-events:auto element -- so we only
        // ever claim a mousedown on our own widget and never stop the event for another mod's.
        if (!root || root.style.display === "none") return;
        if (!e.ctrlKey) return;
        if (!root.contains(e.target)) return;
        // It IS our drag: pre-empt any other mod's mousedown (stopImmediatePropagation also stops
        // any later document-capture listener + all bubbling) so nothing else can grab the drag.
        e.stopImmediatePropagation();
        e.preventDefault();
        const r0 = root.getBoundingClientRect();
        const boxW = r0.width, boxH = r0.height;   // scaled rendered size (clamp basis)
        const offX = e.clientX - r0.left;          // cursor -> top-left x
        const offY = e.clientY - r0.top;           // cursor -> top-left y
        const startLeft = Math.round(r0.left);
        const startTop = Math.round(r0.top);
        // Switch to the top-left anchor at the current on-screen position -- no jump.
        enterPinAnchor(root, startLeft, startTop);
        root._moeDragging = true;
        root._moeDidDrag = true;
        root.style.cursor = "move";
        hideTooltip();   // suppress the hover tooltip while dragging (reopen guarded too)
        const onMove = function (ev) {
            const w = window.innerWidth || 0;
            const h = window.innerHeight || 0;
            let cx = ev.clientX - offX;
            let cy = ev.clientY - offY;
            // clamp so the whole box stays on-screen. y floored at 1 (0 is the auto sentinel).
            if (w) cx = Math.max(0, Math.min(w - boxW, cx));
            if (h) cy = Math.max(1, Math.min(h - boxH, cy));
            // Shift axis-lock (Photoshop-style), re-evaluated every move so releasing/holding
            // Shift or changing the dominant direction switches the locked axis live.
            if (ev.shiftKey) {
                const dx = cx - startLeft, dy = cy - startTop;
                if (Math.abs(dx) >= Math.abs(dy)) cy = startTop; else cx = startLeft;
            }
            root.style.left = Math.round(cx) + "px";
            root.style.top = Math.round(cy) + "px";
        };
        const onUp = function () {
            document.removeEventListener("mousemove", onMove, true);
            document.removeEventListener("mouseup", onUp, true);
            root._moeDragging = false;
            root.style.cursor = "";
            const r = root.getBoundingClientRect();
            const vp = currentVP();
            invokeCommand(CMD.SET_POSITION, {
                x: Math.max(1, Math.round(r.left)),   // never 0 (the auto sentinel)
                y: Math.max(1, Math.round(r.top)),
                w: vp.w, h: vp.h,
            });
            // Hold _moeDidDrag through the click that fires right after mouseup, then clear.
            setTimeout(function () { root._moeDidDrag = false; }, 0);
        };
        // capture phase so a fast drag that leaves the box still tracks + releases.
        document.addEventListener("mousemove", onMove, true);
        document.addEventListener("mouseup", onUp, true);
    }, true);   // CAPTURE on document: fires for EVERY mousedown so e.target is the real hit element
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
    installDrag();   // Ctrl+drag reposition (document-capture listener, bound exactly once)
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
            if (root._moeDragging || root._moeDidDrag) return;   // never open mid-drag / just after
            clearTimeout(ttShowTimer);
            ttShowTimer = setTimeout(function () {
                if (root.style.display === "none") return;   // widget hid during the delay
                if (root._moeDragging || root._moeDidDrag) return;   // a drag started during the delay
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

    // Keep the last-pushed data for the viewport-resize hook (which re-applies position).
    root._moeLastData = data;

    // Responsive bottom offset: tag the root with the carousel geometry so the CSS can
    // lift the bar clear of a single / small-double / tall-double carousel. Detect a CHANGE
    // (vs the previous render) so a PINNED widget can follow the carousel's vertical shift.
    const rows2 = Number(data.carouselRows) === 2;
    const small = !!data.carouselSmall;
    const carSig = (rows2 ? 2 : 1) * 10 + (small ? 1 : 0);
    const prevAutoTop = root._moeLastAutoTop;   // baseline from the PREVIOUS carousel state
    const carouselChanged = root._moeCarSig !== undefined && root._moeCarSig !== carSig;
    root.classList.toggle("moe-rows2", rows2);
    root.classList.toggle("moe-small", small);
    root._moeCarSig = carSig;

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

    // Position: apply the persisted pin (or the auto CSS default). This also refreshes
    // _moeLastAutoTop to the auto top in the CURRENT carousel state.
    applyPosition(root, data);

    // Follow Carousel Mode: when the carousel state changed AND the widget is pinned AND the
    // setting is on, nudge the pin vertically by the auto-anchor's shift so it keeps clearing
    // the carousel, then echo the new position back so it persists. Carousel changes are
    // vertical-only -- X is never nudged. Skipped when unpinned (auto follows via CSS) or off.
    if (carouselChanged && root._moePinned && data.followCarousel &&
        prevAutoTop !== undefined && root._moeLastAutoTop !== undefined) {
        const delta = root._moeLastAutoTop - prevAutoTop;   // how far the auto anchor moved
        if (delta) {
            const vp = currentVP();
            const curLeft = parseFloat(root.style.left) || (data.posX | 0);
            const curTop = parseFloat(root.style.top) || (data.posY | 0);
            let newTop = Math.round(curTop + delta);
            if (vp.h) {
                const boxH = root.getBoundingClientRect().height;
                newTop = Math.min(newTop, Math.max(1, vp.h - boxH));
            }
            newTop = Math.max(1, newTop);
            root.style.top = newTop + "px";
            invokeCommand(CMD.SET_POSITION, {
                x: Math.max(1, Math.round(curLeft)), y: newTop, w: vp.w, h: vp.h,
            });
        }
    }
}

// Cold-mount self-heal. The widget repaints only when its ModelObserver's data-changed callback
// fires (observer.onUpdate -> render). But on a freshly mounted sub-view the engine does NOT
// deliver that callback until the view next composites -- which in the idle garage (or with the
// settings overlay open) only happens when the camera moves. So an idle-garage push -- an MSA
// per-mod reset or a stepper-to-0 that zeroes the position -- is dropped and the bar stays pinned
// until the player nudges the camera (then every queued update lands at once). The first paint
// works only because it's a DIRECT render() call below, not observer-driven.
//
// Fix: poll a cheap monotonic counter (moeData.rev, bumped by Python FIRST on every push) and
// render when it changes. This runs even when the data-changed event is dormant, so the bar
// follows pushes within one poll interval. Idle cost is a shallow field read + compare; a real
// render happens only when rev actually moves, so no spurious rebuilds. applyPosition (called by
// render) already respects the _moeDragging guard, so a poll never fights an active drag.
let _lastRev = null;

function revOf(model) {
    const data = unwrap(model && model.moeData);
    return data && data.rev !== undefined ? data.rev : null;
}

function renderAndTrack(model) {
    _lastRev = revOf(model);
    render(model);
}

function pollForChanges() {
    const rev = revOf(observer.model);
    if (rev !== null && rev !== _lastRev) renderAndTrack(observer.model);
}

engine.whenReady.then(() => {
    observer.onUpdate(renderAndTrack);   // warm path: instant repaint when the event fires
    observer.subscribe();
    renderAndTrack(observer.model);      // direct initial paint (observer event not needed)
});

/* Resolution-calibrated size law. k depends only on the LOGICAL viewport
   height (innerHeight/remPx): k=1 at the 1080 reference (so 1080p@x1 and 4K@x2,
   which share logical vp 1080, render at the same accepted screen fraction),
   growing by GROWTH per +1080 logical px. GROWTH is the single free knob
   (governs 1440p@x1 and 4K@x1); tuned live in-game, then baked.

   SATURATION CLAMP: the logical viewport is capped at LVP_CAP=1440 before the
   growth term, so growth SATURATES at 1440 logical px. This makes 1440p@x1
   (lvp 1440) and 4K@x1 (lvp 2160 -> clamped to 1440) render at the IDENTICAL
   size (same k). Below 1440 nothing changes: 1080p@x1 (lvp 1080) and 4K@x2
   (lvp 1080) still give k=1. The paired position-law clamp (min(26.11vh,376px)
   in the CSS bottom anchor) makes their GAP identical too.

   The content is authored in rem (1rem == interfaceScale px == remPx); we rescale
   it by k, anchored at the bottom-right corner (transform-origin 100% 100%) so the
   calibrated `bottom`/`right` anchor holds; the box grows up and to the left. */
var SIZE_REF = 1080;     // logical-viewport reference height (k=1 here)
var CAL_REMPX = 2;       // interface scale (root font px) at which the x2 size was verified correct
var LVP_CAP = 1440;      // logical-viewport saturation point: growth stops past 1440 -> 1440p@x1 == 4K@x1
function widgetScale(remPx) {
    remPx = remPx || CAL_REMPX;
    var GROWTH = 0.625;   // size slope: +GROWTH per +SIZE_REF logical px
    // k=1 at the 1080 logical-vp reference, growing by GROWTH per +1080 logical px,
    // SATURATING at LVP_CAP=1440 logical px (so 1440p@x1 and 4K@x1 collapse to one k).
    var lvp = Math.min(window.innerHeight / remPx, LVP_CAP);
    var k = 1 + GROWTH * (lvp - SIZE_REF) / SIZE_REF;
    if (remPx >= 2) { k *= 132 / 136; }   // x2 anchor trim: 136px -> 132px (4K@x2 only)
    return k;
}
var _lastRemPx = 0;
var _lastIH = 0;
function readRemPx() {
    return parseFloat(getComputedStyle(document.documentElement).fontSize) || CAL_REMPX;
}
function applyWidgetScale() {
    var root = document.getElementById("moe-root");
    if (!root) return;
    var remPx = readRemPx();
    _lastRemPx = remPx;
    _lastIH = window.innerHeight;
    // The transform carries only the resolution-calibrated scale. The transform-origin depends
    // on the anchor mode: bottom-right (100% 100%) so the CSS bottom/right anchor holds when
    // AUTO; top-left (0 0) when PINNED so the inline left/top anchor holds (drag math relies on
    // the scaled box's top-left equalling left/top). Never touch the inline left/top set by
    // drag / applyPosition here.
    root.style.transformOrigin = root._moePinned ? "0 0" : "100% 100%";
    root.style.transform = "scale(" + widgetScale(remPx) + ")";
    // 4K@x2 only: widen the box by ~32 screen px extending LEFT (right-anchored origin).
    // Base width is 315rem (MoECalculator.css). At x2 1rem=2px and k=132/136, so
    // +16.5rem -> +16.5*2*(132/136) ~= 32 screen px. Reset to "" everywhere else so a
    // live resolution/interfaceScale change re-arms cleanly to the CSS default.
    if (remPx >= 2 && window.innerHeight >= 2160) { root.style.width = "331.5rem"; }
    else { root.style.width = ""; }
}
function pollWidgetScale() {
    if (!document.getElementById("moe-root")) return;
    if (readRemPx() !== _lastRemPx || window.innerHeight !== _lastIH) applyWidgetScale();
}
// A screen-resolution / UI-scale change resizes the Gameface viewport but does NOT re-push the
// model, so applyPosition wouldn't otherwise re-run and a pinned widget would keep stale px.
// Re-run applyPosition on resize against the last-pushed data (auto re-derives the CSS default,
// a pinned position rescales proportionally + echoes to converge). rAF-coalesced so a burst of
// resize events collapses to one recompute. The Python g_guiResetters push is a backstop.
function onViewportResize() {
    if (onViewportResize._pending) return;
    onViewportResize._pending = true;
    var raf = window.requestAnimationFrame || function (f) { f(); };
    raf(function () {
        onViewportResize._pending = false;
        var root = document.getElementById("moe-root");
        if (root && root._moeLastData) applyPosition(root, root._moeLastData);
    });
}

engine.whenReady.then(function () {
    applyWidgetScale();
    window.addEventListener("resize", applyWidgetScale);
    window.addEventListener("resize", onViewportResize);
    // One 250ms tick drives both the resolution/scale self-heal AND the cold-mount rev poll
    // (pollForChanges re-renders when Python bumped moeData.rev but the data-changed event was
    // dormant -- see the cold-mount self-heal note above).
    setInterval(function () { pollWidgetScale(); pollForChanges(); }, 250);
});
