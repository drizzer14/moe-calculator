# -*- coding: utf-8 -*-
"""
Build a distributable .wotmod package from src/.

  python build/build_wotmod.py

What it does:
  1. Reads <id> and <version> from src/meta.xml.
  2. Compiles every .py under src/res/ to .pyc bytecode.
  3. Zips meta.xml + res/ (with .pyc, NOT .py) into dist/<id>_<version>.wotmod
     using ZIP_STORED (no compression) — WoT rejects compressed archives.

IMPORTANT: run this with **Python 2.7.18**. The game executes the .pyc, and
bytecode is tied to the Python version (magic number). Compiling under Python 3
produces bytecode the WoT client cannot load. OS does not matter — 2.7 .pyc is
portable across macOS/Windows/Linux — only the Python *version* matters.
"""
from __future__ import print_function

import os
import sys
import shutil
import zipfile
import py_compile

import meta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
RES = os.path.join(SRC, "res")
META = os.path.join(SRC, "meta.xml")
DIST = os.path.join(ROOT, "dist")

# Fixed zip-entry timestamp (the earliest a zip can represent) so identical
# source produces a byte-identical .wotmod -- lets a release verify diff/checksum
# the artifact instead of eyeballing it. See _normalize_pyc for the bytecode half.
_FIXED_DATE = (1980, 1, 1, 0, 0, 0)


def _check_python():
    if sys.version_info[0] != 2 or sys.version_info[1] != 7:
        sys.exit("ERROR: build_wotmod must run under Python 2.7 (got {0}.{1}). "
                 "The game executes the .pyc and bytecode is version-locked, so a "
                 "package built under any other version will NOT load in the WoT "
                 "client. Re-run with C:\\Python27\\python.exe."
                 .format(sys.version_info[0], sys.version_info[1]))


def _normalize_pyc(pyc):
    """Zero the mtime field in the .pyc header for reproducible builds.

    A 2.7 .pyc header is magic(4) + source-mtime(4); py_compile stamps the .py's
    mtime, so identical source otherwise yields a byte-different .pyc every build.
    Only the .pyc ships (the .py is dropped), so this timestamp is never consulted
    at load time -- zeroing it is safe and makes the package deterministic.
    """
    with open(pyc, "r+b") as fh:
        fh.seek(4)
        fh.write(b"\x00\x00\x00\x00")


def _compile_tree(src_root, out_root):
    """Copy res/ to out_root, compiling .py -> .pyc and dropping the .py."""
    for dirpath, dirs, files in os.walk(src_root):
        # Never ship dev/build artifacts: Python 3 __pycache__ from pytest, etc.
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        rel = os.path.relpath(dirpath, src_root)
        target_dir = os.path.join(out_root, rel) if rel != "." else out_root
        if not os.path.isdir(target_dir):
            os.makedirs(target_dir)
        for name in files:
            src_file = os.path.join(dirpath, name)
            if name.endswith(".py"):
                pyc = os.path.join(target_dir, name + "c")  # foo.py -> foo.pyc
                py_compile.compile(src_file, cfile=pyc, doraise=True)
                _normalize_pyc(pyc)
            elif name.endswith(".pyc"):
                continue  # skip stray/foreign bytecode; we compile fresh from .py
            else:
                shutil.copy2(src_file, os.path.join(target_dir, name))


def main():
    _check_python()
    mod_id, version = meta.read_meta()

    build_dir = os.path.join(DIST, "_build")
    if os.path.isdir(build_dir):
        shutil.rmtree(build_dir)
    os.makedirs(build_dir)

    # meta.xml at archive root
    shutil.copy2(META, os.path.join(build_dir, "meta.xml"))
    # compiled res/ tree
    _compile_tree(RES, os.path.join(build_dir, "res"))

    if not os.path.isdir(DIST):
        os.makedirs(DIST)
    out_path = os.path.join(DIST, "{0}_{1}.wotmod".format(mod_id, version))
    if os.path.exists(out_path):
        os.remove(out_path)

    # Gather entries in a stable (sorted) order -- os.walk order is filesystem-
    # dependent, and a reproducible archive needs a fixed member sequence.
    entries = []
    for dirpath, _dirs, files in os.walk(build_dir):
        for name in files:
            full = os.path.join(dirpath, name)
            arc = os.path.relpath(full, build_dir).replace(os.sep, "/")
            entries.append((arc, full))
    entries.sort()

    # ZIP_STORED = no compression (required by WoT). Fixed per-entry timestamps
    # (via ZipInfo) drop the last source of nondeterminism, so identical source
    # yields a byte-identical .wotmod.
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_STORED) as zf:
        for arc, full in entries:
            with open(full, "rb") as fh:
                data = fh.read()
            info = zipfile.ZipInfo(arc, date_time=_FIXED_DATE)
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16  # -rw-r--r--
            zf.writestr(info, data)

    shutil.rmtree(build_dir)
    print("Built: {0}".format(out_path))


if __name__ == "__main__":
    main()
