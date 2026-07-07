# Research: In-battle MoE — replace the mount layer (registered Gameface window)

_Submitted: "Continue in-battle moe calculator" → root-caused the non-rendering overlay; hand the
mount-layer rework to a clean session · Status: **IMPLEMENTED (2026-07-06 session 3), built +
deployed, AWAITING LIVE VERIFY** · still UNCOMMITTED_

## IMPLEMENTED — what shipped this session (all UNCOMMITTED)

The registered-window rework below is now built end-to-end and deployed to
`D:/Games/World_of_Tanks_EU/mods/2.3.0.1/`. Domain/adapter untouched (43 tests pass, py2.7
compiles). All open questions were resolved from source (decompile + extracted
battlehits/openwg bundles), NOT yet live:

- **res_map** `src/res/mods/configs/res_map/MoEBattleView.json` (itemID `MoEBattleView`,
  type Layout, impl gameface). Ships INSIDE the .wotmod — confirmed OpenWG reads packaged
  `mods/configs/res_map/*.json` (battlehits ships its there too). ⇒ **Open Q3 answered: no
  res_mods copy needed.**
- **layoutID lookup (Open Q1 answered):** `openwg_gameface.ModDynAccessor("MoEBattleView")`
  — a deferred `DynAccessor`; CALL it (`accessor()`) to get the layoutID. `INVALID_RES_ID
  == -1` until the res_map validates at client start (resolved well before battle). Same
  accessor battlehits' header view uses.
- **View + Window (Open Q2 answered):** the golden precedent is WG's OWN in-battle Gameface
  window `gui.impl.battle.prebattle.prebattle_hints_view.PrebattleHintsWindow`:
  `WindowImpl(WindowFlags.WINDOW | WindowFlags.WINDOW_FULLSCREEN, content=<ViewImpl>,
  layer=WindowLayer.OVERLAY)`. A `WindowImpl` self-composits its own surface (does NOT need
  a Flash placeId — that's exactly what the failed probe lacked). Crucially, PrebattleHints
  EXPLICITLY does `enterGuiControlMode` + `registerGuiKeyHandler` to CAPTURE input ⇒ a plain
  overlay window that skips those (and `show(focus=False)`) should NOT steal battle input.
  New `src/.../moe_calculator/bridge/battle_view.py` = `MoEBattleView(ViewImpl)` (ViewSettings
  layoutID+ViewFlags.VIEW+BattleMoEVM) + `MoEBattleWindow(WindowImpl)` + open/close singleton.
- **Lifecycle:** MainView patch DROPPED. `battle_bridge` now opens the window on
  `g_playerEvents.onAvatarReady` and destroys it on `onAvatarBecomeNonPlayer` (globals persist
  across battles); `_install_battle` just arms the listeners once. `push()` targets the
  window view's own root VM; `attach()`/gf_mod_inject removed.
- **Widget:** `MoEBattleView.html` (loads MoEBattle.css + MoEBattle.js); `MoEBattle.js`
  now `ModelObserver()` (root, no name) reading `model.combinedDamage` etc directly; CSS got
  html/body transparent+full-size+pointer-events:none. All added to `sync_gameface.py`.

**NEXT (live, needs the user in a battle):** launch the client — OpenWG detects the new
res_map entry and AUTO-RESTARTS once (RESTART_FLAG_FILE guards against a loop). Enter a
battle; the overlay should open automatically. To isolate rendering, execfile
`tools/dev/probe_battle_window.py` via the REPL (force-opens + pushes a synthetic visible
model). Verify: (a) it renders over the HUD, (b) it does NOT steal cursor/input, (c) then
calibrate `MoEBattle.css` `left/bottom`, (d) validate EWMA `k` + metrics 2-4 in a LIVE
battle (replays have no baseline — BUG B). Then commit.

---

## Original research (below) — superseded by the IMPLEMENTED section above


**Read order:** this note supersedes the BUG A section of `TASKS/in-battle-moe-handoff.md` and the
"NEXT" notes in `TASKS/in-battle-moe-panel.md`. The domain/adapter/data layer and the widget's
render logic are DONE and reused as-is; only the **mount + how the widget is hosted** changes. All
work is still **UNCOMMITTED**.

## Summary

The in-battle overlay never renders. Root cause is now **confirmed live + from source**: the
garage-style OpenWG sub-view injection *cannot* work in battle, because **the battle HUD has no
full-screen Gameface document to inject a `position:fixed` overlay into**. The fix is to stop
injecting onto a sub-view and instead **register our own Gameface view via OpenWG `res_map` and open
it as a standalone top-layer window** — the mechanism `me.poliroid.battlehits` and
`me.poliroid.modslistapi` already use (installed, on disk, copyable).

## Root cause (confirmed — do not re-litigate)

OpenWG's injector (`net.openwg.gameface_1.1.6.wotmod` → `res/gui/gameface/js/index.js`, read this
session) is **strictly sub-view-scoped**: on `subViews.onAdded` / existing `subViews.ids()` it reads
`window.subViews.get(resId).model.ModInjectModel` and appends the listed `<script>`/`<link>` to
`document.body` of **the document index.js is running in** (assets persist once added).

- **Garage works** because a full-screen Gameface document (`mono/hangar/main`, seen in
  `python.log` as `Load view mono/hangar/main`) fills the hangar MainView; our garage sub-view
  (`HangarVehicleParamsPresenter`, `layoutID=R.aliases.common.none()`) injects into *that* visible
  DOM.
- **Battle has no equivalent.** `python.log` at battle start shows only
  `Load view battle/battle_page/TabView`, `battle/death_cam/DeathCamHudView`,
  `battle/postmortem_panel/PostmortemPanelView` — and **no** `battle/...main`. Those battle Gameface
  views are each composited by **Flash at a placeId** (`InjectComponentMeta.as_setPlaceIdS` →
  `flashObject.as_setPlaceId`, see `gui/Scaleform/daapi/view/meta/InjectComponentMeta.py:7`), i.e.
  separate surfaces, not one shared HUD DOM. The battle `MainView` (uid=2, layoutID=1) document our
  code attached to is **not a visible full-screen surface**.

**Live proof (this session, replay, REPL):** injecting our own `ViewComponent` child (none layout)
onto the battle `MainView` — both real widget and a loud red-full-screen-box probe — rendered
**nothing**, with no `coui://` load errors and no JS console output in `python.log`. Two independent
visual tests → the surface simply isn't there. (Probes kept: `tools/dev/probe_battle_subview.py`,
`tools/dev/probe_inject_test.py`; loud JS at
`res_mods/.../14th_ua/MoECalculator/probe_inject.js` on the game install — delete when done.)

Why the sub-view-child idea seemed right first: `gui/Scaleform/framework/entities/inject_component_adaptor.py:93-96`
does `mainView = windowsManager.getMainWindow().content; mainView.addChild(placeId, view, True)` — so
battle Gameface views ARE children of MainView in the Wulf tree. But being a Wulf child ≠ living in a
visible DOM; Flash composits each child's own surface. That's the trap.

## Suggested approach — registered Gameface window via `res_map`

Copy the `battlehits` pattern (all paths below are from its extracted `.wotmod`):

**1. res_map registration.** Add `src/res/mods/configs/res_map/MoEBattleView.json`:
```json
[
  {
    "type": "Layout",
    "path": "coui://gui/gameface/mods/14th_ua/MoECalculator/MoEBattleView.html",
    "parameters": { "extension": "", "entrance": "MoEBattleView", "impl": "gameface" },
    "itemID": "MoEBattleView"
  }
]
```
OpenWG's `ResMapManager` (in `openwg_gameface.pyc`) reads `mods/configs/res_map/*.json` at client
startup, rebuilds `res_map.json`, and **restarts the client once** if it changed. So this needs a
one-time restart to take effect (and the config must be inside the packaged `.wotmod`, or under
`res_mods/.../mods/configs/res_map/` for dev iteration).

**2. View bundle.** Convert the standalone overlay into a real registered view (see
`battlehits` `BattleHitsHeaderView.{html,css,js}`):
- New `MoEBattleView.html` — `<!doctype html>` page whose `<body>` holds the overlay root and which
  loads our JS/CSS itself: `<link rel="stylesheet" href="MoEBattle.css">` +
  `<script type="module" src="MoEBattle.js">`. (No gf_mod_inject — a registered view loads its own
  assets.)
- Rework `MoEBattle.js`: it currently reads a *named injected sub-model* via
  `ModelObserver("MoEBattle")` and `model.moeBattleData` (`MoEBattle.js:13,75`). In a registered
  view the view's **own root ViewModel** is our model — use `ModelObserver()` (no name, as
  `BattleHitsHeaderView.js` does) and read fields directly off the root (either make the view's model
  BE `BattleMoEVM`, or keep `moeBattleData` as a root property — pick one and keep JS+Python in sync).
  All the render/formatting logic (thousands, pctText, signedPct, visibility gate) is unchanged.
- Keep `MoEBattle.css` (position the overlay inside the now-full-screen transparent window; the
  `left/bottom` guesses still need live calibration).

**3. Python: a view class + open/close as a window.**
- New `MoEBattleView(ViewImpl)` (mirror `gui/impl/battle/battle_notifier/battle_notifier_view.py`):
  `ViewSettings(layoutID=<resId for "MoEBattleView">, flags=ViewFlags.VIEW or a window content flag,
  model=BattleMoEVM())`. Resolve the layoutID from the registered itemID — battlehits builds it via
  `R.views...`/the res system; simplest is to look it up through OpenWG's resId-by-key helpers
  (`res_id_by_key`/`res_ids_by_mask` exist in `openwg_gameface.pyc`) or the generated `R`. **Confirm
  the exact call live** (see Open questions).
- Open it as a **top-layer window** via `windowsManager.loadView(layoutID, MoEBattleView, ...)` or a
  `Window(WindowFlags..., content=MoEBattleView())`. battlehits uses `windowsManager.loadView` +
  `WindowLayer` + `closeWindow` (confirmed from its pyc strings). API:
  `frameworks/wulf/windows_system/windows_manager.py:73 def loadView(self, layoutID, viewClass, *args, **kwargs)`.
- **Lifecycle** — replace the `MainView._onLoading` patch in
  `src/res/scripts/client/gui/mods/mod_moe_calculator.py:65 (_install_battle)`: open the window on
  battle start and close it on battle end. Cleanest is event-driven off the GLOBAL `g_playerEvents`
  (persists across battles — unlike the per-battle controllers): open on `onAvatarReady` /
  `onArenaPeriodChange`, close on `onAvatarBecomeNonPlayer`. The battle bridge already arms these
  (`battle_bridge.py:100 _LISTENERS`); redirect its mount from "attach onto MainView sub-view" to
  "open our window + push into its VM". `battle_bridge.attach()` (`battle_bridge.py:168`) and its
  `gf_mod_inject` call go away; `push()` (`battle_bridge.py:195`) stays, targeting the window's VM.

## Touch points

- `src/res/scripts/client/gui/mods/mod_moe_calculator.py` — `_install_battle` (:65): drop the
  MainView patch; arm global events once, open/close the window.
- `src/res/scripts/client/moe_calculator/bridge/battle_bridge.py` — `attach` (:168) removed;
  `push` (:195) retargets the window's VM; listeners (:100) reused.
- `src/res/scripts/client/moe_calculator/bridge/view_models.py` — `BattleMoEVM` (:105) reused (maybe
  as the view's root model).
- NEW `.../moe_calculator/bridge/battle_view.py` (or similar) — `MoEBattleView(ViewImpl)` + window
  open/close helpers.
- NEW `src/res/mods/configs/res_map/MoEBattleView.json` — the registration.
- NEW `src/res/gui/gameface/mods/14th_ua/MoECalculator/MoEBattleView.html`; edit `MoEBattle.js`
  (root ModelObserver) + `MoEBattle.css` (positioning). Add all three + the JSON to
  `tools/dev/sync_gameface.py` ASSETS and to the build packaging.
- Reference bundle (read-only): extracted battlehits at
  `<scratch>/bh/res/...` this session, or re-extract `me.poliroid.battlehits_2.3.7.wotmod`.

## Verification

- Unit tests unaffected: `py -3 -m pytest tests/ -q` (34 pass) — domain/adapter untouched.
- Build (client CLOSED, Py2.7): `C:\Python27\python.exe build/deploy_wotmod.py "D:/Games/World_of_Tanks_EU" 2.3.0.1`
  then `py -3 tools/dev/sync_gameface.py "D:/Games/World_of_Tanks_EU" 2.3.0.1`. **Restart the client
  once** so OpenWG rebuilds res_map with our layout.
- Live (replay ok for RENDER; metrics 2-4 need a LIVE battle — replays have an unsynced items cache,
  see BUG B in `in-battle-moe-handoff.md`): enter battle, confirm the overlay renders over the HUD.
  Push a synthetic visible model via the REPL to isolate rendering (reuse the transaction block in
  `tools/dev/probe_battle_subview.py`).
- REPL: `py -3 tools/dev/repl_client.py "execfile(r'<abs .py>')"` (TCP 127.0.0.1:2224). Decompile at
  `~/wot-eu/source/res/scripts/client` (branch 2.3).

## Open questions (resolve live/early)

1. **Exact layoutID lookup** for a res_map-registered `itemID` from Python 2.7 — via generated `R`,
   or OpenWG's `res_id_by_key`. Confirm against battlehits' pyc / live REPL before wiring.
2. **Which `WindowLayer`** composites a Gameface window OVER the Scaleform battle HUD (battlehits is
   garage, so its layer is not directly transferable). Probe `WindowLayer` values live; the other
   battle mods sit at layer 7 (`SFWindow`s) — a Gameface window at a comparable top layer is the
   target. Verify our window doesn't steal input (pointer-events:none in CSS + a non-modal window
   flag).
3. **Does res_map require the config inside the packaged `.wotmod`**, or is `res_mods/.../mods/configs/
   res_map/` honored for dev? (Affects iteration speed — test both.)
4. Confirm no clash between our window and the existing garage sub-view path (they're mutually
   exclusive by context, but the shared `battle_bridge._active`/`moe_data` singletons should be
   re-checked).
