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
| `src/meta.xml` | `<version>0.1.0</version>` — **source of truth** |
| `src/res/scripts/client/gui/mods/mod_moe_calculator.py` | `MOD_VERSION = "0.1.0"` |
| `installer/moe_calculator-setup.iss` | `#define ModVersion "0.1.0"` + `#define ModWotmod "…_0.1.0.wotmod"` |
| `installer/build_installer.ps1` | `$ModWotmod = …com.14th_ua.moe_calculator_0.1.0.wotmod` |
| `INSTALL.md` | `MoECalculator-Setup-0.1.0.exe`, `…_0.1.0.wotmod` |
| `dist/INSTALL.txt` | prose `version 0.1.0` (gitignored build output; checked when present) |

- `README.md` uses `<version>` placeholders (no hard-coded number). `adapter/moe_data.py`'s
  `_AGENT` string embeds `0.1.0` cosmetically (**not** enforced).
- The **client** version `2.3.0.1` is deliberately excluded from the check (a `(?!\.\d)` lookahead skips the 4-part client version).

## build/ scripts

- **`build_wotmod.py`** — **Python 2.7 only** (asserts). Reads `meta.xml`, compiles `.py`→`.pyc`
  (drops `.py`, skips `__pycache__`), zips `meta.xml` + `res/` as **`ZIP_STORED`** →
  `dist/com.14th_ua.moe_calculator_<version>.wotmod`. Non-`.py` files (fonts/PNG/JSON) are copied verbatim.
- **`deploy_wotmod.py`** — Python 2.7. Cleans old `…_[0-9]*.wotmod` from `mods/<ver>/` + loose
  `res_mods` leftovers, calls `build_wotmod.main()`, copies in. Reads `deploy.local.json` if no args.
  `--clean-overlay` removes the hot-reload overlay. **Needs `WorldOfTanks.exe` closed** (`wgc` ok).
- **`build_moe_zip.py`** — any Python. Builds `dist/MoECalculator_<version>.zip` = bilingual
  `readme.txt` (from `installer/readme.moe.txt`, `{VERSION}` substituted, CRLF) + the mod `.wotmod`
  + all `installer/vendor/*.wotmod` under `mods/2.3.0.1/`. Manual upload to wgmods.net. Holds `CLIENT_VERSION="2.3.0.1"`.
- **`check_version.py`** — the version gate above. **`clean_dist.py`** — prunes non-current release artifacts from `dist/` (`--dry-run`).

## installer/

- **`moe_calculator-setup.iss`** — Inno Setup 6. Detects WoT root, resolves client version, installs
  to `mods\<version>\`, bundles OpenWG from `installer/vendor/` **only if absent**
  (`NeedOpenWg`, `uninsneveruninstall`), cleans old builds, WoT-running guard, GitHub
  Atom-feed self-update. Repo `drizzer14/moe-calculator`, base name `MoECalculator-Setup`.
- **`build_installer.ps1`** — preflights the built `.wotmod` + vendor dep, finds `ISCC.exe`, compiles → `dist/MoECalculator-Setup-<version>.exe`.
- **`readme.moe.txt`** — bilingual EN/UA readme for the wgmods zip. **`readme.wgmods.txt`** — stub (superseded). **`installer/vendor/`** — `net.openwg.gameface_1.1.6.wotmod`.

## Hot-reload (the split that bites)

- **Garage widget hot-reloads:** `<py3> tools\dev\sync_gameface.py "D:/Games/World_of_Tanks_EU" 2.3.0.1`
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

v0.1.0 assets are **built but not published**; the GitHub repo
`drizzer14/moe-calculator` must be created by the user, and the installer self-update needs a
real `vX.Y.Z` release carrying the `MoECalculator-Setup-<ver>.exe` asset before it works. Follow `wotmod-release` for the bump→tag→build→publish flow.
