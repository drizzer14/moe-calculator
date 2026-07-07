# -*- coding: utf-8 -*-
# DEV probe: hunt for a good "Marks of Excellence" title key and a short "Marks" label.
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
CANDIDATES = [
    "#achievements:marksOnGun",
    "#achievements:marksOnGunName",
    "#achievements:marksOnGunHeader",
    "#achievements:marksOnGunDescr",
    "#menu:marksOnGun",
    "#menu:vehicleInfo/marksOnGun",
    "#tooltips:marksOnGun",
    "#tooltips:vehParams/marksOnGun",
    "#tooltips:achievement/marksOnGun/header",
    "#tooltips:achievement/marksOnGun/body",
    "#quests:details/achievement/marksOnGun",
    "#menu:tank_params/marksOnGun",
    "#vehicle_customization:propertySheet/marksOnGun",
    # short "Marks" / "Mark" noun candidates
    "#menu:marks",
    "#menu:mastery/marks",
    "#tooltips:marksOnGunCount",
    "#achievements:marksCount",
]
for key in CANDIDATES:
    try:
        t = i18n.makeString(key)
        hit = "MISS" if (not t or t.startswith("#")) else "HIT "
        _p("%s %-48s => %r" % (hit, key, t))
    except Exception as e:
        _p("ERR  %-48s %r" % (key, e))
