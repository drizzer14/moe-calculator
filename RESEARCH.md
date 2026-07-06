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

- **MoE damage thresholds (NOT available client-side) — the runtime data source:**
  The 65/85/95% combined-damage thresholds are computed server-side and never sent to the
  client, so they are **fetched live at runtime** and cached.
  - **Primary source (verified working, unauthenticated):**
    `https://tomato.gg/moe/<SERVER>` where `<SERVER>` ∈ `EU` / `NA` / `ASIA`. The page is
    App-Router SSR; the full per-tank table (~768 tanks) is embedded in the HTML flight
    payload as JSON records of the shape:
    `{"65":1291,"85":1858,"95":2287,"100":2641,"id":1073, ...diffs/percents...}`
    where `"65"/"85"/"95"` are the 1/2/3-mark combined-damage requirements, `"100"` is the
    100% mark, and `"id"` is the WG tank id (e.g. 1073 = Tiger I). Parse by extracting all
    records matching that field pattern; key by `id`. Use `EU` for this client.
    - **Fetch discipline:** one request per session (≈640 KB), cache in memory + on disk with
      a TTL (e.g. 24 h); identify the mod in the User-Agent; degrade gracefully (blank the
      per-mark labels) on any network/parse failure. Verify in-client that tomato's `id`
      equals the client `intCD` (Tiger I intCD should read 1073); adjust the key map if not.
  - **Fallbacks:** tomato.gg authenticated API (`api.tomato.gg`, `x-api-key`, 60 req/min) —
    bulk MoE endpoint undocumented; or modxvm `https://static.modxvm.com/wn8-data-exp/json/wn8exp.json`
    (unauth, bulk, `IDNum` = tank id) but that is WN8 **expected damage**, a rough proxy, NOT
    real MoE percentile thresholds — label clearly as an estimate if ever used.
  - The base URL + server are centralized in `adapter/moe_data.py` so the source can be
    swapped without touching the rest of the mod.
    NB: the `me.poliroid.tomatogg` .wotmod is an updater-stub package (downloads its logic +
    data at runtime, no in-package URL) — not a usable static source; tomato.gg's SSR page is.

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
