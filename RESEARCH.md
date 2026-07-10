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

- **MoE damage thresholds (NOT available client-side) — the data source:**
  The 65/85/95% combined-damage thresholds are computed server-side and never sent to the
  client. Neither the official WG public web API nor the game client exposes the *population*
  thresholds — WG returns only the player's OWN result (dossier `damageRating` = their achieved
  percentile, `movingAvgDamage` = their EWMA combined damage). The mod ships **two build
  variants**, selected at package time by `moe_calculator/build_config.py::MOE_DATA_SOURCE`
  (see `adapter/moe_data.py`, the source router):

  - **`offline` (WGMods release) — no external API.** `adapter/moe_offline.py` ESTIMATES each
    tank's thresholds from the client's own dossier. Every garage read is one point
    `(movingAvgDamage, damageRating)` on that tank's combined-damage→percentile curve; the
    samples accumulate per tank (persisted under the prefs dir: `mods_data/14th_ua_moe/
    moe_samples.json`) and feed `domain/moe_estimate.py`, which assumes a ~normal population
    (`d = mu + sigma·Φ⁻¹(p)`), fits `(mu, sigma)` by OLS over ≥2 percentile-spread samples,
    and reads off the 65/85/95/99 targets. A single sample still yields an estimate via a baked
    universal prior (`UNIVERSAL_CV`, derived once at dev time by `tools/dev/derive_moe_prior.py`
    — median σ/µ over ~760 EU tanks ≈ 0.808; normal-fit residual at the 85th ≈ 1.4%). Results
    are ESTIMATES; caveats: weakest in the tails / when extrapolating far from the player's
    current standing; a never-played tank shows no labels.

  - **`tomato` (GitHub release, default) — crowd-sourced exact values.** `adapter/moe_tomato.py`
    fetches `https://tomato.gg/moe/<SERVER>` (`EU` here). App-Router SSR; the per-tank table
    (~768 tanks) is embedded in the HTML flight payload as JSON records
    `{"65":1291,"85":1858,"95":2287,"100":2641,"id":1073, ...}` (`"65/85/95"` = 1/2/3-mark
    requirements, `"100"` = the 100% goalpost, `"id"` = WG tank id == client `intCD`). One
    request per session (≈640 KB) on a worker thread; degrades gracefully (blank per-mark
    labels) on any network/parse failure. NB: the `me.poliroid.tomatogg` .wotmod is an
    updater-stub (no in-package URL) — not a usable static source; tomato's SSR page is.

  - The fill / current % / current avg damage never depended on the table (they read
    `damageRating`/`movingAvgDamage` directly), so they stay exactly official in both variants.

- **Modes / states** — a single MoE bar. Hidden when off the plain garage (reuse the
  sibling's `hangar/{root}` visible-state check) or while a tank-setup overlay is open.

- **Actions it performs** — none in v1 (read-only display; no clickable ticks).

- **Open questions / to verify in-client:**
  - Confirm tomato.gg `id` == client `intCD` for the vehicle key mapping.
  - Confirm the in-client HTTP mechanism (WoT Python 2.7 HTTPS): worker thread +
    `urllib2` with an SSL context, marshalling the parsed table back to the main thread via
    `BigWorld.callback`. Check whether the bundled Python 2.7 verifies TLS certs.
  - Calibrate the exact bottom-right anchor: widget width to match the top-right
    Battlepass/missions widgets, and per-carousel-case bottom offsets, via the debug REPL
    (`getComputedStyle`).
