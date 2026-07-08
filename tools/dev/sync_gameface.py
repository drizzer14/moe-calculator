# -*- coding: utf-8 -*-
"""Hot-reload helper: copy ONLY the Gameface front-end assets (MoECalculator.js
/ .css) into the client's res_mods overlay, so visual changes can be applied
WITHOUT relaunching the client.

WoT's `coui://gui/...` resolves through a merged virtual filesystem where
`res_mods/<version>/` outranks the packaged `.wotmod`. The hangar sub-view
document re-fetches our assets every time it's (re)built, so after a sync you
just switch to another screen and back to the garage and the new CSS/JS loads.

This is for VISUAL (JS/CSS) iteration only. Python changes (the mount logic in
the .wotmod) still require build + deploy + relaunch via deploy_wotmod.py.

Usage (any Python 3, client may stay running):
    python tools/dev/sync_gameface.py "D:/Games/World_of_Tanks_EU" 2.3.0.1

Note: this leaves a loose res_mods overlay in place. It only shadows the .wotmod's
COPY of the SAME assets (intended) -- it does NOT shadow the Python entry point,
so the mod keeps loading normally. Remove it before shipping / final verify if
you want to confirm the packaged assets render identically.
"""
import os
import shutil
import sys

REL = os.path.join("gui", "gameface", "mods", "14th_ua", "MoECalculator")
ASSETS = ("MoECalculator.js", "MoECalculator.css", "card_border.png",
          "tooltip_bg.png", "tooltip_divider.png", "MoEBattle.js",
          "MoEBattle.css", "MoEBattleView.html", "checker.png",
          # Battle-overlay font: ONE cut (weight 600), a bare sibling of the CSS
          # (Coherent @font-face only resolves bare-sibling src urls, not subdir-relative).
          # This window has NO in-session hot-reload (resources pin at launch) -- needs relaunch.
          "MoEBattle.ttf")


def main(argv):
    if len(argv) != 3:
        print("usage: sync_gameface.py <wot_install_dir> <version>")
        return 2
    install, version = argv[1], argv[2]
    here = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(here, "..", "..", "src", "res", REL)
    dst = os.path.join(install, "res_mods", version, REL)
    if not os.path.isdir(src):
        print("source assets not found: %s" % os.path.abspath(src))
        return 1
    if not os.path.isdir(os.path.join(install, "res_mods", version)):
        print("res_mods/%s not found under %s" % (version, install))
        return 1
    if not os.path.isdir(dst):
        os.makedirs(dst)
    for name in ASSETS:
        shutil.copy2(os.path.join(src, name), os.path.join(dst, name))
        print("synced: %s" % os.path.join(dst, name))
    print("Done. In-game: switch screen (e.g. to Tech Tree) and back to reload.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
