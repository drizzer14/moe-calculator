# Research: Code cleanups & refactors (batch)

_Submitted: repo-wide bug hunt (2026-07-09) · Status: PARTIALLY SHIPPED (2026-07-09, 76fa5c3)_

> **Shipped:** doc/markup drift (position:fixed comment, percent-clamp docstring, inert
> `defer`/`crossorigin`); micro (`markIcon` clamp reuse); `moe_data.add_ready_listener` fires
> immediately if already loaded. **Deliberately NOT shipped (see reasons below / handoff):**
> the JS `thousands`/`pctText` extraction (rejected -- `../../libs/` is OpenWG's shared runtime
> dir, NOT ours to add a `format.js` to; a bad import kills both untested front-ends); the
> bridge listener/refresh-scaffolding extraction (too risky without any bridge test coverage);
> `_RECORD_RX` keyed-JSON rewrite (deferred pending a 2nd data source); ~~the worker-thread
> `LOG_CURRENT_EXCEPTION` invariant contradiction~~ (now DONE, see the finding below); the
> `_AGENT` vs `MOD_VERSION` version dedup (deferred to the **0.2.0 release bump** the
> collision-aware feature triggers — the dedup wants a shared version module + a
> `check_version.py` REQUIRED-list update, so folding it into the bump touches versioning once
> instead of twice); and the `battle_adapter._read_moe` battle short-circuit (foreclosed an
> unprobed early-load dossier read for negligible gain -- keep the seam). `wulf_args.py` stays
> (Phase-3 drag).

## Summary

Non-behavioral cleanups spotted during the bug hunt: duplicated scaffolding, dead-but-kept
code, brittleness, and doc/markup drift. None are bugs; they reduce future-drift risk and
noise. Pick off opportunistically — none is urgent.

## Findings

### Duplication worth extracting
- **Bridge listener/refresh scaffolding** — `gameface_bridge.py:167-223` vs
  `battle_bridge.py:173-228` are near-verbatim twins: `_arm`, `install_all_listeners`,
  `_schedule_refresh`/`_do_scheduled_refresh`, the `_refresh_pending`/`_data_listener_armed`
  globals, the `_LISTENERS` table pattern. The `getattr` divergence in
  TASKS/garage-bridge-lifecycle.md is exactly the drift this breeds. Extract a shared
  listener-manager/coalescer helper.
- **JS format helpers** — `thousands` and `pctText` are byte-identical in
  `MoECalculator.js:39-52` and `MoEBattle.js:36-47` (`signedPct` a near-twin). Both files
  already `import { ModelObserver } from "../../libs/model.js"`, so a shared
  `libs/format.js` is reachable. Keeps the truncate-not-round percent rule in one place.

### Dead / near-dead code
- **`wulf_args.py`** — `map_get`/`cmd_int_arg`/`cmd_xy_arg` have **zero production
  importers** (grep: only `tests/test_builder.py` imports them). BUT this is exactly the
  reverse-channel command-arg parsing the Phase-3 drag-and-drop needs
  (TASKS/mod-positioning-handoff.md). **Do NOT delete** — cross-reference it there so the
  implementer finds it instead of rebuilding it.
- **Disabled tooltip subsystem** — `MoECalculator.js:143-270` + `MoECalculator.css:362-501`
  (~270 lines) ship to every hangar behind `TOOLTIP_ENABLED=false`. The disabled path is
  clean (no dangling DOM/listeners — verified). Kept intentionally (WIP, see
  TASKS/tooltip-handoff.md); noted only for bundle-size awareness.

### Brittleness / maintenance
- **`moe_data._RECORD_RX`** (moe_data.py:37) — order- and field-name-locked regex; any
  tomato.gg field-order/markup change yields `{}`. Degrades gracefully (documented,
  moe_data.py:33-37) but a keyed JSON parse would survive reordering.
- **`moe_data.add_ready_listener`** (moe_data.py:75-79) — a listener registered **after**
  the fetch already completed never fires (`_poll` fires listeners exactly once, line 129).
  Late subscribers can still call `get_thresholds`, so harmless today, but the API silently
  no-ops in that ordering. Consider firing immediately if `_loaded`.
- **`_FetchThread.run` calls `LOG_CURRENT_EXCEPTION`** (moe_data.py:170) from the worker
  thread despite the "Never touches game state" docstring (moe_data.py:155-156). WG logging
  is likely thread-tolerant, but it contradicts the stated invariant. **DONE (working tree,
  UNCOMMITTED, 2026-07-09):** the worker now stashes `traceback.format_exc()` on `self.error`
  and the main-thread `_poll` emits it via `LOG_NOTE` — WG's logger is only ever touched on the
  main thread, honouring the invariant.
- **`battle_adapter._read_moe` in battle** (battle_adapter.py:190) — always returns zeros in
  battle (lobby dossier is None), so it imports dossier symbols + does a lookup every
  snapshot purely to get zeros before falling through to `baseline_cache`. Could
  short-circuit straight to the cache on the battle path.
- **`battle_builder._threshold_stops`** (battle_builder.py:104-106) — battle requires a
  strictly-increasing stop set **including the `100` key**, so a partial table (marks 1/2/3,
  no 100) yields `has_data=False`; the garage `build_model` (builder.py) shows per-threshold
  labels independently. `moe_data` always supplies key 100, so this only bites malformed
  data — but the two builders degrade inconsistently.
- **`build/build_moe_zip.py:40`** — `CLIENT_VERSION = "2.3.0.1"` hardcoded and **not**
  covered by `check_version.py` (its pattern ignores the 4-part client version). A client
  bump silently ships the wrong `mods/<client>/` folder with nothing flagging it.

### Doc / markup drift
- `MoEBattle.css:111` comment says `#moe-battle-root` is `position:fixed`; the actual rule
  (`MoEBattle.css:57`) is `position:absolute` (stacking-context reasoning still holds; only
  the comment is wrong — could mislead a future "fix").
- `format.percent` docstring (format.py:31-32) says "Clamped display" but has no upper clamp
  (`percent(140.0)` → `"140.0%"`); callers pre-clamp, so it's a misleading doc only.
- `MoEBattleView.html:7` — `defer` on `<link>` (not a valid attribute, ignored) and
  redundant `defer` on the module `<script>` (`:15`, module scripts defer by spec);
  `crossorigin` on same-origin `coui://` is inert.
- Version string duplicated in `moe_data._AGENT` (moe_data.py:29) vs
  `mod_moe_calculator.py:17` `MOD_VERSION`; only the latter is `check_version.py`-enforced.

### Micro
- `MoECalculator.js:114` computes `count = max(1,min(3,markCount||1))` then `markIcon(tk)`
  (`:103-107`) recomputes the identical clamp — pass `count` in.
- `MoECalculator.js:109-110` — `renderTicks` does `innerHTML=""` + rebuilds 3 ticks × 3
  child divs every push (per-vehicle-change, infrequent) rather than updating in place.

## Suggested approach

Land opportunistically. The two extractions (bridge scaffolding, JS helpers) are the only
ones with real payoff and both should wait until an adjacent feature touches those files, so
the refactor rides a change rather than standing alone. Doc/markup/micro items are trivial
drive-by fixes.

## Touch points

Listed inline per finding.

## Verification

- After the JS-helper extraction: run the mod, confirm both widgets still format numbers
  (garage bar labels + battle readouts) — no hot-reload for battle, so relaunch.
- After bridge extraction: full run of the 40+ domain unit tests plus in-client mount of
  both surfaces (unit tests don't cover the bridge).
- Doc/micro changes: no runtime surface; a build (`build/build_wotmod.py`) + smoke-mount.

## Open questions

- Is a keyed JSON parse for `moe_data` worth it, or is the regex + graceful-degrade
  acceptable given tomato.gg is the single source? (Ties to whether a second data source is
  ever added.)
