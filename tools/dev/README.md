# Dev tools (WoT 2.3.0.1)

In-game introspection + the real dev loop for this mod. **Not shipped** with the mod.
See the harness skills `wotmod-build-deploy` and `wotmod-debug-repl` for the generic
pattern behind these scripts.

## Environment (this PC)
- WoT install: `D:/Games/World_of_Tanks_EU`, version **2.3.0.1**. OpenWG Gameface installed.
- **Python 2.7.18** at `C:\Python27\python.exe` — packaging only (compiles `.pyc`; bytecode is 2.7-locked).
- **Python 3.13** at `%LOCALAPPDATA%\Programs\Python\Python313\python.exe` — runs pytest + the REPL client.
- Git at `C:\Program Files\Git\cmd\git.exe`, `core.longpaths=true` (needed for decompiled clones).

## The dev loop (WoT 2.x loads ONLY `.wotmod`)
Loose `res_mods\<version>\scripts` does **not** load in 2.x, and `res_mods` outranks `.wotmod`
(a stale loose copy SHADOWS the package → client ignores the mod). So always:

```
# 1) close the WoT client (file locks); then build+deploy the real mod:
& "C:\Python27\python.exe" build\deploy_wotmod.py "D:/Games/World_of_Tanks_EU" 2.3.0.1
# 2) relaunch the client. (OpenWG may auto-restart once when res_map changes.)
```
`deploy_wotmod.py` auto-cleans old `com.14th_ua.moe_calculator_[0-9]*.wotmod` and loose leftovers.

### Hot-reload loop for JS/CSS-only changes (NO relaunch)
`coui://gui/...` resolves through a merged FS where `res_mods/<version>/` outranks
the `.wotmod`, and the hangar sub-view re-fetches our assets each time its document
is rebuilt. So for **visual-only** (MoECalculator.js/.css) iteration:
```
# client may stay running:
& "<py3>" tools\dev\sync_gameface.py "D:/Games/World_of_Tanks_EU" 2.3.0.1
# then in-game: switch to another screen (e.g. Tech Tree) and back to the Garage.
```
This is ONLY for front-end assets. Python (mount/data) changes still need
build+deploy+relaunch. **Caveats:** after every `deploy_wotmod.py`, re-run
`sync_gameface.py` (else the stale overlay shadows the fresh package); and **remove
the overlay** (`res_mods\2.3.0.1\gui\gameface\mods\14th_ua\`) before a
clean ship-verification so you're testing the packaged assets.

Unit tests (engine-free domain layer, Python 3):
```
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" -m pytest -q   # expect green
```

## Debug REPL (live introspection)
`com.14th_ua.moe_calculator_debug.wotmod` runs a TCP REPL on **127.0.0.1:2224** in the client
(the sibling Garage Progress Bar's debug REPL owns **2223**, so both can run at once).
- Build/deploy it (client closed):
  `& "C:\Python27\python.exe" tools\dev\build_debug_wotmod.py "D:/Games/World_of_Tanks_EU" 2.3.0.1`
- Drive it from the host (client running, in Garage):
  `& "<py3>" tools\dev\repl_client.py "<expr>"` or `--file cmds.txt`
- One command per line; state shared only within one run → put interdependent
  commands in one `--file`. For multi-line code: write a `.py` and send
  `execfile(r'<abs path>')` as one command.
- Keep the debug package SLIM (only `mod_moe_calculator_debug.pyc`). If it also ships
  `moe_calculator`, it conflicts with the real mod and WoT ignores it.

### Handy REPL snippets
```python
# current vehicle -> snapshot -> model
from CurrentVehicle import g_currentVehicle
from moe_calculator.adapter import engine_adapter
from moe_calculator.domain.builder import build_model
m = build_model(engine_adapter.build_snapshot())
(m.mode, m.scale_min, m.scale_max, m.fill_vehicle, m.fill_free, len(m.ticks))

# force a refresh of the mounted widget
from moe_calculator.bridge import gameface_bridge as B
B.refresh()
```

## Decompiled source (re-clone as needed; not in repo)
Match the client's branch/region — use the branch matching your client's major
version (e.g. the `2.3.0.1` major line):
```
& $git clone --depth 1 --branch <major> --single-branch https://github.com/StranikS-Scan/WorldOfTanks-Decompiled.git wot-eu
```
(The repo's default branch is a different regional client — cross-check against
the live `res/packages/scripts.pkg` by listing module filenames.)
