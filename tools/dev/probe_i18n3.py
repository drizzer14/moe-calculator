# -*- coding: utf-8 -*-
import sys
try:
    _echo = echo  # noqa: F821
except NameError:
    _echo = lambda x: sys.stdout.write(str(x) + "\n")
def _p(x):
    try:
        _echo(x)
    except Exception as e:
        _echo("<<err %r>>" % (e,))

from helpers import i18n
def tail(k):
    return k.split(":", 1)[1] if ":" in k else k
for key in [
    "#achievements:marksOnGun0",
    "#achievements:marksOnGun1",
    "#achievements:marksOnGun2",
    "#achievements:marksOnGun3",
    "#achievements:marksOnGun_condition",
    "#achievements:marksOnGun/count",
    "#achievements:marksOnGunHeader",
    "#achievements:marksOnGun/descr/param/label/c_1",
]:
    try:
        t = i18n.makeString(key)
        miss = (not t) or t == tail(key) or t.startswith("#")
        _p("%s %-42s => %r" % ("MISS" if miss else "HIT ", key, t))
    except Exception as e:
        _p("ERR  %-42s %r" % (key, e))

# Try the generated R.strings accessors directly (real string IDs).
try:
    from gui.impl.gen import R
    from gui.impl import backport
    for name in ["marksOnGun0", "marksOnGun1", "marksOnGun2", "marksOnGun3", "marksOnGunHeader"]:
        acc = getattr(R.strings.achievements, name, None)
        val = backport.text(acc()) if acc is not None else "<no-accessor>"
        _p("R.achievements.%-16s => %r" % (name, val))
except Exception as e:
    _p("R.strings ERR %r" % (e,))
