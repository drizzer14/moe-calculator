# Ideas backlog

Short, one-line entries for future features and bug reports. The **wotmod-planner**
skill researches each submission against the codebase and saves an implementer-ready
note under `TASKS/`; delete an entry here once it ships.

## Open

### BUG — garage bridge lifecycle: Rider 2 (only remaining piece)
The `refresh()` view-alive guard + Rider 1 **shipped** (76fa5c3), and the real `_active`
teardown now **landed uncommitted** (2026-07-09) with the collision-aware feature: `bridge.detach()`
clears `_active` + the placement commitment + cached candidate VMs, called from `refresh()`'s
host-gone branch. **Remaining: Rider 2** — does OpenWG re-execute injected modules per mount,
stacking JS `observer.onUpdate` callbacks? Needs a live REPL probe before deciding on a guard
(plus in-client confirmation of the teardown: no `[moe]` push/exception spam during battle).
→ Research: TASKS/shipped/collision-aware-injection.md · TASKS/garage-bridge-lifecycle.md

### Cleanup (batch) — the deferred remainder (PARTIAL)
Doc/markup/micro drift + the `moe_data` late-subscriber no-op **shipped** (76fa5c3); the
worker-thread `LOG_CURRENT_EXCEPTION` invariant now **landed uncommitted** (2026-07-09 — the
worker stashes the traceback, the main-thread `_poll` logs it). **Remaining (each deferred with a
reason in the note):** the bridge listener/refresh-scaffolding extraction (needs bridge test
coverage first); `moe_data._RECORD_RX` keyed-JSON rewrite (only if a 2nd data source is added);
the `_AGENT` vs `MOD_VERSION` version dedup + uncheck'd `CLIENT_VERSION` (deferred to the 0.2.0
release bump the collision-aware feature triggers); inconsistent partial-table degrade between the
two builders. NOT doing: the JS `thousands`/`pctText` extraction (`../../libs/` is OpenWG's, not
ours). `wulf_args.py` stays (Phase-3 drag needs it).
→ Research: TASKS/code-cleanups-2026-07.md

### In-battle overlay — LTR (current) / RTL layout direction
The overlay is built left-to-right (`[icon] [value]`, left-aligned, backdrop fading from the
left, window anchored bottom-left). Add an RTL mode that mirrors it (`[value] [icon]`,
right-aligned, backdrop from the right, and likely a bottom-right anchor). Same wiring as the
single/double-row toggle: a `rtl` VM flag → a `.mb-rtl` CSS class → mirrored overrides (try
`direction: rtl` first, fall back to explicit flex/margin/mask flips). Shares the VM property
slot budget with the row-mode task and couples with positioning (the right-edge anchor).
→ Research: TASKS/in-battle-rtl-layout.md

### Single / double row mode for the in-battle overlay
The in-battle overlay is a fixed two-row vertical stack (row 1 dmg/avg, row 2 %/delta). Add a
single-row mode that lays both metric groups on ONE horizontal line for a shorter footprint.
Mostly CSS: flip `#moe-battle-root` to `flex-direction: row` + kill the column-overlap margin;
drive it off a `compact` flag (mirror the garage's `carouselRows` class-toggle precedent —
BattleMoEVM even has a spare property slot). Couples with positioning (single row is shorter →
re-tune the bottom-flush anchor). Open decision: dev-constant vs a future in-game settings toggle
(no settings backend is wired — would be new plumbing).
→ Research: TASKS/in-battle-single-double-row.md

