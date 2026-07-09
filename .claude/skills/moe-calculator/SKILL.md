---
name: moe-calculator
description: Use when working anywhere in the 14th_ua MoE Calculator repo and you need orientation — the mod's identity, versions, dependencies, the src/ tree, the shared cross-feature modules, the MoE data source, or the exact dev/deploy/test/REPL commands. Start here, then branch to moe-garage, moe-battle, or moe-build-release.
---

# 14th_ua's MoE Calculator — project map

A World of Tanks **Garage + in-battle** Marks-of-Excellence mod. This skill is the
orientation; the concrete patterns live in the harness skill `wotmod-basics`. The two
features and the build each have their own project skill:

- **`moe-garage`** — the hangar percentile-bar widget, end-to-end.
- **`moe-battle`** — the in-battle live-MoE overlay, end-to-end.
- **`moe-build-release`** — packaging, deploy, version files, dev loop, release.

## Identity (facts)

- **Mod id:** `com.14th_ua.moe_calculator` (`src/meta.xml` is the canonical version, currently **0.1.0**).
- **Client:** WoT **EU 2.3.0.1**. Runtime **Python 2.7** (BigWorld); tests on **Python 3.13**.
- **Hard dep:** OpenWG GameFace ≥ 1.1.6 (`import openwg_gameface` raises if absent). No optional deps.
- **MoE data source:** `https://tomato.gg/moe/EU` — per-tank combined-damage thresholds `{1,2,3,100}` keyed by intCD (Tiger I id 1073). Fetched once/session on a worker thread in `adapter/moe_data.py`.

## The tree

```
src/res/scripts/client/
  gui/mods/mod_moe_calculator.py     entry: _install() garage + _install_battle() overlay
  moe_calculator/
    domain/     engine-free, pytest-able (NO game imports)
      constants.py        wire contract: MARK_PERCENTS=(65,85,95), EWMA, battle anchors
      types.py builder.py                garage data + build_model
      battle_types.py battle_builder.py  battle data + CD/EWMA/percent math
      positioning.py                     overlay anchor + damage-log-collapse predicate
      baseline_cache.py                  garage→battle career-baseline bridge
    adapter/    the ONLY read-side layer touching live game symbols (fail-soft via _safe)
      engine_adapter.py   garage dossier read      battle_adapter.py  in-battle efficiency read
      moe_data.py         tomato.gg fetch/parse     format.py          pure formatters
      i18n.py             localized label bundle
    bridge/     marshals model → Wulf ViewModels (PC-only)
      gameface_bridge.py  garage inject+push        battle_bridge.py   battle lifecycle+push
      battle_view.py      registered window host    view_models.py     MoEVM/MarkTickVM/BattleMoEVM
      wulf_args.py        (reverse-channel helpers; unused — v1 is read-only)
    _compat.py            LOG_* shim + _safe/_safe_int
src/res/gui/gameface/mods/14th_ua/MoECalculator/   the two front-ends + assets (see moe-garage / moe-battle)
src/res/mods/configs/res_map/MoEBattleView.json    registers the in-battle view
```

## Shared (cross-feature) modules

`domain/constants.py` (mark percents, EWMA, anchors), `adapter/moe_data.py` (threshold
table), `adapter/format.py` (`thousands`/`percent`/`signed_percent`/`mark_icon_url`),
`adapter/i18n.py` (label bundle), `domain/baseline_cache.py` (career baseline keyed by
intCD, bridging garage read → battle read), `_compat.py`. Everything else is feature-specific.

## Dev quickref

Deploy yourself — never ask the user to run these (run the commands directly via the shell):

| Task | Command |
|---|---|
| Package + deploy | `C:\Python27\python.exe build\deploy_wotmod.py "D:/Games/World_of_Tanks_EU" 2.3.0.1` (reads `deploy.local.json` if no args) |
| Garage hot-reload | `<py3> tools\dev\sync_gameface.py "D:/Games/World_of_Tanks_EU" 2.3.0.1` (front-end only; **battle window can't hot-reload**) |
| Tests | `<py3> -m pytest -q` |
| Live REPL | `<py3> tools\dev\repl_client.py "<expr>"` — needs `com.14th_ua.moe_calculator_debug.wotmod` on TCP **:2224** |

- WoT install: `D:/Games/World_of_Tanks_EU`. Decompiled client source: `C:\Users\Dmytro Vasylkivskyi\wot-eu\source\res\scripts\client\`.
- Sibling repo with portable code (Ctrl+drag): `C:\Users\Dmytro Vasylkivskyi\wgmod-research-progress`.
- **Deploy needs `WorldOfTanks.exe` closed** (file locks); the `wgc` launcher may stay open.
- Backlog + research notes live in `TASKS/` (`TASKS/shipped/` = archived). Planner role: see `wotmod-planner`.
