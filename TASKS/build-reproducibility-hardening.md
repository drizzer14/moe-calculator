# Research: Build reproducibility & packaging hardening

_Submitted: repo-wide bug hunt (2026-07-11) · Status: open_

## Summary

The packaging is functionally correct (STORED zip, `meta.xml` at root, ships `.pyc` and drops
`.py`, excludes `__pycache__`/`.env`/tests, app_id injection fails safe). The issues are about
the **reproducible-build guarantee not actually holding** (and leaking the dev's local path
into shipped artifacts), plus a few smaller build-hygiene items.

## Findings

### 1. Reproducible-build guarantee is violated by `co_filename` — HEADLINE
`build/build_wotmod.py:96-116`. The docstrings claim "identical source → byte-identical
.wotmod" (for release checksum verification) and `_normalize_pyc` zeroes the pyc mtime toward
that. But `py_compile.compile` embeds the **source path as `co_filename`** in every `.pyc`:
- `build_config.py` is compiled from a **`NamedTemporaryFile`** copy (`:107`), so its
  `co_filename` is a **random temp path that changes every build** → `build_config.pyc` is
  never byte-stable, even on the same machine — defeating the exact-diff/checksum verification
  this determinism work exists for.
- Every other `.pyc` embeds the builder's **absolute source path** (`os.walk(RES)` yields
  absolute paths), so the artifact is only reproducible on an identical checkout path, and each
  shipped `.pyc` **leaks the dev's Windows home/username** (`C:\Users\Dmytro Vasylkivskyi\...`).

**Impact:** release "verify by checksum" gives false diffs; artifacts carry the developer's
local path. Functionally harmless to the running mod. **Confidence:** high (path is embedded);
medium (on how much the project cares). **Fix:** pass a stable `dfile=` to `py_compile.compile`
(the arc-relative path) for **all** files, including `build_config`.

### 2. Hardcoded 4-part `CLIENT_VERSION` still ungated by `check_version.py`
`build/build_moe_zip.py:40` `CLIENT_VERSION = "2.3.0.1"` sets the `mods/<client>/` folder layout
in the wgmods zip, but none of `check_version.py`'s patterns match it (uppercase, 4-part; the
prose pattern's `(?!\.\d)` lookahead deliberately rejects it). On a WoT client bump this drifts
silently while `check_version.py` prints "OK," and the wgmods zip lays the mod under a dead
folder → players extract into a path the new client ignores and the mod silently doesn't load.
The same client string is duplicated ungated across `INSTALL.md`, `README.md`,
`installer/readme.moe.txt`, `installer/readme.wgmods.txt`, and the `.iss` comments.
**Already tracked** in `TASKS/code-cleanups-2026-07.md:81` (deferred to fold into the next
release bump) — confirmed still true; cross-referenced here, not re-filed. **Confidence:** high.

### 3. `check_version.py:67` prose version pattern is fragile
`version\s+(\d+\.\d+\.\d+)(?!\.\d)` guards only the 4-part client version. It would
false-mismatch on any *other* 3-part version written as prose (e.g. a doc line "version 1.1.6"
for the bundled OpenWG dep → spurious release-gate failure), and the lookahead lets
"version 0.2.20" match the substring "0.2.2". **Severity:** low (spurious failures / rare
missed drift). **Confidence:** medium. **Fix:** anchor the pattern to the specific files/labels
it means to check rather than free prose.

### 4. Secret briefly written to a temp `.py` on disk
`build/build_wotmod.py:107-113`. The substituted `build_config.py` (carrying the real
`WG_APPLICATION_ID`) is written to a `NamedTemporaryFile`, then removed in `finally`. A short
window exists where the secret sits in the OS temp dir; a kill between write and `os.remove`
leaves it. **Severity:** low — the WG application_id is a low-sensitivity client key and is
extractable from the shipped `.pyc` by design anyway. **Confidence:** high (behavior), low
(severity). **Fix (optional):** compile from an in-memory string via `compile()` +
`marshal`/`importlib` rather than a temp file, if worth it. (Folds naturally into the #1
`dfile=` rework, since both touch how `build_config` is compiled.)

### 5. Debug builder has no lock/abort guard
`tools/dev/build_debug_wotmod.py:56` does `os.remove(out)` with no guard, so if WoT is running
it raises a raw `OSError` instead of `deploy_wotmod.py`'s friendly "close the client" message.
It also skips `_normalize_pyc` and writes `meta.xml` in text mode (CRLF), so the debug artifact
isn't deterministic — acceptable for a dev tool, noted only for parity. **Severity:** low
(dev-only UX). **Confidence:** high.

### 6. Unused disabled-tooltip PNGs ship in every `.wotmod`
`build_wotmod.py:135-136` copies all non-`.py` files, so `tooltip_bg.png` and
`tooltip_divider.png` are packaged into every build although the hover tooltip is disabled
(`TOOLTIP_ENABLED=false`). Small dead weight; harmless but avoidable — and tied to the tooltip
resurrection decision (`TASKS/tooltip-handoff.md`), so don't strip them if the tooltip is
coming back. **Severity:** bloat (low). **Confidence:** medium.

## Suggested approach

#1 (and #4, which rides the same `build_config` compile path) is the real payoff — a stable
`dfile=` for every `py_compile.compile` call makes artifacts byte-reproducible and strips the
dev path. #3 is a small regex hardening. #2 is already deferred to the release bump. #5/#6 are
opportunistic.

## Touch points

- `build/build_wotmod.py:96-116,107-113,130-136` (`_normalize_pyc`, the compile loop)
- `build/build_moe_zip.py:40` · `build/check_version.py:67`
- `tools/dev/build_debug_wotmod.py:56`

## Verification

- #1: build twice from a clean checkout on two different paths (or two machines); diff the
  `.wotmod` — after the fix the `.pyc` bytes should match. Confirm `co_filename` in a shipped
  `.pyc` is the arc-relative path, not `C:\Users\...`.
- #3: run `check_version.py` against a doc containing "version 1.1.6" — should not false-fail.
- #6: unzip a build, confirm which tooltip assets are present vs. referenced by the live CSS.

## Open questions

- Does the project actually rely on byte-reproducible artifacts for release verification, or is
  the guarantee aspirational? (Sizes the priority of #1.)
- Strip the tooltip PNGs now or wait for the tooltip decision (`TASKS/tooltip-handoff.md`)?
