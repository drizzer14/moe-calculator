# -*- coding: utf-8 -*-
"""Static guard on the Inno Setup installer's vendor-dependency check
(installer/*.iss): every bundled vendor .wotmod must be gated by the
VERSION-aware NeedVendor Check (skip only when a same-or-newer copy of that
package id is installed) and followed by PurgeOlderVendor (delete the older
copies). A presence-only check (any file matching a mask counts) let a dead
old build copied into mods\\<version>\\ block the bundled one.

Same file in every 14th_ua installer repo. Reads the .iss text -- no Inno
Setup compiler needed.
"""
import glob
import os
import re

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_VENDOR_IDS = ("net.openwg.gameface", "aslain.modmenu", "me.poliroid.modslistapi")


def _iss_text():
    paths = glob.glob(os.path.join(_ROOT, "installer", "*.iss"))
    assert len(paths) == 1, "expected exactly one installer .iss, got %r" % paths
    with open(paths[0], "r", encoding="utf-8") as fh:
        return fh.read()


def _defines(text):
    for inc in re.findall(r'^#include\s+"([^"]+)"', text, re.MULTILINE):
        path = os.path.join(_ROOT, "installer", inc)
        if os.path.exists(path):  # e.g. a gathered payload manifest
            with open(path, "r", encoding="utf-8") as fh:
                text += "\n" + fh.read()
    return dict(re.findall(r'^#define\s+(\w+)\s+"([^"]*)"', text, re.MULTILINE))


def _vendor_wotmod_lines(text):
    """[Files] Source lines that ship a bundled vendor .wotmod."""
    files = re.search(r"^\[Files\]\s*$(.*?)^\[", text, re.MULTILINE | re.DOTALL)
    assert files, "no [Files] section"
    return [ln for ln in files.group(1).splitlines()
            if ln.startswith("Source:") and "uninsneveruninstall" in ln
            and re.search(r'Source:\s*"[^"]*vendor\\[^"]*"', ln)
            and not re.search(r'Source:\s*"[^"]*\.txt"', ln)]


def test_every_bundled_vendor_wotmod_is_version_checked():
    lines = _vendor_wotmod_lines(_iss_text())
    assert lines, "no bundled vendor .wotmod entries found in [Files]"
    for ln in lines:
        m = re.search(r'Source:\s*"[^"]*\{#(\w+)\}"', ln)
        assert m, "vendor source is not a #define file name: %s" % ln
        define = m.group(1)
        assert "Check: NeedVendor('{#%s}')" % define in ln, (
            "vendor entry is not gated by the version-aware NeedVendor check: %s" % ln)
        assert "AfterInstall: PurgeOlderVendor('{#%s}')" % define in ln, (
            "vendor entry does not purge older copies after install: %s" % ln)


def test_bundled_vendor_defines_are_id_underscore_version():
    text = _iss_text()
    defines = _defines(text)
    names = [re.search(r"\{#(\w+)\}", ln).group(1) for ln in _vendor_wotmod_lines(text)]
    for name in names:
        value = defines.get(name)
        if value is None:
            continue  # #include'd manifest not gathered yet
        assert re.match(r"^(%s)_\d+(\.\d+)*\.wotmod$" % "|".join(map(re.escape, _VENDOR_IDS)),
                        value), "%s=%r is not <vendor id>_<dotted version>.wotmod" % (name, value)


def test_code_compares_versions_not_presence():
    text = _iss_text()
    code = text[text.index("[Code]"):]
    for fn in ("function CompareDottedVer", "function WotmodVer", "function NeedVendor",
               "procedure PurgeOlderVendor"):
        assert fn in code, "%s missing from [Code]" % fn
    for vid in _VENDOR_IDS:
        assert vid + "*" not in code, (
            "presence-only mask %s* is back in [Code]; use NeedVendor" % vid)
