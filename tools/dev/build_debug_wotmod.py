# -*- coding: utf-8 -*-
"""Build + deploy the DEV debug-REPL .wotmod (run with Python 2.7.18).

  python tools/dev/build_debug_wotmod.py "D:/Games/World_of_Tanks_EU" 2.3.0.1

Produces com.14th_ua.moe_calculator_debug.wotmod (slim: just mod_moe_calculator_debug.pyc) and
drops it in mods/<version>/. Keep it slim so it never conflicts with the real
mod's moe_calculator package. Requires the client to be CLOSED. Restart after.
"""
from __future__ import print_function
import os
import sys
import zipfile
import py_compile
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
META = """<root>
    <id>com.14th_ua.moe_calculator_debug</id>
    <version>0.0.1</version>
    <name>14th_ua's MoE Calculator Debug REPL</name>
    <description>DEV-ONLY: TCP REPL on 127.0.0.1:2224. Not for distribution.</description>
</root>
"""


def _check_python():
    if sys.version_info[0] != 2 or sys.version_info[1] != 7:
        sys.exit("ERROR: build_debug_wotmod must run under Python 2.7 (got {0}.{1}). "
                 "The game executes the .pyc and bytecode is version-locked, so a "
                 "debug mod built under any other version will NOT load (symptom: "
                 "connection refused on the REPL port 2224). Re-run with "
                 "C:\\Python27\\python.exe."
                 .format(sys.version_info[0], sys.version_info[1]))


def _abort_if_locked(err):
    """Mirror build/deploy_wotmod.py: a locked output file means the WoT client is still running
    (it holds mods/<version>/*.wotmod open). Print the same friendly 'close the client' message
    instead of dumping a raw OSError traceback."""
    if getattr(err, "errno", None) in (13, 32):  # EACCES / sharing violation
        print("\nERROR: the debug .wotmod is locked -- the WoT client is still running.")
        print("Close World of Tanks completely, then re-run this build.")
        sys.exit(2)
    raise err


def main():
    _check_python()
    if len(sys.argv) < 3:
        print('Usage: python tools/dev/build_debug_wotmod.py "<wot_path>" <version>')
        sys.exit(1)
    wot_path, version = sys.argv[1], sys.argv[2]
    out = os.path.join(wot_path, "mods", version, "com.14th_ua.moe_calculator_debug.wotmod")

    stage = os.path.join(HERE, "_stage_debug")
    mods_dir = os.path.join(stage, "res", "scripts", "client", "gui", "mods")
    if os.path.isdir(stage):
        shutil.rmtree(stage)
    os.makedirs(mods_dir)
    with open(os.path.join(stage, "meta.xml"), "w") as f:
        f.write(META)
    src = os.path.join(HERE, "mod_moe_calculator_debug.py")
    pyc = os.path.join(mods_dir, "mod_moe_calculator_debug.pyc")
    py_compile.compile(src, cfile=pyc, doraise=True)

    try:
        if os.path.exists(out):
            os.remove(out)
        zf = zipfile.ZipFile(out, "w", zipfile.ZIP_STORED)
        zf.write(os.path.join(stage, "meta.xml"), "meta.xml")
        zf.write(pyc, "res/scripts/client/gui/mods/mod_moe_calculator_debug.pyc")
        zf.close()
    except (OSError, IOError) as e:
        shutil.rmtree(stage, ignore_errors=True)
        _abort_if_locked(e)
    shutil.rmtree(stage)
    print("built + deployed:", out)
    print("Restart the WoT client to load it.")


if __name__ == "__main__":
    main()
