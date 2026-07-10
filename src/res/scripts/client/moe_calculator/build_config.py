# -*- coding: utf-8 -*-
"""Build-variant configuration.

`MOE_DATA_SOURCE` selects which Marks-of-Excellence threshold provider the `moe_data` router
uses at runtime:
  - "tomato"  -> adapter/moe_tomato  (fetch tomato.gg; the GitHub-release / dev / deploy build)
  - "offline" -> adapter/moe_offline (estimate from the client's own dossier; no external API --
                 the WGMods-release build)

The in-repo default is "tomato". build/build_wotmod.py OVERWRITES this constant at package time
from its --data-source argument (compiling a substituted copy -- the repo file is never mutated),
so the WGMods package ships "offline" without a source edit. Keep this module import-cheap and
free of game symbols: the router imports it at module load.
"""
MOE_DATA_SOURCE = "tomato"   # "tomato" | "offline"
