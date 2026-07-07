# -*- coding: utf-8 -*-
# DEV probe: verify reused WG-string wording + deployed labels() output.
import sys
# `echo` is injected by the REPL server into this exec namespace; fall back to print.
try:
    _echo = echo  # noqa: F821
except NameError:
    _echo = lambda x: sys.stdout.write(str(x) + "\n")
def _p(x):
    try:
        _echo(x)
    except Exception as e:
        _echo("<<print-err %r>>" % (e,))

try:
    from helpers import getClientLanguage
    _p("lang=%r" % (getClientLanguage(),))
except Exception as e:
    _p("lang ERR %r" % (e,))

from helpers import i18n
KEYS = [
    ("title",     "#achievements:marksOnGunHeader"),
    ("avgDamage", "#menu:tank_params/avgDamage"),
    ("damage",    "#menu:tank_params/damage"),
    ("marks",     "#tooltips:achievement/marksOnGunCount"),
]
for name, key in KEYS:
    try:
        t = i18n.makeString(key)
        _p("WGKEY %-10s %-45s => %r" % (name, key, t))
    except Exception as e:
        _p("WGKEY %-10s %-45s ERR %r" % (name, key, e))

# What the deployed adapter actually produces:
try:
    from moe_calculator.adapter import i18n as modi18n
    modi18n.reset_cache()
    _p("labels()=%r" % (modi18n.labels(),))
except Exception as e:
    _p("labels() ERR %r" % (e,))
