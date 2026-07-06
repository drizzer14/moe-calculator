# -*- coding: utf-8 -*-
"""Assert the mod version is consistent everywhere.

  python build/check_version.py

`src/meta.xml` <version> is the source of truth. This scans the repo for every
version reference that must track it and fails (exit 1) on any mismatch, printing
each offending file:line. It exists because the version is hand-edited in several
places at release time (see the wotmod-release skill) and drift slips through.

To avoid false positives on the *other* version numbers in the repo (the target
client 2.3.0.1, bundled ModsSettingsAPI 1.7.0 / OpenWG GameFace
1.1.6, etc.) this matches only patterns that unambiguously carry THIS
mod's version:

  * com.14th_ua.moe_calculator_<v>.wotmod          (the packaged filename)
  * MoECalculator-Setup-<v>.exe   (the installer filename)
  * MOD_VERSION = "<v>"            (mod_moe_calculator.py)
  * #define ModVersion "<v>"       (the .iss installer script)
  * version <v>                    (prose header, e.g. dist/INSTALL.txt)

The last (prose) pattern has a negative lookahead so it matches THIS mod's 3-part
version only, never the 4-part client version ("version 2.3.0.1").

New references written in any of these forms are picked up automatically. On top of
that, a small REQUIRED list names files that must carry at least one reference, so a
file silently LOSING its version reference also fails the check.

The hand-bumped consumer readme (dist/INSTALL.txt) lives under gitignored dist/,
which is otherwise skipped; it is scanned explicitly when present.

Runs on Python 2.7 or 3.x (release tooling is 2.7; CI is 3.13).
"""
from __future__ import print_function

import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
META = os.path.join(ROOT, "src", "meta.xml")

# Directories not worth scanning (build output, VCS, vendored binaries, editor cfg).
_SKIP_DIRS = {".git", "dist", "__pycache__", "node_modules", ".idea", ".vscode",
              "vendor", "assets"}
# Only these extensions hold version references.
_SCAN_EXT = (".md", ".py", ".xml", ".iss", ".ps1", ".txt")

# Under a _SKIP_DIRS folder but scanned anyway (hand-bumped, drift-prone). Relative
# to ROOT; skipped silently when absent (dist/ is gitignored build output).
_EXTRA_FILES = ("dist/INSTALL.txt",)

# Each pattern captures a semver in group 1 that must equal the meta version.
# The mod id is matched via re.escape so any dots in it stay literal. The prose
# "version <v>" pattern uses (?!\.\d) so it matches this mod's 3-part version but
# never the 4-part client version ("version 2.3.0.1").
_PATTERNS = [
    re.compile(re.escape("com.14th_ua.moe_calculator") + r"_(\d+\.\d+\.\d+)\.wotmod"),
    re.compile(re.escape("MoECalculator") + r"-Setup-(\d+\.\d+\.\d+)\.exe"),
    re.compile(r'MOD_VERSION\s*=\s*"(\d+\.\d+\.\d+)"'),
    re.compile(r'#define\s+ModVersion\s+"(\d+\.\d+\.\d+)"'),
    re.compile(r"version\s+(\d+\.\d+\.\d+)(?!\.\d)"),
]

# Files that MUST carry at least one version reference. Catches a file silently
# LOSING its reference (which would otherwise pass). Paths are ROOT-relative,
# forward-slashed. Entries under dist/ are checked only when the file exists
# (gitignored build output). Add your own consumer docs (INSTALL.md, etc.) here
# once they exist and carry a version reference.
_REQUIRED = (
    "src/res/scripts/client/gui/mods/mod_moe_calculator.py",
    "installer/moe_calculator-setup.iss",
    "installer/build_installer.ps1",
    "dist/INSTALL.txt",
)


def _meta_version():
    return ET.parse(META).getroot().findtext("version").strip()


def _iter_files():
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for name in files:
            if name.endswith(_SCAN_EXT):
                yield os.path.join(dirpath, name)
    # Files under an otherwise-skipped dir that we still want checked.
    for rel in _EXTRA_FILES:
        path = os.path.join(ROOT, rel.replace("/", os.sep))
        if os.path.isfile(path):
            yield path


def main():
    expected = _meta_version()
    mismatches = []
    counts = {}  # rel path -> number of version references found
    found_any = False
    for path in _iter_files():
        try:
            with open(path, "rb") as fh:
                text = fh.read().decode("utf-8", "replace")
        except (IOError, OSError):
            continue
        rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
        for lineno, line in enumerate(text.splitlines(), 1):
            for pat in _PATTERNS:
                for m in pat.finditer(line):
                    found_any = True
                    counts[rel] = counts.get(rel, 0) + 1
                    if m.group(1) != expected:
                        mismatches.append((rel, lineno, m.group(1), line.strip()))

    # A required file that carries NO reference (e.g. an edit dropped it silently).
    # dist/INSTALL.txt is only required when it exists (gitignored build output).
    missing = [rel for rel in _REQUIRED
               if not counts.get(rel)
               and (not rel.startswith("dist/")
                    or os.path.isfile(os.path.join(ROOT, rel.replace("/", os.sep))))]

    if mismatches:
        print("Version mismatch (src/meta.xml says %s):" % expected)
        for rel, lineno, got, line in mismatches:
            print("  %s:%d  found %s  ->  %s" % (rel, lineno, got, line))
        return 1
    if missing:
        print("Missing version reference (src/meta.xml says %s) in required files:"
              % expected)
        for rel in missing:
            print("  %s  (expected at least one %s reference)" % (rel, expected))
        return 1
    if not found_any:
        print("WARNING: no version references matched any pattern -- "
              "check_version.py may be stale.")
        return 1
    print("OK: all version references match src/meta.xml (%s)." % expected)
    return 0


if __name__ == "__main__":
    sys.exit(main())
