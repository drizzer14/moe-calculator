# In-battle MoE — session handoff (live-verify findings)

_Written 2026-07-06 after a live replay + REPL verification session. Read this first; it
supersedes the "NEXT" notes in `TASKS/in-battle-moe-panel.md`. All work is **UNCOMMITTED**._

## TL;DR

The full in-battle stack is **built, deployed, and mounting live** — but the overlay **does
not render**, for a now-understood architectural reason, and the **replay baseline is empty**
because the items cache isn't synced in replays. Two root causes below, both diagnosed against
the live client + the on-disk decompile + OpenWG's source. The **pure calculation domain is
done and unit-tested (34/34)** and is unaffected by either issue.

## What is deployed right now

- Real mod `com.14th_ua.moe_calculator_0.1.0.wotmod` deployed to `D:/Games/World_of_Tanks_EU/
  mods/2.3.0.1/` (contains the full battle path — verified in the zip).
- Debug REPL `com.14th_ua.moe_calculator_debug.wotmod` deployed (TCP 127.0.0.1:2224). The REPL
  that answered this session was actually the sibling `wgmod-research-progress` debug mod — same
  port, fine for game introspection.
- Gameface overlay re-synced into `res_mods/2.3.0.1/...` (hot-reload available for CSS).

## VERIFIED WORKING (live, 2.3.0.1 replay)

Data path is fully correct — confirmed via `tools/dev/probe6.py`:
- `_install_battle` patched `gui.impl.pub.main_view.MainView._onLoading`; `battle_bridge._active`
  is set; the host VM carries our `ModInjectModel` + `moeBattleData`.
- Live reads: `getTotalEfficiency(DAMAGE/ASSIST/STUN)` → real values (e.g. `415/0/0`); intCD via
  `vehicleState.getControllingVehicleID()` → `arena.vehicles[vid]['vehicleType'].type.compactDescr`
  = `8545` (`japan:J40_Type_71`); `arena.period == ARENA_PERIOD.BATTLE == 3`.
- Thresholds fetch works in battle; `moeBattleData` is pushed with correct `combinedDamage`.

## BUG A — overlay never renders (THE blocker)

**Root cause (certain).** `openwg_gameface.gf_mod_inject(model, ...)` does exactly one thing
(disassembled live): `model._addViewModelProperty('ModInjectModel', ModInjectModel(...))`. OpenWG's
`index.js` (in `net.openwg/net.openwg.gameface_1.1.6.wotmod`, `res/gui/gameface/js/index.js`) only
ever injects for entries in **`window.subViews`** — it reads `window.subViews.get(resId).model
.ModInjectModel` on `subViews.onAdded` + existing `subViews.ids()`. **The battle root `MainView`
is NOT a subView**, so index.js never scans it → our JS/CSS never load → nothing renders. (Our
data is all correctly on the VM; it just never reaches a DOM.) The garage works only because
`HangarVehicleParamsPresenter` IS a genuine subView of the hangar document.

**No lightweight precedent among installed mods.** Checked all three battle-injector windows
(seen live at layer 7, all `inject=False` — none use gf_mod_inject):
- `me.poliroid.battlehits` — actually a **garage/hangar** post-battle hit viewer (`HangarScene`,
  `BattleHitsMainView`), NOT in-battle. Not applicable.
- `me.kurzdor.battleequipment` — renders via **Flash** (`res/gui/flash/battleEquipment.swf`).
- `me.poliroid.pmod` `gui.pmod.views.battleInjector` — single `.pyc`, no bundled Gameface JS
  (own framework / Flash). Not a copyable Gameface pattern.

**Fix options (pick in next session):**
1. **Inject onto a persistent battle Gameface _subView_** (lightest — reuses our current code,
   just change the host from `MainView` to a subView). Battle Gameface subViews DO exist
   (`findViews` returned `MainView`, `TabView`, `DeathCamHudView`, `PostmortemPanelView`; the last
   three are subViews, not top-level windows). **OPEN QUESTION to resolve first:** is any battle
   subView (a) persistently *loaded* from battle start (not just shown-on-demand) and (b) sharing
   the `MainView` Gameface document's DOM (so our `position:fixed` `#moe-battle-root` appended to
   `document.body` shows even when that subView is hidden)? If yes → 2-line host swap. Experiment:
   gf_mod_inject onto e.g. `TabView`'s VM live via REPL and see if the overlay appears.
2. **Build a native Gameface view/window** (heaviest, no installed precedent): our own `ViewImpl`
   + a registered layout resource with our JS bundled, loaded as a layer-7 window — because a
   top-level window's root view is NOT a subView either, so gf_mod_inject can't help there; the JS
   must be bundled in the view's native layout. This is real new work (layout XML + gen viewmodel).

**Recommendation:** run experiment (1) first — if a persistent shared-DOM subView exists, it's a
tiny change. Only fall back to (2) if not.

### UPDATE (offline source dig — OPEN QUESTION resolved, fix designed)

Read OpenWG's actual `index.js` (extracted from `net.openwg.gameface_1.1.6.wotmod`) + the
decompile. Confirmed:
- **index.js is strictly subView-scoped** and assets are appended to `document.body` and
  tracked in `injectedResIds` → **once injected they persist for the document's life** even
  if the subView later hides/unloads. So the host subView need only appear ONCE, early.
- **Battle Gameface subViews ARE children of the battle MainView's document.**
  `gui/Scaleform/framework/entities/inject_component_adaptor.py::_createInjectView` does
  `mainView = windowsManager.getMainWindow().content; mainView.addChild(placeId, view, True)`
  — i.e. DeathCam / Postmortem / BattleNotifier / Tab are all added as children (subViews) of
  the battle `MainView`. **This resolves the OPEN QUESTION: a subView of MainView injects into
  the HUD document → a `position:fixed` overlay shows over the whole battle.**
- **Don't piggyback a WG component** — they're gated: `BattleNotifier` needs a server flag AND
  the user's `ENABLE_BATTLE_NOTIFIER` setting; DeathCam/Postmortem are death-lifecycle. None is
  a guaranteed always-present subView.

**CHOSEN FIX (robust, no new resource, no restart): create our OWN subView.**
In `_install_battle`, after MainView loads, create `ViewComponent()` (layoutID defaults to
`R.aliases.common.none()` — the SAME inert layout our working garage sub-view uses), add it as
a child of the battle MainView, and `gf_mod_inject` onto ITS ViewModel (not MainView's). This is
the exact analogue of the InjectComponentAdaptor pattern, fully under our control, independent of
WG settings. `frameworks/wulf/view/view.py::addChild` registers it as a subView (`getSubView`).

**Experiment to confirm BEFORE writing code:** `tools/dev/probe_battle_subview.py` (execfile in a
battle) creates that child, injects, and pushes a SYNTHETIC visible model. If the overlay renders
→ wire it into `_install_battle` (change host from `self.getViewModel()` to the child's VM). Needs
a LIVE/replay battle running with the REPL up.

## BUG B — empty dossier baseline in replays

**Root cause (certain).** `probe10`: `IItemsCache.isSynced() == False`, `items.getVehicles()`
returns **0** in the replay. `getItemByCD(8545)` = `japan:J40_Type_71` but `isInInventory=False`.
So the account's inventory/dossiers are **not loaded in a replay** → `getVehicleDossier(8545)`
returns an empty dossier (`playerDBID=None`) → `pre_avg=0, pre_percentile=0`. The intCD is CORRECT
(no key mismatch). User confirmed it's a replay of their own tank at 1.49% MoE, so the read *should*
have data — the cache just isn't synced.

**Implication:** **metrics 2–4 (projection / percent / delta) cannot be validated in a replay** —
there's no baseline. Only metric 1 (live combined damage) is meaningful in replays.
**Fix/validation path:** test metrics 2–4 in a **LIVE battle** (cache synced from the garage), OR
investigate whether entering the garage before opening a replay syncs the cache. Consider a widget
gate: when the cache is unsynced / baseline is 0, show only combined damage (hide the % rows) —
mirrors the lebwa "play more battles" gate idea.

## Debugging setup (reusable)

- **Decompiled client:** `~/wot-eu/source/res/scripts/client/` (StranikS-Scan branch `2.3`).
  Recorded in the `wotmod-debug-repl` harness skill.
- **REPL:** `py -3 tools/dev/repl_client.py --file <cmds.txt>` or `... "execfile(r'<abs .py>')"`
  (one command per line; multi-line blocks MUST use `execfile`; server catches per-line errors).
- **Reusable probes kept:** `tools/dev/probe_battle.txt` (data-read smoke test),
  `tools/dev/probe6.py` (mount + pushed-model verifier). One-shot discovery probes were deleted.
- **Build/deploy (client CLOSED):** `C:\Python27\python.exe build/deploy_wotmod.py "D:/Games/
  World_of_Tanks_EU" 2.3.0.1` then `py -3 tools/dev/sync_gameface.py "D:/..." 2.3.0.1`.
- **Tests:** `py -3 -m pytest tests/ -q` (34 pass).

## Key files

- Entry/mount: `src/res/scripts/client/gui/mods/mod_moe_calculator.py` (`_install_battle` patches
  `MainView._onLoading`, gated on `_in_arena()`). **This is what changes for BUG A fix.**
- Bridge: `.../moe_calculator/bridge/battle_bridge.py` (attach/push/re-arm; all PlayerEvents +
  efficiency symbols verified).
- Adapter: `.../adapter/battle_adapter.py` (reads verified; reuses `engine_adapter._read_moe` for
  the baseline — the empty-in-replay read is a cache-sync issue, not an adapter bug).
- Domain (done, tested): `.../domain/battle_builder.py`, `battle_types.py`; `tests/test_battle_builder.py`.
- Widget: `src/res/gui/gameface/mods/14th_ua/MoECalculator/MoEBattle.{js,css}` (renders once the
  mount is fixed; CSS offsets `left:1.6vw; bottom:22vh` are unvalidated guesses to calibrate).

## Immediate next steps for a clean session
1. BUG A experiment: probe battle subViews; try gf_mod_inject onto a persistent one; confirm render.
2. If none work, scope the native-view approach (option 2).
3. Validate metrics 2–4 in a LIVE battle (not a replay) to get a real baseline.
4. Calibrate `MoEBattle.css` position live; then validate EWMA `k`.
5. Nothing is committed — decide on committing once the overlay renders.
