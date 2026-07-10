# Research: In-battle overlay dashes ("-") on the very first battle in a tank

_Submitted: "In the very first battle in a tank, in-battle widget shows '-', although MoE data is available for it." · Status: SHIPPED (2026-07-10) — in-game verified (LGTM)._

**Shipped as the suggested approach exactly:** `baseline_cache._seen` set + `seen()` query
(marked on every `remember()`, independent of the >0 value guard); new `BattleSnapshot.baseline_known`
populated in `build_battle_snapshot` from `seen(int_cd)` OR a real >0 read; `has_baseline` in
`build_battle_model` now also passes on `baseline_known`. No JS change. 169 tests pass. Open question
resolved live: a freshly-bought tank IS read by the garage widget before its first battle, so it is
marked seen → projects from a genuine 0. BUG B (never-garaged replay) still dashes.

## Summary
On the first-ever battle in a tank (a freshly-bought tank with **0 career battles**), the
in-battle overlay renders `-` for the projected avg, percent and delta — even though the
per-tank MoE threshold table ("MoE data") is loaded. Only the live combined-damage figure
shows a real number. The user expects a live projection, since the thresholds are available.

This is a **different bug from the shipped BUG B** (replay / relogin-into-battle). It shares the
same symptom and the same gate, but the cause is that the gate cannot tell a *genuinely-zero*
career baseline apart from a *never-read* one.

## Findings — what the code does today
The dash is driven entirely by the `hasBaseline` flag, top to bottom:

- **`MoEBattle.js:125`** — render branch: `if (data.hasBaseline !== false) { …normal… } else { …dash… }`.
  When false, `.mb-avg` → `-`, `.mb-pct` → `-%`, `.mb-delta-num` → `-`; only `.mb-cd`
  (combined damage) stays real (`MoEBattle.js:139-147`). Early in a battle CD is 0, so the
  player sees `0 / -` and `-% (-)` — reads as "the widget shows '-'".
- **`view_models.py:124` (`BattleMoEVM` prop 6 `hasBaseline`)** — pushed straight from the model.
- **`battle_builder.py:108-109`** — the root computation:
  ```python
  has_baseline = ((snapshot.pre_percentile or 0) > 0
                  or (snapshot.pre_avg_damage or 0) > 0)
  ```
  For a never-played tank the career read is `(0, 0.0, 0)`, so **both** terms are 0 →
  `has_baseline = False` → dash. `has_data` is independently True (thresholds loaded), which is
  why the user correctly observes "MoE data is available."
- **`battle_adapter.py:194-202`** — the baseline source. In battle the dossier is unreadable
  (`engine_adapter._read_moe` returns `(0, 0.0, 0)`), so it falls back to `baseline_cache.get()`.
  For a never-played tank that cache is **also** empty (see next), so `pre_avg/pre_percentile`
  stay 0.
- **`baseline_cache.py:25-35` (`remember`)** — **no-ops on an all-zero read** (`if p <= 0.0 and
  a <= 0: return`). So a 0-career tank viewed in the garage leaves **no** cache entry — exactly
  like a tank never seen in the garage at all (the replay/relogin case). Downstream the two are
  indistinguishable.

## Root cause
`has_baseline` overloads one 0/0 signal to mean two different things:

1. **"Baseline unreadable / untrusted"** — replay or relogin straight into battle; the garage
   dossier was never read, so 0 is a *false* zero. Dashing is correct (BUG B, by design).
2. **"Baseline genuinely 0"** — first-ever battle in a tank; the garage dossier *was* readable
   and legitimately reported 0 career damage. Here 0 is the *true* baseline and the projection
   is perfectly well-defined: `proj = ewma_project(0, cd) = k·cd`, and
   `cur_percent = 0 + (interp(proj) − interp(0)) = interp(proj)` — an honest "where this one
   battle places you." (`battle_builder.py:100-124`.)

Because a genuine 0 and an unread 0 both surface as `pre_* == 0` **and** both leave
`baseline_cache` empty (the all-zero no-op), the gate lumps case 2 in with case 1 and dashes a
projection that is actually meaningful.

## Suggested approach
Distinguish "read succeeded, value genuinely 0" from "never read." The cleanest signal we
already have is **whether the garage saw this tank this session** — `baseline_cache` is the
right place to record it, independent of the >0 value guard:

1. **`baseline_cache`** — add a session `_seen` set populated on *every* `remember()` call
   regardless of value (keep the existing all-zero no-op for the `_baseline` *value* map so a
   transient blank never clobbers a real baseline). Add a `seen(int_cd)` query.
2. **`BattleSnapshot`** (`battle_types.py`) — add a `baseline_known` (or `baseline_seen`) bool.
3. **`battle_adapter.build_battle_snapshot`** — set it from `baseline_cache.seen(int_cd)` (OR a
   real >0 read), so the pure builder gets an engine-free signal.
4. **`battle_builder.build_battle_model:108`** —
   `has_baseline = (pre_percentile>0 or pre_avg>0) or snapshot.baseline_known`.

Net effect: a first-ever battle in a tank you *selected in the garage* (the normal buy → battle
flow — the garage widget reads its dossier, marking it seen) projects from a genuine 0 baseline;
a true replay/relogin (never seen in garage) still dashes (BUG B preserved).

Honest uncertainty: this hinges on the garage widget having actually rendered/read the tank
before the battle. That holds for the current/selected tank (its hangar widget mounts at client
start) and for any tank clicked in the carousel, but confirm the "seen" hook fires for a
freshly-bought tank before its first battle (see Open questions). If it turns out the garage
read is unreliable, the fallback is to gate purely on `has_data` (thresholds present ⇒ project
from whatever baseline, including 0) and accept that replays would then also project from 0 —
which would regress BUG B, so it is the weaker option.

## Touch points
- `src/res/scripts/client/moe_calculator/adapter/baseline_cache.py` — `_seen` set, `seen()`.
- `src/res/scripts/client/moe_calculator/domain/battle_types.py` — new `BattleSnapshot` field.
- `src/res/scripts/client/moe_calculator/adapter/battle_adapter.py` — populate the field.
- `src/res/scripts/client/moe_calculator/domain/battle_builder.py:108` — the gate.
- No JS change needed — `MoEBattle.js` already renders the projection when `hasBaseline` is true.

## Verification
- **Unit** (`tests/test_battle_builder.py`, `tests/test_battle_adapter.py`): add a case —
  thresholds present, `pre_avg=pre_percentile=0`, `baseline_known=True` ⇒ `has_baseline True`
  and a non-zero climbing `cur_percent`; and `baseline_known=False` ⇒ still dashes (BUG B). Run
  `python -m pytest` on Python 3.13.
- **In-game**: take a **freshly-bought, 0-battle tank** into a battle; the overlay should show a
  live projected % that climbs with damage, not `-`. Then load a **replay** and confirm it still
  dashes.
- **REPL**: probe the pushed VM — `hasBaseline` should be True for the new-tank battle. Baseline
  cache state via `baseline_cache._seen` / `_baseline` (see `wotmod-debug-repl`).

## Open questions
- Does the garage `build_snapshot` → `baseline_cache.remember` path actually fire for a
  just-purchased tank before you battle it (so it gets marked `seen`)? Confirm live; it's the
  linchpin of the suggested fix.
- Product intent: for a genuine 0 baseline, is a projection anchored on 0 (opening near 0% and
  climbing) the desired display, or would a distinct "new tank" treatment be clearer? Default:
  project from 0 (matches the garage's new-tank `0/0%` precedent).

_Related: `TASKS/shipped/battle-baseline-empty-replay.md` (BUG B — same gate, the case we must
keep dashing)._
