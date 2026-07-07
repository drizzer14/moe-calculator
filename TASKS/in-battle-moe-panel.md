# Research: In-battle MoE info (into the battle damage-log panel)

_Submitted: "add mod info into battle — into the Log panel from the screenshot; display current
damage counted towards MoE, current percent, current MoE (damage), and percent delta. Also:
best way to debug this without going into battle." · Status: open_

> ⚠️ Big feature — the mod is **garage-only** today; battle is a new UI context. The battle
> symbols + MoE formula below were researched against the StranikS-Scan decompiled client.
> **UPDATE (2026-07-06):** a full decompile IS on disk at `~/wot-eu` (branch `2.3`; recorded in
> the `wotmod-debug-repl` harness skill). The core battle symbols are now **source-verified**:
> `sp.shared.{personalEfficiencyCtrl,vehicleState}`, `getTotalEfficiency`/`onTotalEfficiencyUpdated`,
> `PERSONAL_EFFICIENCY_TYPE.{DAMAGE=1,ASSIST_DAMAGE=2,STUN=32}`, `vehicleState.getControllingVehicleID`,
> `arena.vehicles[vid]['vehicleType'].type.compactDescr`, and the `PlayerEvents` arena hooks.
> **Inject host RESOLVED (live replay via REPL, 2.3.0.1):** the battle app is Scaleform
> (`gui.Scaleform.battle_entry.BattleEntry`) that slots Gameface children; the persistent
> Gameface root is **`gui.impl.pub.main_view.MainView`** (layoutID=1, layer=1, whole-battle,
> has `_onLoading`+`getViewModel`). OpenWG (`gf_mod_inject`/`ModInjectModel`) is loaded in
> battle and other mods inject there (`PMODBattleInjector`/`BattleEquipmentInjector` windows at
> layer 7). So `_install_battle` patches `MainView._onLoading`, gated on `arena` present (that
> class is also the lobby root). `getTotalEfficiency(DAMAGE/ASSIST/STUN)`, the vehicle-intCD
> path, and `ARENA_PERIOD.BATTLE`(=3) all confirmed live. Only remaining: build+deploy the real
> mod and eyeball the overlay (metrics 2–4 need a tank YOU'VE played — in a replay the dossier
> baseline reads YOUR account's stats for the replayed tank, so an unplayed tank shows 0).

## The panel in the screenshot
It's the in-battle **damage panel / personal-efficiency log** (bottom-left HUD): a summary
block (damage dealt ✕, blocked 🛡, assisted 📡, received ↓) above a per-hit **damage log**
(`320 ✕ T34`, `151 📡 T34`, …). WG's own component, fed by the battle "personal efficiency"
controller. The user wants our MoE readout added into / beside this area.

## What exists today to reuse
- **Thresholds** (`adapter/moe_data.py`): per-tank `{1:D1, 2:D2, 3:D3, 100:D4}` = combined
  damage for 65/85/95/100th percentile. Fetched once per session, keyed by intCD. This is the
  "MoE (damage)" reference and the axis for turning combined damage → percent. **Works in
  battle too** (in-memory, engine-free fetch) — start it on battle load.
- **Pre-battle standing** (`adapter/engine_adapter._read_moe`): dossier `getDamageRating()`
  (current %, hundredths) + `movingAvgDamage` (current avg combined damage) + `marksOnGun`.
  The dossier is cached client-side, so it's **readable in battle** as the baseline to delta
  against.
- **Pure domain + formatting** (`domain/`, `adapter/format.py`) — reuse `thousands()`,
  precise-percent formatting, clamping. Keep the new battle math in a **pure, engine-free**
  module so it unit-tests like the rest.

## Architecture — extend the existing layering to battle
Mirror the garage stack, add a parallel battle path (keep the domain engine-free):
- **`adapter/battle_adapter.py`** (NEW, PC-only) — read live combat stats into an engine-free
  `BattleSnapshot` (combined damage so far, its components, intCD). Guarded reads like
  `engine_adapter`.
- **`domain/battle_builder.py`** (NEW, pure) — turn `BattleSnapshot` + thresholds + pre-battle
  standing into the 4 display values (below). Unit-testable on plain Python 3.
- **`bridge/battle_bridge.py`** (NEW, PC-only) — mount our Gameface widget into the battle HUD,
  push a `BattleMoEVM`, and re-arm battle listeners each battle load (battle teardown drops
  hangar-scoped delegates; assume battle-scoped ones need re-arming too).
- **`bridge/view_models.py`** — add a `BattleMoEVM` (or extend) with the 4 numeric fields.
- Entry point (`gui/mods/mod_moe_calculator.py`) wires the battle bridge alongside the garage one.

## The four metrics — definition + computation
Let `C` = live combined damage this battle (from the battle adapter), and the fetched
thresholds `D1/D2/D3/D100`. Pre-battle dossier gives standing `curPct` and `avgDmg`.

1. **Current damage counted toward MoE** = `C`. WG's official combined-damage formula is
   **`CD = damage_dealt + max(spot_assist, track_assist, stun_assist) − team_damage`** — the
   **MAX** of the assist streams (stun included), **not their sum** (WG support #15060). ⚠️
   **Live limitation:** the battle controller merges spot+track into ONE `ASSIST_DAMAGE`
   bucket (only post-battle splits them), with `STUN` separate — so live we can only compute
   an **approximation**, e.g. `C ≈ damage + max(ASSIST_DAMAGE, STUN)`. This **over-counts**
   vs. true CD when a tank earns both spotting AND track assist in the same battle (they get
   summed in `ASSIST_DAMAGE` but WG takes the max). For most tanks one stream dominates so
   it's close; scouts/arty diverge. An exact live CD needs raw per-event interception via the
   feedback adaptor — flag as a known caveat, or label the number "≈". Display `thousands(C)`.
2. **Live average MoE including this CD** = the projected moving-average combined damage if
   this battle (CD = `C`) is folded into your rating: `avgWithCD = avgDmg + k·(C − avgDmg)`,
   EWMA `k = 2/(N+1)`, N≈100 → `k ≈ 0.0198` (see §3; `k` is a community assumption — validate).
3. **Current percent** = the MoE % of that projected average `avgWithCD`, by piecewise-
   interpolating it over the threshold stops `[(0,0),(65,D1),(85,D2),(95,D3),(100,D100)]`
   (same axis as the garage `barX`, inverted: damage→percent). = "where you'd stand if the
   battle ended now."
4. **Percent delta** = `pct(avgWithCD) − curPct` — how much this battle moves your standing %
   (signed; `curPct` = pre-battle dossier `damageRating`).

### Presentation — user-confirmed layout (two damage-panel log rows)
Render as two rows styled like the panel's own log rows (right-aligned value + icon + label):
- **Row 1:** `live CD  /  live average MoE (incl. this CD)` → metrics 1 & 2.
- **Row 2:** `current percent   ·   percent delta` → metrics 3 & 4 (delta signed, e.g. `+0.4%`).

Note this layout **commits to the moving-average projection** (metrics 2–4 all derive from
`avgWithCD`), so the EWMA `k` assumption is now load-bearing — see the validation item in the
verify-live checklist. (Interpretation to confirm: "current percent" = % of the projected
average `avgWithCD`, as above — not the raw this-battle-CD percentile.)

## Reference examined: lebwa gunmarks mod (`tv.lebwa.gunmarks_1.3.08`)
Extracted from the live install (`mods/2.3.0.1/`). **Not usable as a code reference** — but
informative:
- **Rendering is Flash**, not Gameface: `res/gui/flash/gunmarks-lebwa-{battle,lobby}.swf`. An
  established in-battle MoE mod uses a Flash panel — consistent with the battle HUD being
  Flash-friendly. (We stay Gameface via a standalone overlay; we can't copy its rendering.)
- **Logic is one protected module** `mod_lebwa_gunmarks.pyc` — **encrypted/obfuscated** (the
  whole file is high-entropy; zero readable symbols/strings, unlike a normal py2.7 `.pyc`). So
  the exact CD formula, controller symbols, and averaging scheme **cannot be lifted from it** —
  we rely on the web-researched symbols (§1/§2) + live REPL confirmation.
- **Readable labels** (`res/mods/lebwa.gunmarks/text/en.yml`) reveal its display model:
  `totalDamageLabel: "Tot. damage"`, `nextPercentLabel: "Damage for {}%"`,
  `unavailableLabel: "Play more battles"`, `lobby/currentValue: "Current total"`. So lebwa
  shows current combined damage + the **damage needed for a target %** (a threshold-table
  approach — same data shape as our tomato.gg thresholds), and gates on battle count. The
  `"Play more battles"` gate is worth mirroring (hide/█ when the tank has too few battles for a
  stable average / when thresholds are unknown).
- Extracted copy in `scratchpad/lebwa/` (session-scoped).

## §1 — Injecting a widget into the battle HUD  (researched; confirm live on 2.3.x)
**`openwg_gameface.gf_mod_inject` is app-agnostic — there is NO separate battle function.**
It's the same call as garage; what changes is *which* ViewModel you attach to. OpenWG's
`resources/in/gui/gameface/js/index.js` auto-loads into **every** Gameface document, scans all
`subViews`, and injects assets for any subView whose model carries a `ModInjectModel` — no
garage/battle conditional (so it should fire in the battle document too; confirm
`window.subViews` is populated in battle).

**Battle HUD architecture gotcha — the damage panel is still FLASH:** the battle app is
`scaleform/battle` (`APP_NAME_SPACE.SF_BATTLE`), a Scaleform host that slots Gameface children.
- **Flash (CANNOT `gf_mod_inject`):** the **damage panel / personal-efficiency panel**
  (`gui/Scaleform/daapi/view/battle/shared/damage_panel.py`) and crosshair — i.e. the "Log"
  panel in the screenshot itself is Flash. **So we cannot inject *into* it** — reinforcing the
  standalone-overlay approach below and ruling out the "inside WG's panel" option.
- **Gameface VMs (hookable):** views under `gui/impl/battle/battle_page/` — e.g.
  `ammunition_panel/*_inject.py`, `battle_context_hints/`, `carousel/prebattle_carousel_inject.py`,
  `battle_notifier/`. There is **no** single monolithic "BattlePage" VM.
- WG's own native battle-mount pattern is **`InjectComponentAdaptor`**
  (`gui.Scaleform.framework.entities.inject_component_adaptor`) — the authoritative example.

**Two viable strategies:**
1. **Standalone Gameface overlay (recommended)** — our own `ViewImpl` in a Wulf `WindowImpl`,
   layered over the HUD, `pointer-events:none`, positioned in the damage-log corner. Version-
   robust, Fair-Play clean, independent of WG internals. (Since the damage panel is Flash, an
   overlay positioned *near* it is the only clean option anyway.)
2. **Piggyback a battle Gameface VM** — monkeypatch one of the `*_inject.py` battle VMs and
   `gf_mod_inject` onto it (direct analogue of the garage `HangarVehicleParamsPresenter` flow).
   Reuses a mounted battle document, but is fragile against generated-name changes across patches.

**Lifecycle events** (`PlayerEvents.g_playerEvents`): `onAvatarBecomePlayer`/`onAvatarReady`
(mount), `onAvatarBecomeNonPlayer` (teardown → **re-arm every battle**), `onArenaPeriodChange`
with `ARENA_PERIOD {IDLE0, WAITING1, PREBATTLE2, BATTLE3, AFTERBATTLE4}` (gate "combat started"
on `BATTLE`), `onBattleResultsReceived`.

## §2 — Reading live combined damage in battle  (researched; confirm field names on 2.3.x)
Use the **`PersonalEfficiencyController`** — `gui/battle_control/controllers/personal_efficiency_ctrl.py`
(this is what feeds the screenshot's panel). Access it via the battle session provider:
```python
from helpers import dependency
from skeletons.gui.battle_session import IBattleSessionProvider
sp = dependency.instance(IBattleSessionProvider)
ctrl = sp.shared.personalEfficiencyCtrl          # the controller
# sp.shared.feedback -> BattleFeedbackAdaptor (raw upstream; only if you need per-event splits)
```
- **Read totals:** `getTotalEfficiency(eType)`; **subscribe** to `onTotalEfficiencyUpdated(totals)`
  (full dict) for live cumulative updates. (`onTotalEfficiencyChanged` does NOT exist.)
- **Stat keys** — `PERSONAL_EFFICIENCY_TYPE` in `gui/battle_control/battle_constants.py`:
  `DAMAGE=1, ASSIST_DAMAGE=2, BLOCKED_DAMAGE=4, RECEIVED_DAMAGE=8, RECEIVED_CRITICAL_HITS=16,
  STUN=32`.
- **Assist-merge caveat (see metric 1):** `ASSIST_DAMAGE` = spot+track merged; only `STUN` is
  separate live. `IBattleFieldCtrl` is NOT relevant (team health/spotted only).

## §3 — MoE math (pure domain)
- **damage→percent:** piecewise-linear interpolate `C` over the fetched threshold stops
  `[(0,0),(65,D1),(85,D2),(95,D3),(100,D100)]` (clamp 0..100). **These thresholds ARE WG's
  per-tank/per-region 14-day percentile distribution** (that's exactly what tomato.gg publishes
  and `moe_data.py` already fetches) — so the mapping needs no extra data source. `thisBattlePct`
  feeds metrics 2 and 4a.
- **The rating is a moving average** (WG-official but vague: "~50–100 battles"). The specific
  scheme — EWMA `newEMA = prevEMA + k·(CD − prevEMA)`, `k = 2/(N+1) ≈ 0.0198` for N=100 — is
  **community-reverse-engineered, NOT WG-confirmed**; treat `k` as an assumption to validate.
- **Metric 4b (projected rating change), if wanted:** you can compute the per-battle EMA *damage*
  step client-side (given prevEMA=`avgDmg` and this battle's `CD`), but converting the new EMA to
  a **percentage** still needs the percentile table — which we have. So 4b is feasible but doubly
  approximate (EMA `k` guess × threshold interpolation). **Recommend metric 4a** (this-battle-%
  minus standing-%): exact given our data, no `k` assumption.

## Debugging this WITHOUT going into battle  (the user's sub-question)
**User confirmed: debugging in replays.** Best loop, in order (replays first, as chosen):
1. **Replays (primary).** WoT replays a `.wotreplay` through the **full battle client + HUD**,
   re-runnable and deterministic — the damage/assist totals evolve exactly as recorded, so it
   exercises §2 (live-stat reading) and the UI end-to-end with **no queue, no live match**.
   Pause/seek to hit specific damage states. Requires replay saving enabled
   (`replay` settings / launch with a `.wotreplay`). This is the standard battle-UI dev loop.
2. **Debug TCP REPL — synthetic push (fast visual/layout loop).** Push fake values for the 4
   fields straight into `BattleMoEVM` (via the REPL, like the garage bridge's `refresh()`), to
   iterate on **layout/style** instantly without any battle. Doesn't exercise the live-stat
   reader, but nails placement/legibility over the HUD. (See `wotmod-debug-repl`.)
3. **Training room** — a 1-player room is a real battle context (mounts the HUD, live
   controllers) with no matchmaker; good for confirming §1 injection + §2 reads against real
   (if sparse) combat, when you want live rather than replayed data.
4. **REPL introspection in a replay/training room** — run the bytecode-arg + live-call probes
   from `wotmod-debug-repl` against the real battle controllers to discover the §1/§2 symbols
   before coding.

Recommendation: **discover symbols in a replay via the REPL (steps 4+1), build the reader,
then iterate the widget visually via synthetic REPL pushes (step 2)** — reserving live queue
battles for final confirmation.

## Verify-live checklist before coding (in a replay/training room, via the REPL)
1. Confirm OpenWG's `index.js` injector actually runs in the `scaleform/battle` document —
   `window.subViews` populated in battle.
2. Confirm `personal_efficiency_ctrl` field names on the exact 2.3.x client: `getTotalEfficiency`,
   `onTotalEfficiencyUpdated`, and the `PERSONAL_EFFICIENCY_TYPE` values (`DAMAGE`/`ASSIST_DAMAGE`
   /`STUN`). Read arg names off the bytecode + call live (per `wotmod-debug-repl`).
3. Pick the concrete host VM (or commit to the standalone overlay) — enumerate
   `gui/impl/battle/battle_page/**/*_inject.py` VMs live; confirm one accepts `gf_mod_inject`.
4. Sanity-check `moe_data.get_thresholds(intCD)` returns for the played tank in battle.
5. Validate the EWMA `k = 2/101` assumption against a few real battles (or a per-tank table)
   before trusting metric 4b; prefer metric 4a which needs no `k`.
6. Empirically check the assist-merge over-count (metric 1) on a scout/arty replay.

## Touch points (new + edited)
- NEW: `adapter/battle_adapter.py`, `domain/battle_builder.py`, `bridge/battle_bridge.py`,
  a battle widget `res/gui/gameface/mods/14th_ua/MoECalculator/…battle.{js,css}` (or reuse).
- EDIT: `bridge/view_models.py` (add `BattleMoEVM`), `gui/mods/mod_moe_calculator.py` (wire
  battle mount), `tools/dev/sync_gameface.py` (hot-reload the battle assets).
- REUSE: `adapter/moe_data.py`, `adapter/format.py`, dossier reads in `engine_adapter.py`.

## Open questions
_Resolved: presentation = the 2-row layout above; metrics 2–4 use the EMA projection; render as
a standalone overlay (the damage panel is Flash, can't inject into it)._
- **"current percent" interpretation** — % of the projected average `avgWithCD` (assumed), vs.
  the raw this-battle-CD percentile? (Confirm.)
- **EWMA `k`** — validate `k = 2/(N+1)` (N≈100) against real replays; the whole 2-row layout
  rides on it. If it's off, the projected average/percent/delta are all skewed.
- Show the lebwa-style **"play more battles" gate** when the tank has too few battles / no
  threshold data?
- Fair Play: read-only info display is fine; keep it to post-facto stats (no per-shot advice)
  — matches what lebwa/WG's own panel already show.

## References (from web research)
- **MoE combined-damage formula** (`damage + max(spot, track, stun) − teamDmg`; max not sum;
  65/85/95 pct over a rolling 14-day per-tank/region window): WG support #15060
  (`wargaming.net/support/en/products/wot/article/15060/`), `mtltemplar.com/marks-of-excellence/`,
  `13disciple.stream/how-moe-work.html`. Moving-average ~50–100 battles is WG-official but
  vague; the EWMA `k=2/(N+1)` coefficient is community-reverse-engineered, not WG-confirmed.
- **Percentile table** (CD→%): tomato.gg (`tomato.gg/moe/EU`), wot-life, gunmarks — already the
  source `moe_data.py` fetches.
- **Battle symbols** (verified against the decompiled client):
  `gui/battle_control/controllers/personal_efficiency_ctrl.py`, `.../battle_constants.py`
  (`PERSONAL_EFFICIENCY_TYPE`), `feedback_adaptor.py`, `common/constants.py` (`ASSIST_TYPES`),
  `PlayerEvents.py`, `skeletons/gui/battle_session.py` — IzeBerg/wot-src
  (`github.com/IzeBerg/wot-src`), mirror StranikS-Scan/WorldOfTanks-Decompiled.
- **OpenWG injection** (`gf_mod_inject`, `index.js` subView scan): `gitlab.com/openwg/wot.gameface`.
  Battle-mount pattern `InjectComponentAdaptor` +
  `gui/impl/battle/battle_page/**/*_inject.py` (StranikS-Scan decompile).
- **`gf_mod_inject` usage examples / docs:** `github.com/wotstat/wotstat-debug-utils`,
  `github.com/wotstat/mods-development-docs`. Closest behavioral match (extends personal-
  efficiency counters, but compiled/no source): Kurzdor "Advanced Personal Efficiency"
  (`github.com/Kurzdor/wotmods-public`). Injection-vs-overlay patterns:
  `modding.wot-tools.dev`.
