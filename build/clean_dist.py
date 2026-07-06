# -*- coding: utf-8 -*-
"""
Prune old release artifacts from dist/, keeping only the current version.

  python build/clean_dist.py            # delete every dist artifact whose
                                        # version != src/meta.xml <version>
  python build/clean_dist.py --dry-run  # list what WOULD be removed, delete nothing

dist/ is gitignored local scratch; the full release history lives on the GitHub
Releases page, so there is no reason to hoard superseded binaries here. This is a
release step (see the wotmod-release skill): tidy dist/ so it holds exactly one
release's worth of artifacts.

Runs on ANY Python (2.7 or 3.x): pure filesystem + XML, no bytecode. It only
touches the canonical release artifact families and never deletes the current
version's files or the unversioned INSTALL.txt:
  * <id>_<ver>.wotmod                  (build_wotmod.py)
  * MoECalculator-Setup-<ver>.exe     (build_installer.ps1)
  * MoECalculator_<ver>.zip           (consumer / wgmods bundle zip, hand-assembled)
Anything else in dist/ (INSTALL.txt, the transient _build/ dir, unrelated files)
is left untouched.
"""
from __future__ import print_function

import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
META = os.path.join(ROOT, "src", "meta.xml")
DIST = os.path.join(ROOT, "dist")


def _read_meta():
    root = ET.parse(META).getroot()
    return root.findtext("id").strip(), root.findtext("version").strip()


def _keep_names(mod_id, version):
    """The exact filenames the current version legitimately owns (never deleted)."""
    return set([
        "{0}_{1}.wotmod".format(mod_id, version),
        "MoECalculator-Setup-{0}.exe".format(version),
        "MoECalculator_{0}.zip".format(version),
    ])


def _artifact_patterns(mod_id):
    """Filenames that are versioned release artifacts of ANY version."""
    return [
        re.compile(r"^" + re.escape(mod_id) + r"_.+\.wotmod$"),
        re.compile(r"^" + re.escape("MoECalculator") + r"-Setup-.+\.exe$"),
        re.compile(r"^" + re.escape("MoECalculator") + r"_.+\.zip$"),
    ]


def clean(dry_run=False):
    mod_id, version = _read_meta()
    if not os.path.isdir(DIST):
        print("dist/ does not exist -- nothing to clean.")
        return []

    keep = _keep_names(mod_id, version)
    patterns = _artifact_patterns(mod_id)

    removed = []
    for name in sorted(os.listdir(DIST)):
        path = os.path.join(DIST, name)
        if not os.path.isfile(path):
            continue  # skip _build/ and other dirs
        if name in keep:
            continue
        if not any(p.match(name) for p in patterns):
            continue  # not a release artifact (e.g. INSTALL.txt) -- leave it
        if dry_run:
            print("would remove:", name)
        else:
            os.remove(path)
            print("removed:", name)
        removed.append(name)

    if not removed:
        print("dist/ already clean -- only v{0} artifacts present.".format(version))
    else:
        verb = "would remove" if dry_run else "removed"
        print("{0} {1} old artifact(s); kept v{2}.".format(verb, len(removed), version))
    return removed


def main():
    dry_run = "--dry-run" in sys.argv[1:]
    clean(dry_run=dry_run)


if __name__ == "__main__":
    main()
