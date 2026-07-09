---
name: moe-garage
description: Use when editing the 14th_ua MoE Calculator's HANGAR percentile-bar widget — its garage mount/hook, the MoEVM/MarkTickVM data channel, the engine read, or the MoECalculator.js/.css DOM, render branches, bar axis, carousel positioning, assets, or the (disabled) hover tooltip. For the in-battle overlay see moe-battle.
---

# MoE Calculator — garage widget (feature)

The hangar percentile bar. Reusable patterns are in `wotmod-gameface-widget` (front-end)
and `wotmod-architecture` (Python layering + `references/game-api.md`); this skill is the
concrete wiring. All paths under `src/res/`.

## Data flow (game → widget)

1. **Mount** — `gui/mods/mod_moe_calculator.py::_install()` patches
   `HangarVehicleParamsPresenter._onLoading` (a hangar sub-view). Every mount it re-arms
   listeners then `bridge.attach()` + `bridge.push()` — re-arming is required because the
   post-battle hangar teardown drops our `onChanged` delegate. Idempotent (`_moe_calculator_patched`).
2. **Inject** — `bridge/gameface_bridge.py::attach()` calls `openwg_gameface.gf_mod_inject`
   with `WIDGET_NAME="MoECalculator"`, styles `MoECalculator.css`, module `MoECalculator.js`,
   and adds the `DATA_PROP="moeData"` property. Five re-armed listeners: vehicle, loadout,
   lobby-state, stats, settings.
3. **Read** — `adapter/engine_adapter.py::build_snapshot()` reads `g_currentVehicle` +
   dossier `MARK_ON_GUN_RECORD` (`.getValue()`=marks 0–3, `.getDamageRating()`=percentile
   float, nation) and `movingAvgDamage`; caches the career baseline into `baseline_cache`.
4. **Build** — `domain/builder.py::build_model()` — three ticks at `MARK_PERCENTS=(65,85,95)`,
   fill = clamped percentile, `end_damage_required` from threshold key `100`. `bar_visible()` gates.
5. **Push** — `bridge/view_models.py::MoEVM` (see slots below).

**Lifecycle guard:** `attach()` caches `_active=(host_vm, rvm)` and nothing clears it (no
view-destroy hook is wired). Session-persistent listeners — the `moe_data` ready hook and
`IItemsCache.onSyncCompleted` — can fire AFTER battle entry tears the hangar down, so `refresh()`
early-returns via `_host_alive()` (lobby state machine present) instead of pushing into the dead
VM. `_arm` uses `getattr(holder, attr, None)` so a renamed WG event degrades quietly. A full
`_active` teardown + the re-injection observer-stacking question stay open (`TASKS/garage-bridge-lifecycle.md`).

## VM slots (`bridge/view_models.py`) — HAND-NUMBERED, JS reads by name

- **`MoEVM`** — `properties=12`, `commands=0`. Indices: 0 `visible`, 1 `nation`, 2 `marks`,
  **3 `curPercent` (Real)**, 4 `curAvgDamage`, **5 `fill` (Real)**, 6 `hasData`,
  7 `carouselRows`, 8 `carouselSmall`, 9 `ticks` (Array of `MarkTickVM`),
  **10 `endDamageRequired`**, 11 `labels` (JSON string for the tooltip).
- **`MarkTickVM`** — `properties=5`: 0 `percent`, 1 `markCount`, 2 `damageRequired`, 3 `reached`, 4 `icon`.
- `curPercent`/`fill` are **`_addRealProperty`+`_setReal`** on purpose: `_setNumber` int-casts and would render `73.67`→`73.00` (the `wotmod-architecture` Wulf-decimals rule).

## Front-end (`MoECalculator.js` / `.css`)

- `ModelObserver("MoECalculator")` reads `model.moeData`. `#moe-root` built once by `ensureRoot()`:
  `.moe-head>.moe-cur(.moe-cur-dmg + .moe-cur-icon)` and `.moe-body>.moe-track` holding
  `.moe-fill .moe-split .moe-split-label(50%) .moe-end .moe-end-label .moe-cur-marker .moe-cur-pct .moe-ticks`.
- **Bar axis** (`barX`): piecewise `PCT_STOPS=[0,50,65,85,95,100]` → `BAR_STOPS=[0,20,40,60,80,100]`
  (five equal fifths — spreads the crowded 65/85/95 ticks). `SPLIT_PCT=50` drives `.moe-split-passed` at fill ≥ 50.
- **Render branches (`render`):** no `moeData` → hidden; `visible===false` → hidden;
  otherwise shown. **New tank genuinely reads `0` / `0%`** (synchronous dossier read, not the
  async table) — explicit zeros, not a "—" placeholder. Percent via `pctText` is **floored to
  2 decimals** (never rounds up past a threshold). Carousel classes `moe-rows2` / `moe-small`
  toggled from `data.carouselRows`/`carouselSmall`.
- **Ticks** use the flat glyph `img://…/library/marksOnGun/mark_%d.png` (ignores `tk.icon` — nation decals mush at tick size); damage requirement printed below each (blank when unknown).
- **Localization:** `labels` arrives as a JSON bundle; `L(key)` is missing-key-safe; JS hardcodes no English (mirrored contract with `adapter/i18n.py`).

## CSS notes (`MoECalculator.css`)

- No `var(--color-*)` (Gameface drops the whole declaration on an unresolved var); everything in **`rem`** (1rem == interfaceScale px); font `PFDINMax`; white fill `#ede6d9` (band/zone colours were removed — plain white bar).
- Anchored bottom-right: `right:46rem; bottom:calc(<rem>+140px)` — `.moe-rows2`=232rem, single-row=205.5rem, `.moe-small`=189rem; width `315rem`. (The `+140px` physical term is a resolution correction — see the `wotmod-gameface-widget` rem/px rule.)
- Track uses WG `img://` progressbar textures; **`card_border.png` is a `border-image`** and MUST be a bare-sibling `url(card_border.png)` (`img://`/`data:` silently fail for `border-image`).

## Hover tooltip — DISABLED

`const TOOLTIP_ENABLED = false` in `MoECalculator.js`: `renderTooltip()` bails early so the
host node is never built and no hover listeners bind. The (paused) layout is a 2×2 requirement
grid + opposite-corner footer, reskinned to WG's ammo/module tooltip (`tooltip_bg.png`
border-image + `tooltip_divider.png`). Never eyeballed live. To re-enable, flip the flag.
See `TASKS/tooltip-handoff.md`.

## Assets (bare siblings of the JS/CSS)

`card_border.png` (border-image), `tooltip_bg.png` / `tooltip_divider.png` (tooltip skin). Fonts for this feature: engine `PFDINMax` (no bundled TTF; the bundled `MoEBattle.ttf` is the battle overlay's).
