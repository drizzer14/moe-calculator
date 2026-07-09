# Research: Test coverage gaps

_Submitted: repo-wide bug hunt (2026-07-09) · Status: open_

## Summary

The 40+ passing unit tests cover the engine-free `domain/` layer and the pure helpers well,
but the two adapters and the async data machinery are untested, and the just-found BUG B has
no regression test. Closing these would let several fixes in the sibling notes land with
confidence instead of in-client-only verification.

## Findings

- **`adapter/engine_adapter.py` and `adapter/battle_adapter.py`: entirely untested.** The
  interesting branch logic is all here and all reachable with injected fakes:
  - the baseline fallback condition (battle_adapter.py:191-198) — the heart of BUG B;
  - `_is_spectating` / `_in_battle` gating (battle_adapter.py ~150-174);
  - the damage-log summary flag defaults;
  - the unguarded garage tail (engine_adapter.py:32-47, see
    TASKS/small-correctness-fixes.md #3).
  `tests/test_i18n.py` already demonstrates the pattern: fake the game symbol
  (`helpers.i18n`) and exercise the pure logic. The adapters import their game symbols
  lazily/at-top, so a `conftest`-injected fake module (or dependency-injected reader) makes
  the branch logic testable on Python 3.13.
- **`adapter/moe_data.py`: only `parse_table` + `get_thresholds` are tested.** Untested:
  `_poll`'s "empty result dict is skipped by `if result:`" branch (moe_data.py:123-124),
  the failure paths (worker returns None), idempotent `start()` (moe_data.py:90-91), and the
  late-subscriber `add_ready_listener` no-op (see TASKS/code-cleanups-2026-07.md). The poll
  loop needs `BigWorld.callback` faked, but the state machine (`_loaded`/`_loading`/`_table`)
  is plain Python and testable by calling `_poll` directly with a fake thread object.
- **No regression test for BUG B** — nothing asserts `build_battle_model` behavior with
  `pre_avg=0, pre_percentile=0` (the empty-baseline case). This test should be written
  **with** the fix in TASKS/battle-baseline-empty-replay.md so it pins the intended
  degraded behavior rather than the current wrong output.

## Suggested approach

Prioritize by payoff:
1. BUG B regression test (couples with the fix note — write them together).
2. `battle_adapter` baseline-fallback + gating tests via injected fakes (`test_i18n.py`
   pattern) — highest-value branch logic, currently zero coverage.
3. `moe_data` state-machine tests (`_poll` with a fake thread, idempotent `start`).
4. `engine_adapter` tail-guard test (fake that raises in `get_thresholds`).

## Touch points

- `tests/` — new `test_engine_adapter.py`, `test_battle_adapter.py`, extend
  `test_moe_data.py` (or wherever `parse_table` lives), extend `test_battle_builder.py`.
- `tests/conftest.py` — shared fake-game-symbol fixtures (mirror `test_i18n.py`).

## Verification

- `<py3> -m pytest -q` stays green; new tests fail against current code for BUG B (proving
  they'd catch a regression) and pass once the fix lands.

## Open questions

- Prefer `conftest`-injected fake modules (matches existing `test_i18n.py`) or refactor the
  adapters to take an injected reader for cleaner seams? The former is lower-risk and needs
  no source change.
