# Research: Small correctness fixes (batch)

_Submitted: repo-wide bug hunt (2026-07-09) · Status: open_

## Summary

A batch of low-severity, individually-small correctness defects found across the Python and
JS layers. None break the mod today (each is fail-soft or empirically tolerated), but each
is a latent trap or a contract violation worth cleaning in one pass. Grouped because they're
too small to each warrant a note but shouldn't be lost.

## Findings

### 1. `BattleMoEVM` declares 7 properties, registers 6
`bridge/view_models.py:112` — `def __init__(self, properties=7, commands=0)` but
`_initialize` adds only indices 0–5 (`view_models.py:117-123`, six `_addXProperty` calls;
comments confirm `# 0` … `# 5`). `MoEVM` (12/12) and `MarkTickVM` (5/5) both match exactly,
so this is a copy/edit slip. **Wulf empirically tolerates it** (the overlay mounts and works
in-game), so it's contract hygiene, not a crasher. Fix: `properties=6`.

### 2. `_safe_int` coerces outside its own guard
`_compat.py:35-36`:
```python
def _safe_int(fn, default):
    return int(_safe(fn, default))
```
`_safe` swallows exceptions from `fn()`, but `int(...)` runs **after** `_safe` returns, so a
non-int-coercible non-None return (e.g. a string `"84.7"`, or an object) makes `int()` raise
**uncaught** — through a helper whose contract is "fall back to default on any failure."
Every adapter read routes through this (`veh.intCD`, `mog.getValue()`, efficiency reads,
`compactDescr`). Doesn't fire today (those return ints) but the promise is broken. Fix:
coerce inside the guard (`_safe(lambda: int(fn()), default)` or try/except the `int`).

### 3. `build_snapshot` tail is outside the try/except
`adapter/engine_adapter.py:24-47` — only the `isPresent()/item` access sits inside
try/except (lines 24-30). After it, `baseline_cache.remember` (`:37`),
`moe_data.get_thresholds` (`:38`), and the `MoESnapshot(...)` construction (`:40-47`) run
unguarded. The battle twin wraps its **whole** body (`battle_adapter.py:180-216`). An
unexpected raise in the garage tail propagates into the hangar mount instead of degrading to
a hidden bar, violating the "every read fail-soft" contract. Fix: extend the guard over the
tail (or add a second try/except), matching the battle adapter.

### 4. Signed-zero delta display (Python + JS)
- Python `adapter/format.py:51` — `signed_percent` guards only `if p == 0` (exact). A tiny
  delta like `-0.04` that rounds to `0.0` at display precision still gets a sign →
  `"-0.0%"`. Fix: test `round(p, decimals) == 0`.
- JS `MoEBattle.js:52-57` — `signedPct(0.004)` → sign from `p > 0`, magnitude floored to
  `0.00` → `"+0.00%"`, and `colourBySign` (MoEBattle.js:118) still paints it green `mb-up`.
- JS zero inconsistency — `pctText(0)` → `"0%"` but `pctText(0.004)` → `"0.00%"`
  (MoEBattle.js:43-47; garage twin MoECalculator.js:48-52 same shape).
  These share the "sub-precision value gets a sign/colour that contradicts its magnitude"
  root; fix Python and JS together so battle-start (small deltas) reads honestly.

### 5. Battle overlay visibility gate relies on VM defaults
`MoEBattle.js:97` — `if (!data || data.visible === false || data.hasData === false)`. The
strict `=== false` means a root VM whose `visible`/`hasData` are still **undefined** (before
Python's first push) slips both guards and paints a "0 / 0 — 0%" stub over the HUD. The
registered view's root VM object always exists, so `!data` is false. Currently safe **iff**
`BattleMoEVM` defaults those bools to `false` (it does — view_models.py:117,123), so the JS
leans on the Python default instead of defending itself. Fix: truthy guard
(`if (!data || !data.visible || !data.hasData)`), matching how the garage widget hides on
`!data`.

## Suggested approach

Independent one-to-few-line fixes; can land as a single "correctness cleanup" commit or be
cherry-picked. #4 (Python + JS) and #5 touch the battle display path — verify those in-client
together. #1 is a pure constant change. #2/#3 are adapter-guard tightening with unit-test
coverage available (see TASKS/test-coverage-gaps.md).

## Touch points

- `bridge/view_models.py:112` · `_compat.py:35-36` · `adapter/engine_adapter.py:24-47`
- `adapter/format.py:44-57` · `MoEBattle.js:43-57,97,118` · `MoECalculator.js:48-52`

## Verification

- `_safe_int` / `format.signed_percent`: add unit tests (`-0.04`, `"84.7"`, an object).
- `engine_adapter` tail guard: unit-test with a fake that raises in `get_thresholds`.
- JS #4/#5: in-client at battle start (small deltas) — no green `+0.00%`, no HUD stub
  before first push. No hot-reload for the battle window → full relaunch to verify.

## Open questions

- #1: confirm `properties=6` still mounts (it should — we're removing a phantom slot). If a
  future property is added for the baseline flag (see TASKS/battle-baseline-empty-replay.md),
  bump deliberately.
