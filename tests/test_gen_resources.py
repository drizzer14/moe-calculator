# -*- coding: utf-8 -*-
"""The WG-native resource declaration (client 2.4.1+) must parse and declare every battle view the
bridge resolves via bar_window.layout_id(); an invalid JSON breaks the client's resource loading,
and a missing entry silently leaves that window at layoutID -1."""
import json
import os
import re

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_RES = os.path.join(_ROOT, "src", "res")
_BRIDGE = os.path.join(_RES, "scripts", "client", "moe_calculator", "bridge")
_JSON = os.path.join(_RES, "gui", "gen_resources", "com.14th_ua.moe_calculator.json")


def _src(name):
    with open(os.path.join(_BRIDGE, name), encoding="utf-8") as fh:
        return fh.read()


def test_gen_resources_declares_every_resolved_view():
    with open(_JSON, encoding="utf-8") as fh:
        entries = json.load(fh)
    node = re.search(r'^_RES_NODE = "(\w+)"', _src("bar_window.py"), re.M).group(1)
    views = [re.search(r'^RES_MAP_ITEM_ID = "(\w+)"', _src(f), re.M).group(1)
             for f in ("battle_view.py", "progress_view.py", "efficiency_view.py")]
    by_id = {e["id"]: e for e in entries}
    assert len(by_id) == len(entries)
    for view in views:
        e = by_id["R.mods.%s.views.%s" % (node, view)]
        assert e["type"] == "Layout"
        assert e["parameters"] == {"entrance": view, "impl": "gameface"}
        assert e["path"].startswith("coui://")
        assert os.path.isfile(os.path.join(_RES, e["path"][len("coui://"):]))


def test_no_legacy_res_map_left():
    assert not os.path.exists(os.path.join(_RES, "mods", "configs", "res_map"))
