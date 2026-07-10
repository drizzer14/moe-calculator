# -*- coding: utf-8 -*-
"""
Build a distributable .wotmod package from src/.

  python build/build_wotmod.py

What it does:
  1. Reads <id> and <version> from src/meta.xml.
  2. Compiles every .py under src/res/ to .pyc bytecode. moe_calculator/build_config.py is
     compiled from a SUBSTITUTED copy so its WG_APPLICATION_ID carries the secret read from the
     gitignored .env (the repo file, an empty placeholder, is never mutated).
  3. Zips meta.xml + res/ (with .pyc, NOT .py) into dist/<id>_<version>.wotmod
     using ZIP_STORED (no compression) — WoT rejects compressed archives.

There is a single build: MoE thresholds come from the official Wargaming API (adapter/
moe_wgapi), so the GitHub and WGMods channels ship the identical .wotmod. The API
application_id is injected from .env at build time (copy .env.example -> .env).

IMPORTANT: run this with **Python 2.7.18**. The game executes the .pyc, and
bytecode is tied to the Python version (magic number). Compiling under Python 3
produces bytecode the WoT client cannot load. OS does not matter — 2.7 .pyc is
portable across macOS/Windows/Linux — only the Python *version* matters.
"""
from __future__ import print_function

import os
import re
import sys
import shutil
import zipfile
import tempfile
import py_compile

import meta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
RES = os.path.join(SRC, "res")
META = os.path.join(SRC, "meta.xml")
DIST = os.path.join(ROOT, "dist")

# The WG API application_id is a secret injected at build time: the repo's build_config.py
# ships an empty WG_APPLICATION_ID placeholder, and we compile a SUBSTITUTED copy carrying the
# real id (read from the gitignored .env) so the secret lives only in the built .wotmod, never
# in source control. See moe_calculator/build_config.py and .env.example.
BUILD_CONFIG = os.path.join(RES, "scripts", "client", "moe_calculator", "build_config.py")
_APP_ID_RX = re.compile(r'WG_APPLICATION_ID\s*=\s*"[^"]*"')
ENV_FILE = os.path.join(ROOT, ".env")

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


def _read_app_id():
    """Read WG_APPLICATION_ID from the gitignored .env (KEY=VALUE lines, '#' comments). Returns
    "" if the file or key is absent -- the build then warns and ships no id (fetch disabled)."""
    try:
        with open(ENV_FILE, "rb") as fh:
            text = fh.read().decode("utf-8")
    except (IOError, OSError):
        return ""
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() == "WG_APPLICATION_ID":
            return value.strip().strip('"').strip("'")
    return ""


def _compile_py(src_file, pyc, app_id):
    """Compile one .py -> .pyc (normalized for reproducible builds). For build_config.py, compile
    a SUBSTITUTED temp copy (WG_APPLICATION_ID set to `app_id`) instead of the repo file, so the
    packaged bytecode carries the injected secret without mutating the working tree."""
    if os.path.abspath(src_file) == os.path.abspath(BUILD_CONFIG):
        with open(src_file, "rb") as fh:
            text = fh.read().decode("utf-8")
        text, n = _APP_ID_RX.subn('WG_APPLICATION_ID = "%s"' % app_id, text)
        if n != 1:
            raise SystemExit("ERROR: could not substitute WG_APPLICATION_ID in {0} "
                             "(matched {1} times).".format(BUILD_CONFIG, n))
        tmp = tempfile.NamedTemporaryFile(suffix=".py", delete=False)
        try:
            tmp.write(text.encode("utf-8"))
            tmp.close()
            py_compile.compile(tmp.name, cfile=pyc, doraise=True)
        finally:
            os.remove(tmp.name)
    else:
        py_compile.compile(src_file, cfile=pyc, doraise=True)
    _normalize_pyc(pyc)


def _compile_tree(src_root, out_root, app_id):
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
                _compile_py(src_file, pyc, app_id)
            elif name.endswith(".pyc"):
                continue  # skip stray/foreign bytecode; we compile fresh from .py
            else:
                shutil.copy2(src_file, os.path.join(target_dir, name))


def main():
    """Build the single .wotmod (thresholds come from the WG API at runtime; the API
    application_id is injected from .env into build_config.py)."""
    _check_python()
    app_id = _read_app_id()
    if not app_id:
        print("WARNING: no WG_APPLICATION_ID in .env -- the packaged mod will NOT fetch MoE\n"
              "         thresholds (bar shows ticks only). Copy .env.example to .env and set it.")
    mod_id, version = meta.read_meta()

    build_dir = os.path.join(DIST, "_build")
    if os.path.isdir(build_dir):
        shutil.rmtree(build_dir)
    os.makedirs(build_dir)

    # meta.xml at archive root
    shutil.copy2(META, os.path.join(build_dir, "meta.xml"))
    # compiled res/ tree (build_config.py's WG_APPLICATION_ID substituted to the .env secret)
    _compile_tree(RES, os.path.join(build_dir, "res"), app_id)

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
