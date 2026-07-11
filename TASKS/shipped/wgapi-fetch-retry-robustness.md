# Research: WG-API fetch — no retry on transient error + fetch-state-machine traps

_Submitted: repo-wide bug hunt (2026-07-11) · Status: open_

## Summary

The WG-API threshold provider's fetch state machine conflates "tank genuinely absent from the
API" with "the request transiently failed," and has no retry. The headline consequence: **a
single network blip or rate-limit on the session-open batch dooms the entire garage/battle to
the offline estimator for the rest of the session.** Three smaller state-machine traps in the
same file compound or resemble it.

All findings in `adapter/moe_wgapi.py`.

## Findings

### 1. Transient error permanently marks every tank in the chunk `_seen` (no retry) — HEADLINE
`_poll:461-510`. When a fetch yields no data — `_fetch_text` → `None` (network failure), or a
WG error envelope (rate-limit / `REQUEST_LIMIT_EXCEEDED` / bad app-id) → `parse_response`
returns `({}, None)` — `result` is empty, so the `if result:` block (`:478-491`) is skipped,
but the tail still runs:

```python
for cd in chunk:
    _inflight.discard(cd)
    _seen.add(cd)          # <-- every id marked seen, even on a transient failure
```

`_seen` is a permanent "don't refetch" set: `get_thresholds:224` (`if cd not in _seen`) and
`_enqueue:433` (`cd not in _seen`) both refuse to re-queue a `_seen` id, and
`_ensure_list_ready` runs **once** per session (`_list_ready` guard, `:398`). So the tanks are
never refetched. `needs_estimate:279` (`cd in _seen and cd not in _table`) then returns True
for all of them → the whole roster shows *estimated* labels, not real WG data, until client
restart — even though a retry seconds later would succeed.

**Failure scenario:** session-open batch fetches all 100 owned tanks in one request
(`_ensure_list_ready:423`). WG rate-limits that one request (or wifi blips). All 100 land in
`_seen`; every tank shows the estimator all session. The code cannot tell a transient failure
from a permanent no-data.

**Severity:** wrong-answer (session-long degraded accuracy). **Confidence:** high on behavior.

### 2. `_inflight` leak / queue stall if `_pump` or `_poll` raises after popping a chunk
`_pump:444-458`, `_poll:506-510`. `_enqueue` adds ids to `_inflight`; `_pump` does
`_queue.pop(0)`. If `_build_url` or `_FetchThread(...)` raises (`:452`), the `except` resets
`_busy=False` but the popped chunk is **gone from the queue and its ids stay in `_inflight`
forever**. `_poll`'s bottom `except` (`:506-510`) is worse: it clears `_busy`/`_thread` but
never discards the chunk from `_inflight`, never adds it to `_seen`, and never calls `_pump()`.
Orphaned-in-`_inflight` ids are unrecoverable: `_enqueue` skips them (`cd not in _inflight`),
`get_thresholds` can't re-queue, and they never enter `_seen` (so no estimate either) → bare
ticks, no labels, no fallback, forever. Rare trigger, unrecoverable state.
**Severity:** latent. **Confidence:** medium.

### 3. Empty `APP_ID` does not short-circuit fetching
`:68, 428-458, 530-533`. No `if not APP_ID: return` guard anywhere. A build with no `.env` (or
a source checkout) still issues a real HTTP GET with `application_id=` empty, which WG rejects
→ (via #1) all tanks `_seen` → estimator. `build_config.py:8-10`'s docstring claims blank
degrades to "ticks without per-mark labels," but the actual result is *estimator output* plus a
pointless external round-trip every session. **Severity:** latent/cosmetic (compounds #1).
**Confidence:** high.

### 4. Lazy single-tank fetch re-stamps `fetched_at` for the ENTIRE cached table
`_poll:490-491` + `_save_cache:587-598` + `fresh_table:160-184`. Freshness is stored per-file,
not per-tank: any fetch sets `_fetched_at = now` and `_save_cache` rewrites the whole `_table`
under that single `fetched_at`. Fetching one newly-selected tank at T+20h resets the 24h
window for every tank cached at T, so genuinely older per-tank data is served as "fresh."
Mostly masked by the `updated_at`-change trigger — but not when WG's daily publish lags (same
`updated_at` returned, no `data_changed` refetch). **Severity:** latent (bounded by the
design's accepted 1–2 day lag). **Confidence:** medium.

## Suggested approach

- **#1 (the real fix):** distinguish transient failure from permanent no-data. Only add ids to
  `_seen` when the request **succeeded** (`result is not None` from a well-formed WG envelope)
  *or* the tank was explicitly absent from a successful `distribution`. On a network/error
  response, discard from `_inflight` but leave OUT of `_seen` so a later trigger (or a bounded
  retry with backoff) can re-fetch. Have `parse_response` (or the worker) signal
  request-level failure distinctly from empty-distribution (today both collapse to `({}, None)`
  — see `:117-124`). A small bounded retry (N attempts, backoff) on the batch would also
  address the common rate-limit case.
- **#2:** in both `except` blocks, discard the popped chunk's ids from `_inflight` (and call
  `_pump()` in `_poll`'s except) so the queue can't stall and ids aren't orphaned.
- **#3:** early-return from `_enqueue`/`_pump` when `not APP_ID`, and make `needs_estimate`
  reflect "no source configured" so the doc matches reality (or intentionally route to the
  estimator, but skip the doomed HTTP round-trip).
- **#4:** if per-tank freshness matters, store `fetched_at` per row rather than per file; else
  document that freshness is table-global and accept it (the `updated_at` trigger is the
  primary invalidation — #4 may be acceptable as-is, decide explicitly).

Note the interaction: #1 makes the estimator fire roster-wide on one error, which is exactly
when the estimator's own low-percentile blow-up ([[moe-estimator-prior-blowup]]) can surface.

## Touch points

- `adapter/moe_wgapi.py`: `_poll:461-510`, `_pump:444-458`, `_enqueue:428-441`,
  `get_thresholds:207-226`, `needs_estimate:270-279`, `parse_response:109-157`,
  `_build_url:530-533`, `_save_cache:587-598`, `fresh_table:160-184`
- `src/res/scripts/client/moe_calculator/build_config.py:8-10` (doc claim vs behavior)

## Verification

- Unit-test `_poll` with a worker whose `result` is `None`/`{}` and `error` set: assert the
  chunk's ids are NOT added to `_seen` (retry-able), vs. a successful response missing a tank:
  assert that tank IS `_seen` (no pointless retry). Tests monkeypatch `helpers`/`BigWorld`
  already (see `tests/`), so the poll loop is drivable.
- Unit-test #2: force `_FetchThread` to raise; assert `_inflight` is emptied and the queue
  drains.
- In-client: block/throttle the API (or point `API_URL` at a dead host) at session start,
  confirm labels recover on a later trigger instead of staying on the estimator all session.

## Open questions

- Retry policy: bounded retry-with-backoff on the batch, or just "don't `_seen` on transient
  failure and let the next natural trigger refetch"? The latter is simpler but only recovers on
  a buy/sell/select/battle; a weak session might never trigger one.
- #4: is per-file freshness acceptable given the `updated_at` trigger, or worth per-row?
