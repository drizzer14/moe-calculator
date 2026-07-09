# -*- coding: utf-8 -*-
"""Single source for reading src/meta.xml (the canonical mod id + version).

Imported by the build scripts so meta.xml is parsed in exactly ONE place instead
of a hand-copied one-liner in each. check_version.py is the separate release-time
gate that asserts the version is mirrored across the other files.

Runs on Python 2.7 (release/packaging tooling) and 3.x (tests/CI).
"""
from __future__ import print_function

import os
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
META = os.path.join(ROOT, "src", "meta.xml")


def read_meta():
    """Return (mod_id, version) from src/meta.xml, both stripped."""
    root = ET.parse(META).getroot()
    return root.findtext("id").strip(), root.findtext("version").strip()


def read_version():
    """Return just the version string from src/meta.xml."""
    return read_meta()[1]
