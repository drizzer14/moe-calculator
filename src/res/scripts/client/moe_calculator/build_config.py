# -*- coding: utf-8 -*-
"""Build-injected configuration.

`WG_APPLICATION_ID` is the Wargaming API application_id used by adapter/moe_wgapi. It is a
SECRET, so it is NOT committed: the repo ships an empty placeholder here, and
build/build_wotmod.py substitutes the real value (read from the gitignored `.env`) into a
compiled copy at package time -- the repo file is never mutated and the id only ever exists in
the built .wotmod. A build with no `.env` leaves it empty; moe_wgapi then can't fetch and the
bar degrades to ticks without per-mark damage labels. Keep this module import-cheap and free of
game symbols: moe_wgapi imports it at module load.
"""
WG_APPLICATION_ID = ""
