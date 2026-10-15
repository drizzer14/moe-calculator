# -*- coding: utf-8 -*-
"""Guard that the bundled vendor .wotmod dependencies match their recorded origin/sha256.

`installer/vendor/MANIFEST.json` is the one place that records where each bundled vendor
.wotmod came from and what it is supposed to hash to. This fails loudly if a vendor file is
swapped without updating the manifest (or vice versa), so a supply-chain drift never ships
silently.
"""
import hashlib
import json
import os

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_VENDOR_DIR = os.path.join(_ROOT, "installer", "vendor")
_MANIFEST_PATH = os.path.join(_VENDOR_DIR, "MANIFEST.json")


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _manifest():
    with open(_MANIFEST_PATH, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def _vendor_wotmods():
    return sorted(f for f in os.listdir(_VENDOR_DIR) if f.endswith(".wotmod"))


def test_every_bundled_vendor_file_is_manifested_and_matches_hash():
    manifest = _manifest()
    mismatches = []
    for name in _vendor_wotmods():
        entry = manifest.get(name)
        if entry is None:
            mismatches.append("%s: present in installer/vendor/ but missing from MANIFEST.json" % name)
            continue
        actual = _sha256(os.path.join(_VENDOR_DIR, name))
        if actual != entry["sha256"]:
            mismatches.append("%s: sha256 mismatch (manifest %s, actual %s)"
                               % (name, entry["sha256"], actual))
    assert not mismatches, "\n".join(mismatches)


def test_mit_vendor_entry_ships_its_licence_text():
    mit = [n for n, e in _manifest().items() if e.get("licence", "").startswith("MIT")]
    assert mit
    # MIT requires the notice to travel with the copy: ship it and have the .iss install it.
    lic = os.path.join(_ROOT, "installer", "licenses", "openwg-gameface-LICENSE.txt")
    assert os.path.getsize(lic) > 0
    with open(os.path.join(_ROOT, "installer", "moe_calculator-setup.iss"), encoding="utf-8") as fh:
        assert "licenses\\openwg-gameface-LICENSE.txt" in fh.read()


def test_every_manifest_entry_has_a_bundled_file():
    manifest = _manifest()
    present = set(_vendor_wotmods())
    missing = [name for name in manifest if name not in present]
    assert not missing, "manifested but not bundled: %r" % missing
