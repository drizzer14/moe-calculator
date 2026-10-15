# -*- coding: utf-8 -*-
"""R.mods node is namespaced (no cross-mod collision) and no dead res_map/ModDynAccessor text lingers."""
import os
import re

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_BRIDGE = os.path.join(_ROOT, "src", "res", "scripts", "client", "moe_calculator", "bridge")
_DOC_FILES = ("README.md", "INSTALL.md", os.path.join("installer", "readme.moe.txt"))
_EXTS = (".py", ".js", ".css", ".json", ".md", ".txt", ".html")


def test_res_node_is_author_prefixed():
    with open(os.path.join(_BRIDGE, "bar_window.py"), encoding="utf-8") as fh:
        node = re.search(r'^_RES_NODE = "([^"]+)"', fh.read(), re.M).group(1)
    assert node.startswith("com_14th_ua_")
    with open(os.path.join(_ROOT, "src", "res", "gui", "gen_resources",
                           "com.14th_ua.moe_calculator.json"), encoding="utf-8") as fh:
        assert fh.read().count("R.mods.%s.views." % node) == 3


def test_no_dead_res_map_text_in_src_or_docs():
    files = [os.path.join(_ROOT, f) for f in _DOC_FILES]
    for base, _dirs, names in os.walk(os.path.join(_ROOT, "src")):
        files += [os.path.join(base, n) for n in names if n.endswith(_EXTS)]
    hits = []
    for path in files:
        if os.path.isfile(path):
            with open(path, encoding="utf-8", errors="replace") as fh:
                if re.search(r"res_map|ModDynAccessor", fh.read()):
                    hits.append(os.path.relpath(path, _ROOT))
    assert not hits, hits
