---
name: moe-battle
description: Use when editing the 14th_ua MoE Calculator's IN-BATTLE live-MoE overlay — how it is hosted as a registered Gameface window over the HUD, its arena lifecycle, the BattleMoEVM channel, the combined-damage/EWMA math, the MoEBattle.js/.css/.html DOM, its colours/font/checker backdrop, or the window placement/anchors. For the hangar bar see moe-garage.
---

# MoE Calculator — in-battle overlay (feature)

A live combined-damage / projected-MoE readout floated over the battle HUD. Reusable
patterns: `wotmod-gameface-widget` (front-end), `wotmod-architecture` (Python +
`references/game-api.md` "Battle HUD / efficiency"), `wotmod-debug-repl` (live probing).
All paths under `src/res/`.

## Hosting model (the hard-won part)

You **cannot** `gf_mod_inject` a garage-style sub-view overlay into the battle HUD: there is
no shared full-screen Gameface document — each WG battle Gameface view is Flash-composited at
its own placeId. Instead the mod **registers its own view** and opens it as a window:

- **Register** — `src/res/mods/configs/res_map/MoEBattleView.json` (`itemID "MoEBattleView"`,
  `impl "gameface"`, points at `MoEBattleView.html`). Ships **inside** the `.wotmod`. Adding it
  triggers a **one-time client restart** the first time OpenWG's ResMapManager rebuilds `res_map.json`.
- **Resolve layoutID** — `bridge/battle_view.py` via `openwg_gameface.ModDynAccessor("MoEBattleView")()`
  (deferred; `-1` until validated at client start, resolved before any battle). **Do not hard-code the numeric id.**
- **Window** — `MoEBattleView(ViewImpl)` (its root VM is `BattleMoEVM`) inside
  `MoEBattleWindow(WindowImpl)` at **`WindowLayer.WINDOW` (7)**, `show(focus=False)`.
  - `WindowLayer.OVERLAY` (11) sits **above** the modal in-battle menu (`INGAME_MENU`, TOP_WINDOW 10) and made our window the keyboard sink → menu starved. WINDOW (7) sits below the menu but above the battle MainView. **This is the WINDOW-vs-OVERLAY input-steal rule.**
  - **Content-sized, NOT `WINDOW_FULLSCREEN`.** `pointer-events:none` only stops our own DOM being an event target — it does **not** make the window rectangle click-through to the engine's cross-surface hit-test. A full-screen surface stole the mouse whenever the cursor was raised (Ctrl). Dropping fullscreen shrinks the surface to the small readout box so the minimap/markers stay live.

## Lifecycle

`mod_moe_calculator.py::_install_battle()` arms `bridge/battle_bridge.py::install_all_listeners()`
off the **global** `g_playerEvents` arena hooks (they persist across battles):
`onAvatarReady` opens the window + arms the efficiency listener, `onAvatarBecomeNonPlayer`
destroys it. `battle_view.open_window()`/`close_window()` keep a `_active` singleton; the view's
`_onLoading` calls `battle_bridge.refresh()` for an immediate first paint.

## Data flow

- **Read** — `adapter/battle_adapter.py::build_battle_snapshot()` from
  `IBattleSessionProvider.personalEfficiencyCtrl.getTotalEfficiency(PERSONAL_EFFICIENCY_TYPE
  .DAMAGE=1 / .ASSIST_DAMAGE=2 / .STUN=32)` (+ `onTotalEfficiencyUpdated`); intCD via
  `getControllingVehicleID()` → `arena.vehicles[vid]['vehicleType'].type.compactDescr`; gated on
  `ARENA_PERIOD.BATTLE` (3); spectate detected via `getPlayerVehicleID() != getControllingVehicleID()`
  (not `isObserver()`); `read_damage_log_summary_flags()` for the raised anchor.
- **Baseline** — the dossier is unreadable in battle, so the career baseline comes from
  `domain/baseline_cache.py` (snapshotted in the garage, keyed by intCD; garage intCD == battle intCD).
- **Math** — `domain/battle_builder.py`: `combined = damage + max(assist, stun) − teamDmg`
  (**MAX not sum**, per WG); EWMA projection `avg + k·(C−avg)`, `k=2/(N+1)`, N≈100 (`EWMA_K` in
  `constants.py`; community-derived, not WG-confirmed); `damage_to_percent` piecewise over stops
  `(0,0),(D1,65),(D2,85),(D3,95),(D100,100)`. The `~`/`approx` plumbing was fully removed per user.
- **Push** — `bridge/battle_bridge.py` → `BattleMoEVM`.

## VM slots (`bridge/view_models.py::BattleMoEVM`)

`properties=7`, all **7 registered (indices 0–6)** — no free slot (a future `compact`/single-row
flag would be index 7 + `properties=8`; RTL index 8 + `properties=9`).
0 `visible`, 1 `combinedDamage`, 2 `projAvgDamage`, **3 `curPercent` (Real)**, **4 `pctDelta`
(Real)**, 5 `hasData`, **6 `hasBaseline`** (career baseline present; false on the replay/relogin
BUG-B path → JS dashes proj/%/delta). `curPercent`/`pctDelta` are `_setReal` (the Wulf int-cast
rule — see `wotmod-architecture`).

## Front-end (`MoEBattle.js` / `.css` / `.html`)

- `MoEBattleView.html` is an empty body loading `MoEBattle.css` + `MoEBattle.js`. The JS uses
  **`ModelObserver()` with NO feature name** — the observed root model **IS** `BattleMoEVM`;
  fields are read directly (`model.combinedDamage`, …), no nested submodel, no unwrap for scalars.
- `#moe-battle-root` = two `.mb-row`s: row 1 `[dmg icon] <combinedDamage> / <projAvgDamage>`,
  row 2 `[mark icon] <curPercent%> (<signed pctDelta>)`. Icons
  `icon_battle_condition_barrel_mark.png` (row 1) / `icon_battle_condition_improve.png` (row 2),
  from `…/personal_missions_30/quest_type/128x128/`.
- **Render branch:** hidden unless `visible` **and `hasData`** (truthy guard, not `=== false` —
  a VM whose flags are still undefined before the first push must hide, not paint a `0/0` stub).
  When shown but **`hasBaseline` is false** (replay / relogin — no career baseline; BUG B), the
  projected avg, percent and delta are **dashed to `-`**, keeping only the live combined damage
  (a plain hyphen, NOT an em-dash — see Font). `signedPct`/`pctText` truncate via a `trunc2`
  helper so a sub-precision value reads `0`/`0%` in white, never a coloured `+0.00%`.
- **Colour by sign (`colourBySign`)** — sign carried by a **coloured text-shadow glow, not a fill**
  (numerals stay white): `.mb-up` green, `.mb-down` red, neutral = white + dark drop only. Row 1
  live damage vs projected avg; row 2 delta vs pre-battle standing. Only the delta **number**
  (`.mb-delta-num`) is coloured — the parens stay white.
- **Colours (live `MoEBattle.css`, canonical):** green **`#7BEC37`** `rgba(123,236,55,.9)`, red
  **`#D3443F`** `rgba(211,68,63,.9)`, gold bloom `#FFCD5A`, white `#ffffff`. (A stale note says
  `#61bf22`/`#c81400` — ignore it; the CSS above is what ships.)
- **Font:** `@font-face "MoEBattle"` weight 600 from **bare-sibling `url(MoEBattle.ttf)`**
  (+ a `coui://` absolute fallback). A `fonts/…` subdir path silently falls back to Arial Narrow.
  The family is renamed to avoid colliding with the engine's Flash-registered `MoEBattle`.
  **`MoEBattle.ttf` is a 19-glyph SUBSET** — `0-9 % ( ) + - , . /` + space, NO em-dash/letters;
  an unsupported char renders blank in Gameface (this is why the no-baseline placeholder is `-`,
  not `—`). A new overlay glyph needs a wider re-extract via `tools/dev/swf_font_to_ttf.py` (it
  pulls whatever the SWF `DefineFont3` embeds); check coverage with `fontTools …getBestCmap()`.
- **Backdrop (two layers):** `.mb-row::before` tiles `checker.png` (WG halftone dither, 4px tile /
  2px cells, `background-size:auto`, `image-rendering:pixelated`, `opacity:0.2`, radial **`mask`**
  — unprefixed); `.mb-row::after` = dark radial gradient + left-clip `mask:linear-gradient(...)`.
- Fixed box `340rem × 130rem`, `pointer-events:none`; `.mb-ico` uses `background-size:260%` +
  `brightness(3) drop-shadow(...)` (the glyph fills ~¼ its PNG). Numbers use layered `text-shadow`, no stroke.

## Placement (`bridge/battle_view.py` + `domain/positioning.py`)

- Anchor constants (`domain/constants.py`, fixed **logical-GUI-space px**, scale-invariant):
  default `BATTLE_ANCHOR_X=264` (from left), `BATTLE_ANCHOR_Y=0` (bottom-flush); RAISED
  `X_RAISED=215` / `Y_RAISED=33` used when **all four** DAMAGE_LOG summary flags are unticked (WG
  collapses the summary block → events shift up). `damage_log_summary_hidden()` decides; a failed read defaults to the un-raised anchor.
- The surface is a fixed **~256×256** (windowSize is read-only). Wulf's BOTTOM `PositionAnchor`
  clamps to TOP for a tall surface, so `_place()` always moves with a **TOP-LEFT anchor** and an
  absolute y (self-calibrated by clamping to `_FAR` to read the movable extent).
- **Move the WINDOW from Python (`window.move`), never the DOM.** `apply_position()` re-places on interface-scale change.
- No hot-reload for this window — every JS/CSS tweak needs a full client relaunch (see `moe-build-release`).
