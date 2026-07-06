# -*- coding: utf-8 -*-
"""Shared string ids used across the domain, adapter, and view.

Centralizing them means a typo is a NameError instead of a silently mismatched tick
that renders wrong. Values are the contract with the widget JS -- do not change a
value without updating the JS that switches on Tick.category (the CAT map in the .js).
2/3-compatible, engine-free.
"""


class Category(object):
    """Tick.category -- drives the per-tick glyph the widget renders. Also the value
    of UnlockItem.kind for tech-tree items."""
    VEHICLE = "vehicle"      # tech-tree: a next-vehicle unlock
    MODULE = "module"        # tech-tree: a module unlock
