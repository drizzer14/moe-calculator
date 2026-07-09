# Research: In-battle baseline empty in replays / tanks never seen in garage (BUG B)

_Submitted: repo-wide bug hunt (2026-07-09) — long-known latent "BUG B: empty replay baseline" · Status: open_

## Summary

The in-battle overlay projects from a career baseline (`pre_percentile`, `pre_avg`) that is
only ever captured in the **garage**. Any path that enters battle without a garage visit for
that tank this session — a **replay**, or a **mid-battle relogin** (crash → reconnect
straight into the arena) — leaves the baseline empty, and the overlay confidently shows
garbage: a few percent for a 70%+ tank, plus a nonsense delta. It should either recover a
baseline or hide the percent rows.

## Findings

- `src/res/scripts/client/moe_calculator/adapter/baseline_cache.py:22` — module-level
  `_baseline = {}`, seeded **only** by `remember()`.
- The only `remember()` caller is the garage read:
  `adapter/engine_adapter.py:37` (`build_snapshot`, runs on hangar mounts/refreshes).
- In battle, `adapter/battle_adapter.py:190` calls `engine_adapter._read_moe(int_cd)`,
  which **always** returns `(0, 0.0, 0)` in battle — `getVehicleDossier` is a lobby-only
  resource and returns `None` (engine_adapter.py:59-61). The fallback at
  battle_adapter.py:191-198 then tries `baseline_cache.get(int_cd)`; when the cache has no
  entry it logs `"no baseline (tank not seen in garage this session)"` and proceeds with
  `pre_percentile=0, pre_avg=0`.
- The cache's own docstring (baseline_cache.py:17-19) documents this degrade path.

## Root cause

Nothing seeds the baseline on the battle-entry-without-garage path. And the damage is
**twofold** — not just a lost anchor:

1. `domain/battle_builder.py:102` — `proj = ewma_project(pre_avg=0, cd)` =
   `round(EWMA_K * cd)` with `EWMA_K = 2/101 ≈ 0.0198` (constants.py:27-28). A live
   cd=2000 projects to **~40 damage**, not ~1900 — the EWMA fold collapses when
   `prev_avg=0`.
2. `battle_builder.py:114-117` — `cur_percent = clamp(0 + interp(proj) - interp(0))` ≈ a
   few percent; `pct_delta = inc` is equally meaningless. For a genuinely 73.7% tank the
   overlay reads ~2-3% (matches the "pct=0.0 for a 73.7% tank" symptom recorded in the
   baseline_cache docstring, lines 8-9).

`hasData` stays `True` throughout (it only gates on the threshold table,
battle_builder.py:104-105), so the JS renders the wrong numbers with full confidence.

## Suggested approach

Two complementary layers; the first is the honest minimum:

1. **Fail-soft display (small, self-contained):** thread a `has_baseline` flag
   (`pre_percentile > 0 or pre_avg > 0`) from the snapshot through
   `build_battle_model` → `BattleMoEVM` → JS, and hide (or dash out, e.g. `--%`) the
   percent + delta rows when it's false. Combined damage / projected avg row can stay —
   though note proj is also wrong (collapsed EWMA), so consider showing raw CD only.
2. **Baseline persistence (bigger, optional):** persist `_baseline` to a mod-local JSON so
   the last-known garage baseline survives sessions and covers replays of tanks you own.
   This couples with the settings-store plumbing planned for positioning Phase 3 — see
   TASKS/mod-positioning-handoff.md (drag-and-drop persist needs the same store). A
   replayed tank you've never owned still has no baseline → layer 1 remains necessary.

## Touch points

- `domain/battle_types.py` (snapshot/model fields), `domain/battle_builder.py:96-127`
- `adapter/battle_adapter.py:186-214`, `adapter/baseline_cache.py`
- `bridge/view_models.py:107-141` (`BattleMoEVM` — note it declares `properties=7` with
  only 6 registered, see TASKS/small-correctness-fixes.md; a new flag would use the spare
  slot the RTL/row-mode backlog entries are also eyeing)
- `bridge/battle_bridge.py` push path
- `src/res/gui/gameface/mods/14th_ua/MoECalculator/MoEBattle.js:89-119` (render gate)

## Verification

- Unit: `build_battle_model` with `pre_avg=0, pre_percentile=0` + real thresholds —
  assert the model flags no-baseline (new behavior); this doubles as the missing
  regression test (see TASKS/test-coverage-gaps.md).
- In-client: play a replay without visiting the garage → overlay must show the degraded
  (hidden/dashed) form, not ~2%. Check `python.log` for the
  `[moe-battle] no baseline` line as the trigger marker.
- Normal flow regression: garage → battle on a marked tank still shows the anchored percent.

## Open questions

- Should the whole overlay hide instead of dashing the two bottom rows? (User call —
  replays are also where people *most* want the CD readout.)
- Is a battle-side dossier read truly impossible? `getVehicleDossier` is None in battle
  (verified by the docstring's live log evidence), but an early read at battle *loading*
  (before lobby teardown) hasn't been probed via the REPL.
