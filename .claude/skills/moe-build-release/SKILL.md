---
name: moe-build-release
description: Use when packaging, deploying, testing, hot-reloading, versioning, or releasing the 14th_ua MoE Calculator — which files carry the version, what each build/ script and installer file does, the garage-vs-battle hot-reload split, the debug REPL wiring, and the dev-tools inventory. For feature internals see moe-garage / moe-battle.
---

# MoE Calculator — build, deploy, version & dev loop

Reusable mechanics live in `wotmod-build-deploy`, `wotmod-release`, and `wotmod-debug-repl`;
this skill is the concrete file list and command set. **Two Pythons:** package with
`C:\Python27\python.exe` (bytecode is version-locked), test/dev-tool with Python 3.13.

## Version files (bump together; `src/meta.xml` is canonical)

`build/check_version.py` enforces consistency (`<py> build/check_version.py`, exit 1 on drift):

| File | Reference |
|---|---|
| `src/meta.xml` | `<version>X.Y.Z</version>` — **source of truth** |
| `src/res/scripts/client/gui/mods/mod_moe_calculator.py` | `MOD_VERSION = "X.Y.Z"` |
| `installer/moe_calculator-setup.iss` | `#define ModVersion "X.Y.Z"` + `#define ModWotmod "…_X.Y.Z.wotmod"` |
| `installer/build_installer.ps1` | `$ModWotmod = …com.14th_ua.moe_calculator_X.Y.Z.wotmod` |
| `INSTALL.md` | `MoECalculator-Setup-X.Y.Z.exe`, `…_X.Y.Z.wotmod` |
| `dist/INSTALL.txt` | prose `version X.Y.Z` (gitignored build output; checked when present) |

_`X.Y.Z` is illustrative — the live canonical value is in `src/meta.xml` (currently 1.2.0)._

- `README.md` uses `<version>` placeholders (no hard-coded number). `adapter/moe_wgapi.py`'s
  `_AGENT` string carries the project URL (no version number — nothing cosmetic to bump there).
- The **client** version `2.3.1.0` is deliberately excluded from the check (a `(?!\.\d)` lookahead skips the 4-part client version).

## Release must stay silent (no unconditional logging)

A shipped build must write **nothing** to WoT's `python.log` in normal operation — those logs
are world-readable on every player's machine. Never call `debug_utils.LOG_NOTE` (or `LOG_NOTE`
re-exported from `_compat`) directly for informational output. Route every chatty/internal note
(lifecycle, placement, data payloads, fetch lists) through **`_compat.LOG_DEBUG`**, which is
gated on **`_compat.DEBUG`** (ships **`False`**; flip `True` only for local dev, never commit it
`True`). Genuine failures go through the always-on, path-safe `LOG_CURRENT_EXCEPTION`.

`tests/test_logging_gate.py` enforces this: it fails the build if `DEBUG` is committed `True` or
if any module outside `_compat.py` grows a raw `LOG_NOTE(` call site. **Run the full pytest suite
before every release** (it is part of the gate, alongside `check_version.py`), and eyeball
`python.log` after an in-game smoke test — it should stay clean.

## build/ scripts

- **`build_wotmod.py`** — **Python 2.7 only** (asserts). Reads `meta.xml`, compiles `.py`→`.pyc`
  (drops `.py`, skips `__pycache__`), zips `meta.xml` + `res/` as **`ZIP_STORED`** →
  `dist/com.14th_ua.moe_calculator_<version>.wotmod`. Non-`.py` files (fonts/PNG/JSON) are copied verbatim.
  **Single build, no arguments** — MoE thresholds come from the official WG API at runtime
  (`adapter/moe_wgapi.py`), so GitHub and WGMods ship the identical `.wotmod`.
- **`deploy_wotmod.py`** — Python 2.7. Cleans old `…_[0-9]*.wotmod` from `mods/<ver>/` + loose
  `res_mods` leftovers, calls `build_wotmod.main()`, copies in. Reads `deploy.local.json` if no args.
  `--clean-overlay` removes the hot-reload overlay. **Needs `WorldOfTanks.exe` closed** (`wgc` ok).
- **`build_moe_zip.py`** — any Python. Builds `dist/MoECalculator_<version>.zip` = bilingual
  `readme.txt` (from `installer/readme.moe.txt`, `{VERSION}` substituted, CRLF) + the mod `.wotmod`
  + all `installer/vendor/*.wotmod` under `mods/2.3.1.0/`. Manual upload to wgmods.net. Holds `CLIENT_VERSION="2.3.1.0"`.
  Packages whatever `.wotmod` is in `dist/` — the same single build the GitHub installer uses.
- **`check_version.py`** — the version gate above. **`clean_dist.py`** — prunes non-current release artifacts from `dist/` (`--dry-run`).

## installer/

- **`moe_calculator-setup.iss`** — Inno Setup 6. Detects WoT root, resolves client version, installs
  to `mods\<version>\`, bundles OpenWG from `installer/vendor/` **only if absent**
  (`NeedOpenWg`, `uninsneveruninstall`), cleans old builds, WoT-running guard, GitHub
  Atom-feed self-update. Repo `drizzer14/moe-calculator`, base name `MoECalculator-Setup`.
- **`build_installer.ps1`** — preflights the built `.wotmod` + vendor dep, finds `ISCC.exe`, compiles → `dist/MoECalculator-Setup-<version>.exe`.
- **`readme.moe.txt`** — bilingual EN/UA readme for the wgmods zip. **`readme.wgmods.txt`** — stub (superseded). **`installer/vendor/`** — `net.openwg.gameface_1.1.6.wotmod` + `izeberg.modssettingsapi_1.7.0.wotmod`.

## Hot-reload (the split that bites)

- **Garage widget hot-reloads:** `<py3> tools\dev\sync_gameface.py "D:/Games/World_of_Tanks_EU" 2.3.1.0`
  copies only the Gameface JS/CSS/assets into `res_mods`, then toggle Tech-Tree↔Garage to re-inject. No relaunch.
- **The in-battle registered WINDOW does NOT hot-reload** — its resources pin at client launch;
  reopen and `Window.reload()` both serve the launch-time cached document. **Every CSS/JS tweak to
  `MoEBattle.*` needs a full client relaunch.** Gate the commit on the in-game sign-off (deploy → verify live → commit).
- Clean the `res_mods` overlay before any ship-verification — a stale overlay shadows a fresh packaged build.

## Dev loop / REPL

- Live introspection: build the slim debug package (`tools/dev/build_debug_wotmod.py` →
  `com.14th_ua.moe_calculator_debug.wotmod`, TCP **:2224**), then `<py3> tools\dev\repl_client.py "<expr>"`.
  Multiline needs `execfile(r'<abs path>')`. See `wotmod-debug-repl`.
- Decompiled client source for symbol hunting: `C:\Users\Dmytro Vasylkivskyi\wot-eu\source\res\scripts\client\`.
- **`tools/dev/` inventory:** `sync_gameface.py` (hot-reload), `gen_checker.py` (battle dither PNG),
  `swf_font_to_ttf.py` / `swf_probe.py` (extract `MoEBattle.ttf` from `fontlib.swf`),
  `gen_overlay_tuner.ps1` / `gen_icon_picker.ps1` (browser calibration artifacts → `TASKS/refs/`),
  `mod_moe_calculator_debug.py` (Py2-only REPL server), and the `probe_*` live-discovery scripts.

## Release state

**v0.1.0 through v1.2.0 are published** on `github.com/drizzer14/moe-calculator` (`origin/main`).
The **1.0.0** release retargeted the mod to WoT client **2.3.1.0** (major bump) and added the
Alt-key peek mode + Counted Assistance row; **1.1.0** is a patch-level polish of the in-battle
overlay row/backdrop alignment (shipped as a minor bump by choice); **1.2.0** is a minor bump
carrying the in-battle MoE-projection accuracy work (smooth probit curve + self-calibrating
EWMA `k`) plus the R3 row-backdrop fix — all committed after the v1.1.0 tag but unreleased until then.
Both channels now ship the **same single build** (WG-API threshold source): the GitHub release
carries `MoECalculator-Setup-<ver>.exe` + the bare `.wotmod`, and `MoECalculator_<ver>.zip`
(same `.wotmod` + vendor deps) is uploaded manually to
[wgmods.net/7745](https://wgmods.net/7745/). Since **v0.3.0** the installer and the zip also
bundle **ModsSettingsAPI** (`installer/vendor/izeberg.modssettingsapi_1.7.0.wotmod`) alongside
OpenWG GameFace. The installer self-update reads the GitHub Atom
feed, so keep the `vX.Y.Z` tag + `MoECalculator-Setup-<ver>.exe` asset-name convention. Follow
`wotmod-release` for the bump→tag→build→publish flow.

**GitHub release title = `vX.Y.Z` (v-prefixed), strictly.** Both the tag AND the release title
are `vX.Y.Z` (e.g. `v1.2.0`) — never the bare `X.Y.Z`. Every prior release (v0.1.0 … v1.2.0)
follows this. Create with `gh release create vX.Y.Z --title "vX.Y.Z" …`, then verify
`gh release view vX.Y.Z --json name --jq '.name'` prints `vX.Y.Z`; fix drift with
`gh release edit vX.Y.Z --title "vX.Y.Z"`.
