# -*- coding: utf-8 -*-
"""Clean-build-and-deploy the mod as a .wotmod into a WoT install (run with Python 2.7.18).

  python build/deploy_wotmod.py "D:/Games/World_of_Tanks_EU" 2.3.0.1
  python build/deploy_wotmod.py            # uses deploy.local.json
  python build/deploy_wotmod.py --clean-overlay   # also remove the gameface overlay

WoT 2.x loads mods ONLY from .wotmod packages in mods/<version>/. Loose files in
res_mods/<version>/ outrank .wotmod, so a stale loose copy SHADOWS the packaged
mod and the client silently ignores it. This script therefore ALWAYS cleans up
before deploying:
  1. removes old <id>_*.wotmod from mods/<version>/
  2. removes our loose leftovers from res_mods/<version>/ (mod_moe_calculator*.py + their
     .pyc siblings + the moe_calculator package) -- and nothing else (OpenWG's
     gui/unbound/res_map.json and any pre-existing __init__.pyc are left alone)
Then it builds a fresh .wotmod and copies it in. Restart the client afterwards.

The gameface hot-reload overlay (res_mods/<version>/gui/gameface/mods/14th_ua/,
planted by sync_gameface.py) also shadows the packaged JS/CSS, but is left in
place by default so the dev hot-reload loop keeps working. Deploy WARNS when it
is present; pass --clean-overlay to remove it for a clean packaged verify.
"""
from __future__ import print_function

import os
import sys
import glob
import json
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "build"))
import build_wotmod  # noqa: E402


def _resolve_args(argv):
    if len(argv) >= 3:
        return argv[1], argv[2]
    cfg = os.path.join(ROOT, "deploy.local.json")
    if os.path.exists(cfg):
        with open(cfg) as f:
            data = json.load(f)
        return data["wot_path"], data["version"]
    print('Usage: python build/deploy_wotmod.py "<wot_path>" <version> [--clean-overlay]')
    print("   or create deploy.local.json with wot_path + version")
    sys.exit(1)


def _abort_if_locked(err):
    if getattr(err, "errno", None) in (13, 32):  # EACCES / sharing violation
        print("\nERROR: a mod file is locked -- the WoT client is still running.")
        print("Close World of Tanks completely, then re-run this deploy.")
        sys.exit(2)
    raise err


def _clean(mods_dir, res_mods_dir, mod_id):
    # 1) old versions of OUR packaged mod. Match only version-numbered files
    # (mod_id + "_<digit>...") so we never delete a sibling dev mod such as
    # "<mod_id>_debug.wotmod".
    for f in glob.glob(os.path.join(mods_dir, mod_id + "_[0-9]*.wotmod")):
        try:
            os.remove(f)
        except OSError as e:
            _abort_if_locked(e)
        print("cleaned old package:", os.path.basename(f))
    # 2) our loose leftovers in res_mods (do NOT touch other files there). Remove
    # both the .py and its byte-compiled .pyc sibling -- a stale .pyc outranks the
    # packaged entry point just as a .py does (the installer deletes both too).
    mods_py = os.path.join(res_mods_dir, "scripts", "client", "gui", "mods")
    for stem in ("mod_moe_calculator", "mod_moe_calculator_debug"):
        for name in (stem + ".py", stem + ".pyc"):
            p = os.path.join(mods_py, name)
            if os.path.isfile(p):
                os.remove(p)
                print("cleaned loose:", name)
    pkg = os.path.join(res_mods_dir, "scripts", "client", "moe_calculator")
    if os.path.isdir(pkg):
        shutil.rmtree(pkg)
        print("cleaned loose package: moe_calculator")


def _overlay_dir(res_mods_dir):
    """The gameface hot-reload overlay dir (sync_gameface.py plants it here)."""
    return os.path.join(res_mods_dir, "gui", "gameface", "mods", "14th_ua")


def _handle_overlay(res_mods_dir, clean_overlay):
    """Warn about (or, with --clean-overlay, remove) the shadowing gameface overlay."""
    overlay = _overlay_dir(res_mods_dir)
    if not os.path.isdir(overlay):
        return
    if clean_overlay:
        shutil.rmtree(overlay)
        print("removed overlay: gui/gameface/mods/14th_ua")
    else:
        print("\nWARNING: gameface overlay present -- packaged JS/CSS is SHADOWED")
        print("  " + overlay)
        print("  Remove it (or re-run with --clean-overlay) to verify the packaged")
        print("  assets. Left in place so the sync_gameface.py hot-reload loop works.")


def main():
    clean_overlay = "--clean-overlay" in sys.argv[1:]
    argv = [a for a in sys.argv if a != "--clean-overlay"]
    wot_path, version = _resolve_args(argv)
    mods_dir = os.path.join(wot_path, "mods", version)
    res_mods_dir = os.path.join(wot_path, "res_mods", version)
    if not os.path.isdir(mods_dir):
        print("mods dir not found:", mods_dir)
        sys.exit(1)

    mod_id, mod_version = build_wotmod._read_meta()
    _clean(mods_dir, res_mods_dir, mod_id)

    build_wotmod.main()  # builds dist/<id>_<version>.wotmod

    built = os.path.join(ROOT, "dist", "{0}_{1}.wotmod".format(mod_id, mod_version))
    shutil.copy2(built, mods_dir)
    print("deployed:", os.path.join(mods_dir, os.path.basename(built)))
    _handle_overlay(res_mods_dir, clean_overlay)
    print("Restart the WoT client to load changes.")


if __name__ == "__main__":
    main()
