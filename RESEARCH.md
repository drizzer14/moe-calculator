# RESEARCH.md

WoT-modding background for **14th_ua's MoE Calculator**.

For the general modding stack — how a `.wotmod` loads, the OpenWG GameFace injection
model, Wulf ViewModels, the two-Python split, the community references
(`modding.wot-tools.dev`, `wgmods.dev`) and the WoT Fair Play rules — see the
**`wotmod-basics`** harness skill. Do not duplicate that material here; this file is
only for what is specific to THIS mod.

## Resolved scope (this mod)

- **What it does** — shows the selected vehicle's **Marks of Excellence (MoE)** progress
  in the garage: a horizontal bar in the bottom-right (above the carousel) with three
  milestone ticks at **65% / 85% / 95%** (= 1 / 2 / 3 marks) drawn with the vehicle's
  **nation MoE art**, the **combined-damage requirement** below each mark, and a top-left
  readout of **current average combined damage + current mark percentage**. Battle view is
  a later phase (out of scope for v1).

- **Where it mounts** — injects onto the hangar sub-view
  `gui.impl.lobby.hangar.presenters.hangar_vehicle_params_presenter.HangarVehicleParamsPresenter`
  (same hook the sibling *Garage Progress Bar* uses): OpenWG's JS injector scans hangar
  sub-views for a `ModInjectModel`, so we patch `_onLoading`, `gf_mod_inject` our JS/CSS,
  hang a `MoEVM` ViewModel on the sub-view, and push the model. Re-arm every mount.

- **Data it reads (verified against the EU 2.3 decompiled client):**
  - Vehicle dossier TOTAL block via `itemsCache.items.getVehicleDossier(intCD).getTotalStats()`:
    - `getAchievement(MARK_ON_GUN_RECORD)` → `MarkOnGunAchievement`:
      `.getValue()` = current marks 0–3, `.getDamageRating()` = current percentile as a
      float (e.g. `84.7`), `.getVehicleNationID()` = nation for the art.
    - `getRecordValue(ACHIEVEMENT_BLOCK.TOTAL, 'movingAvgDamage')` = current moving-average
      combined damage (raw). `MARK_ON_GUN_RECORD` from `dossiers2.ui.achievements`.
    - Source: `gui/shared/gui_items/dossier/achievements/mark_on_gun.py`; read pattern
      confirmed in `gui/impl/lobby/tooltips/carousel_vehicle_tooltip.py`.
  - Nation MoE art: `gui/maps/icons/marksOnGun/<size>/<nation>_<count>_<mark|marks>.png`
    (`<size>` ∈ 180x180/95x85/67x71/32x32; `<nation>` from `nations.NAMES`; `<count>` 1/2/3;
    suffix `mark` for 1, `marks` for 2–3). From the widget: `img://gui/maps/icons/marksOnGun/95x85/<nation>_3_marks.png`.
    Generic fallback (nation-agnostic): `gui/maps/icons/library/marksOnGun/mark_{1,2,3}.png`.
  - Carousel geometry (for responsive bottom offset), re-read on
    `ISettingsCore.onSettingsChanged`: `settings_constants.GAME.CAROUSEL_TYPE` →
    `CarouselTypeSetting.getRowCount()` (1 single / 2 double); `GAME.DOUBLE_CAROUSEL_TYPE` →
    `DoubleCarouselTypeSetting.enableSmallCarousel()` (small vs tall adaptive). Source:
    `gui/Scaleform/daapi/view/lobby/hangar/carousels/basic/tank_carousel.py` +
    `account_helpers/settings_core/options.py`.

- **MoE damage thresholds — the data source (official WG API):**
  The 65/85/95% combined-damage thresholds are computed server-side and not in the client
  dossier (which exposes only the player's OWN `damageRating` = achieved percentile and
  `movingAvgDamage` = EWMA combined damage). They ARE, however, published by the official
  Wargaming public API's `wot/tanks/mastery` method — the real *population* distribution:

    `GET https://api.worldoftanks.eu/wot/tanks/mastery/?application_id=<id>`
    `&distribution=damage&percentile=65,85,95,100&tank_id=<≤100 comma-separated intCDs>`
    `→ {"status":"ok","data":{"distribution":{"<tank_id>":{"65":D1,"85":D2,"95":D3,"100":D4}},`
    `   "updated_at":<epoch>}}`

  Percentiles 65/85/95/100 map straight onto the mod's `{1,2,3,100}` contract (1/2/3 marks +
  the right-edge goalpost); `tank_id` == client `intCD`. `adapter/moe_wgapi.py` is the sole
  provider (behind the `adapter/moe_data.py` facade); there is one build for all channels.

  - **Fetch:** on garage entry, round 1 fetches the selected tank (fast first paint), round 2
    warms the 100 most-recently-played owned vehicles in one request (`adapter/garage_roster.py`
    ranks by the dossier TOTAL `getLastBattleTime()`). Selecting a tank not yet cached fetches
    just that one. `helpers.http.openUrl` is blocking, so each request runs on a worker thread
    and results are adopted on the main thread via a `BigWorld.callback` poll (mirrors the old
    tomato provider's discipline). Missing/invalid `tank_id`s are simply absent from the reply.

  - **Cache:** results are persisted (`mods_data/14th_ua_moe/moe_wgapi_cache.json`) and
    revalidated 24h after the reply's own `updated_at` (Wargaming's data-refresh cadence).

  - **Fallback:** if a request errors (or the API has no data for a tank), `engine_adapter`
    extrapolates that tank's thresholds from the player's single dossier point via
    `domain/moe_estimate.py` — a ~normal-population fit (`d = mu + sigma·Φ⁻¹(p)`), single-sample
    universal prior (`UNIVERSAL_CV`). Estimates are marked and weakest in the tails; a
    still-pending fetch does NOT trigger the fallback (it waits).

  - The fill / current % / current avg damage never depended on the thresholds (they read
    `damageRating`/`movingAvgDamage` directly), so they stay exactly official regardless.

- **Modes / states** — a single MoE bar. Hidden when off the plain garage (reuse the
  sibling's `hangar/{root}` visible-state check) or while a tank-setup overlay is open.

- **Actions it performs** — none in v1 (read-only display; no clickable ticks).

- **Open questions / to verify in-client:**
  - (Resolved) WG API `tank_id` == client `intCD`, and `helpers.http.openUrl` handles the
    HTTPS fetch on a worker thread — both confirmed live via the debug REPL.
  - Calibrate the exact bottom-right anchor: widget width to match the top-right
    Battlepass/missions widgets, and per-carousel-case bottom offsets, via the debug REPL
    (`getComputedStyle`).
