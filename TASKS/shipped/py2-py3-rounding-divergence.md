# Research: py2/py3 `round()` divergence between in-game runtime and tests

_Submitted: repo-wide bug hunt (2026-07-11) · Status: open_

## Summary

Several display/threshold values are computed with `round()` / `int(round(...))`. The in-game
runtime is Python 2.7.18 (round-half-**away**-from-zero) but the unit tests run on Python 3.13
(banker's rounding, half-to-**even**). At an exact `.5` boundary the two disagree, so the
py3 tests can pin a value that differs by one unit from what ships. Measure-zero inputs, purely
cosmetic (±1), but it means the tests don't actually verify the in-game display at those points.

## Findings

- `adapter/format.py:41` `int(round(p))`, `:54` `round(p, decimals)`, `:59` `int(round(mag))`
  — e.g. `percent(84.5, decimals=0)`: py3 → `"84%"`, py2 → `"85%"`; `signed_percent(0.5,
  decimals=0)`: py3 → `"0%"`, py2 → `"+1%"`. Only the `decimals<=0` paths bite exact halves;
  the default `decimals=1` mainline is rarely affected.
- `domain/moe_estimate.py:162-163` `int(round(mu + sigma*z))` — a threshold landing exactly on
  `N.5` rounds to a different integer in-game than the test asserts (±1 combined damage).
- `domain/battle_builder.py:93` `int(round(prev + k*(cd-prev)))` — the EWMA projection, same
  divergence (±1).

All three share the root: `round()` at an exact half + a py3-only test suite. No
`from __future__ import division` is needed here (every `/` already uses a float literal or
explicit `float(...)`), so this is purely the rounding-mode gap.

## Suggested approach

Use a rounding helper with a deterministic mode independent of the interpreter — e.g. an
explicit half-up: `int(math.floor(x + 0.5))` for non-negative magnitudes (and a signed variant
for deltas), applied everywhere a rounded int/display value is produced. Put it in one place
(`adapter/format.py` already centralizes display; the domain builders could take a small shared
`domain` helper). Then the py3 tests assert exactly what py2 ships.

Low urgency — no visible defect today, but it's the kind of gap that makes a future "the test
passes but the game shows a different number" bug hard to trust.

## Touch points

- `adapter/format.py:41,54,59`
- `domain/moe_estimate.py:162-163`
- `domain/battle_builder.py:93`

## Verification

- Add unit tests at exact-half inputs (`84.5`, `0.5`, a threshold at `N.5`) and assert the
  intended (half-up) result — they'd currently encode py3 banker's behavior, so writing them
  against half-up documents the intended in-game value.
- Cross-check one value in-client (no hot-reload for battle → relaunch) if paranoid.

## Open questions

- Is half-up the desired convention for all three, or does the display prefer truncation
  (`format` already truncates in the JS twin — confirm parity intent between Python and JS)?
