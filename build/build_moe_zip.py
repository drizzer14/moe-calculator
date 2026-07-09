# -*- coding: utf-8 -*-
"""
Build the wgmods.net distribution .zip: the mod + its dependency .wotmods + a
bilingual readme.txt, laid out under mods/<client>/ so the player extracts it
straight into their World of Tanks folder.

  python build/build_moe_zip.py

This is the extra deliverable for the wgmods.net channel; the GitHub release is
separate (Setup .exe + bare .wotmod). The built zip is UPLOADED TO wgmods.net
MANUALLY -- it is not attached to the GitHub release.

Prereqs:
  * The mod .wotmod must already be built into dist/ (build_wotmod.py, Py 2.7).
  * The dependency payloads must be present under installer/vendor/.
Runs on ANY Python (2.7 or 3.x): it only copies/zips already-built files, it
never compiles bytecode, so the 2.7-vs-3 rule does not apply here.

Output: dist/MoECalculator_<version>.zip
    readme.txt                                              (bilingual EN + UA)
    mods/<client>/com.14th_ua.moe_calculator_<version>.wotmod
    mods/<client>/<each installer/vendor/*.wotmod>          (bundled deps)
"""
from __future__ import print_function

import os
import glob
import zipfile

import meta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
VENDOR = os.path.join(ROOT, "installer", "vendor")
README_TEMPLATE = os.path.join(ROOT, "installer", "readme.moe.txt")

# The target client version -- the mods/<CLIENT>/ folder inside the zip, so the
# player can extract straight into <World of Tanks>\. Mirrors the version folder
# WoT loads mods from; must track the supported client (see CLAUDE.md).
CLIENT_VERSION = "2.3.0.1"


def main():
    mod_id, version = meta.read_meta()

    wotmod = os.path.join(DIST, "{0}_{1}.wotmod".format(mod_id, version))
    if not os.path.isfile(wotmod):
        raise SystemExit(
            "Mod package not found: {0}\nBuild it first:\n"
            "    & \"C:\\Python27\\python.exe\" build\\build_wotmod.py".format(wotmod))

    deps = sorted(glob.glob(os.path.join(VENDOR, "*.wotmod")))
    if not deps:
        raise SystemExit("No dependency .wotmods found under {0}".format(VENDOR))

    if not os.path.isfile(README_TEMPLATE):
        raise SystemExit("Readme template not found: {0}".format(README_TEMPLATE))
    with open(README_TEMPLATE, "rb") as fh:
        readme = fh.read().decode("utf-8").replace(u"{VERSION}", version)
    # readme.txt is opened on Windows -- normalise to CRLF so Notepad renders it.
    readme = readme.replace(u"\r\n", u"\n").replace(u"\n", u"\r\n")

    out_path = os.path.join(DIST, "MoECalculator_{0}.zip".format(version))
    if os.path.exists(out_path):
        os.remove(out_path)

    mods_prefix = "mods/{0}/".format(CLIENT_VERSION)
    payloads = [wotmod] + deps
    # Plain distribution zip (NOT a .wotmod), so compression is fine here -- the
    # WoT "no compression" rule only applies to .wotmod archives themselves.
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("readme.txt", readme.encode("utf-8"))
        for src in payloads:
            zf.write(src, mods_prefix + os.path.basename(src))

    print("Built: {0}".format(out_path))
    print("  readme.txt")
    for src in payloads:
        print("  {0}{1}".format(mods_prefix, os.path.basename(src)))


if __name__ == "__main__":
    main()
