# Ideas backlog

Short, one-line entries for future features and bug reports. The **wotmod-planner**
skill researches each submission against the codebase and saves an implementer-ready
note under `TASKS/`; delete an entry here once it ships.

## Open

### Cleanup (batch) — the deferred remainder (all TRIGGER-GATED)
Doc/markup/micro drift, the `moe_data` late-subscriber no-op, and the worker-thread
`LOG_CURRENT_EXCEPTION` invariant all **shipped** (76fa5c3). Everything still listed here is
deliberately deferred behind a trigger condition — none is landable standalone today:
- **Bridge listener/refresh-scaffolding extraction** — wait until an adjacent feature touches
  `gameface_bridge.py`/`battle_bridge.py` AND bridge test coverage exists (too risky bare).
- **`moe_data._RECORD_RX` keyed-JSON rewrite** — only if a 2nd data source is ever added.
- **`_AGENT` vs `MOD_VERSION` version dedup + unchecked `CLIENT_VERSION`** — fold into the
  **0.2.0 release bump** (the collision-aware feature triggers it) so versioning + the
  `check_version.py` REQUIRED-list update are touched once, not twice.
- **Inconsistent partial-table degrade between the two builders** — note-only; only bites
  malformed `moe_data` (always supplies key 100). Intentional; revisit only if a real case appears.
NOT doing: JS `thousands`/`pctText` extraction (`../../libs/` is OpenWG's, not ours);
`battle_adapter._read_moe` battle short-circuit (keep the seam). `wulf_args.py` stays (Phase-3 drag).
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

