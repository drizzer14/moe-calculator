// 14th_ua's MoE Calculator widget. Injected into the hangar document by OpenWG. Reads our data
// model (exposed as `moe_calculatorModel` on the host sub-view's model) via
// ModelObserver, and renders a single-axis XP bar with stacked fill + ticks.
//
// See the wotmod-gameface-widget harness skill for the DOM/CSS conventions and the
// Gameface (Coherent) quirks this stub already accounts for.
import { ModelObserver } from "../../libs/model.js";

// --- Wire contract with the Python side ------------------------------------
// These string VALUES are the Python<->JS contract; they MUST equal the Python enums
// verbatim. Python centralizes them (a typo there is a NameError); hoist them here so
// each value has ONE definition and a drift can't fail silently at ~30 call sites.
const MODE = {                                          // domain/types.py Mode
    TECH_TREE: "tech_tree", COMPLETE: "complete",
    HIDDEN: "hidden",   // bar isn't pushed at all for HIDDEN, so JS never sees it
};
const CAT = {                                           // domain/constants.py Category
    VEHICLE: "vehicle", MODULE: "module",
};
const CMD = {                                           // bridge/view_models.py commands
    RESEARCH_UNLOCK: "researchUnlock", OPEN_RESEARCH: "openResearch",
};

const observer = ModelObserver("MoECalculator");

// wulf exposes nested viewmodels / array elements wrapped as { value: ... }.
function unwrap(x) {
    return x && x.value !== undefined ? x.value : x;
}

// Invoke a reverse-channel command on our ResearchVM (exposed as `moe_calculatorModel`
// on the host model). Wulf surfaces a ViewModel command as a callable on the model;
// whether it lives on the wrapped proxy or its unwrapped value can differ across
// builds, so try both. `arg` is omitted for a no-arg command (openResearch).
function invokeCommand(name, arg) {
    try {
        const vm = observer.model && observer.model.moe_calculatorModel;
        let host = null;
        if (vm && typeof vm[name] === "function") host = vm;
        else {
            const inner = unwrap(vm);
            if (inner && typeof inner[name] === "function") host = inner;
        }
        if (!host) { console.error("[moe_calculator] command missing: " + name); return; }
        // Wulf commands take a single MAP argument (a raw scalar is rejected by
        // Gameface as "not a map"). A scalar id is wrapped as {value: id}; an arg
        // that's already a map (e.g. {x, y}) is passed through as-is.
        if (arg === undefined || arg === null) host[name]();
        else if (typeof arg === "object") host[name](arg);
        else host[name]({ value: arg });
    } catch (e) {
        console.error("[moe_calculator] invokeCommand failed: " + name, e);
    }
}

// Build the root element once and cache it on the document.
function ensureRoot() {
    let root = document.getElementById("moe_calculator-root");
    if (root) return root;
    root = document.createElement("div");
    root.id = "moe_calculator-root";
    root.innerHTML =
        '<div class="wg-head">' +
        '  <span class="wg-label"></span>' +
        '  <span class="wg-xp"></span>' +
        '</div>' +
        '<div class="wg-bar"><div class="wg-fill-vehicle"></div>' +
        '<div class="wg-fill-free"></div><div class="wg-ticks"></div></div>';
    document.body.appendChild(root);
    // One delegated click handler for the whole bar: hit-test the clicked tick and
    // invoke its command. (A real widget hit-tests by cursor-% against the track;
    // this stub keys off a data-attribute stamped per tick.)
    root.querySelector(".wg-ticks").addEventListener("click", (e) => {
        const el = e.target.closest && e.target.closest(".wg-tick");
        if (!el) return;
        const id = parseInt(el.getAttribute("data-action-id") || "0", 10);
        if (id > 0) invokeCommand(CMD.RESEARCH_UNLOCK, id);
        else invokeCommand(CMD.OPEN_RESEARCH);
    });
    return root;
}

// pct of a value along the [min,max] scale, guarding a zero-width range as 100%.
function pct(v, min, max) {
    if (max <= min) return 100;
    return Math.max(0, Math.min(100, ((v - min) / (max - min)) * 100));
}

function renderTicks(ticksEl, ticks, min, max) {
    ticksEl.innerHTML = "";
    for (let i = 0; i < ticks.length; i++) {
        const tk = unwrap(ticks[i]);
        const el = document.createElement("div");
        el.className = "wg-tick" + (tk.affordable ? " wg-tick-affordable" : "") +
            (tk.category === CAT.VEHICLE ? " wg-tick-vehicle" : " wg-tick-module");
        el.style.left = pct(tk.position, min, max) + "%";
        el.setAttribute("data-action-id", String(tk.actionId || 0));
        el.title = (tk.name || "") + "  (" + (tk.xpRequired || 0) + " XP)";
        ticksEl.appendChild(el);
    }
}

function render(model) {
    const root = ensureRoot();
    const data = unwrap(model && model.moe_calculatorModel);
    const label = root.querySelector(".wg-label");

    if (!data) {
        // Model not attached yet -- show a diagnostic so a missing push is visible.
        const keys = model ? Object.keys(model).join(",") : "no-model";
        label.textContent = "MoECalculator: waiting for data | keys=" + keys;
        return;
    }

    // Python pushes visible=false while a tank-setup overlay is open, or for a
    // toggled-off (HIDDEN) mode. An absent flag (older Python) is treated as visible.
    if (data.visible === false) { root.style.display = "none"; return; }
    root.style.display = "";

    const min = data.scaleMin || 0;
    const max = data.scaleMax || 0;
    const spendable = data.spendableXp || 0;

    if (data.mode === MODE.COMPLETE) {
        label.textContent = "Fully researched";
    } else {
        label.textContent = "Research";
    }
    root.querySelector(".wg-xp").textContent = spendable + " XP";

    // Two stacked fill segments: vehicle XP first, then free XP on top.
    const fv = pct((data.fillVehicle || 0), 0, max || 1);
    const ff = pct((data.fillVehicle || 0) + (data.fillFree || 0), 0, max || 1);
    root.querySelector(".wg-fill-vehicle").style.width = fv + "%";
    root.querySelector(".wg-fill-free").style.width = ff + "%";

    renderTicks(root.querySelector(".wg-ticks"), (data.ticks || []), min, max);
}

engine.whenReady.then(() => {
    observer.onUpdate(render);
    observer.subscribe();
    render(observer.model);
});
