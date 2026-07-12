# -*- coding: utf-8 -*-
"""Enumerate every video mode WoT offers + the interface-scale option table, so we can
compute the exact 1rem(px)=interfaceScale for each resolution the user can pick and
calibrate the garage anchor for ALL of them (not just the 3 tested live).

    py -3 tools/dev/repl_client.py "execfile(r'<abs>/tools/dev/probe_resolutions.py')"
"""


def _line(label, val):
    try:
        echo("[res-probe] %-30s %s" % (label, val))
    except Exception:
        pass


# --- current state ----------------------------------------------------------
try:
    import BigWorld
    _line("screenSize()", BigWorld.screenSize())
except Exception as e:
    _line("screenSize FAIL", repr(e))

# --- video mode list --------------------------------------------------------
try:
    import BigWorld
    modes = BigWorld.listVideoModes()
    _line("listVideoModes() count", len(modes))
    for m in modes:
        _line("  mode", m)
except Exception as e:
    _line("listVideoModes FAIL", repr(e))

try:
    import BigWorld
    _line("videoModeIndex()", BigWorld.videoModeIndex())
    _line("isVideoWindowed()", BigWorld.isVideoWindowed())
    try:
        _line("windowSize()", BigWorld.windowSize())
    except Exception as e:
        _line("windowSize FAIL", repr(e))
except Exception as e:
    _line("videoMode info FAIL", repr(e))

# --- interface scale option table ------------------------------------------
try:
    from helpers import dependency
    from skeletons.account_helpers.settings_core import ISettingsCore
    sc = dependency.instance(ISettingsCore)
    isc = sc.interfaceScale
    _line("interfaceScale.get()", isc.get())
    for attr in ("getIndex", "getOptions", "getScaleLength", "getScaleByIndex",
                 "getInterfaceScale", "_getOptions", "getDefault"):
        try:
            fn = getattr(isc, attr, None)
            if callable(fn):
                _line("interfaceScale.%s()" % attr, fn())
        except Exception as e:
            _line("interfaceScale.%s FAIL" % attr, repr(e))
    _line("interfaceScale dir", [a for a in dir(isc) if not a.startswith("__")])
except Exception as e:
    _line("interfaceScale table FAIL", repr(e))

# --- how Auto derives scale from resolution (the mapping we need) ----------
try:
    from account_helpers.settings_core.settings_options import InterfaceScaleOptions  # noqa
    _line("InterfaceScaleOptions", "imported")
except Exception as e:
    _line("InterfaceScaleOptions import", repr(e))

try:
    from gui.Scaleform.daapi.settings.interface_scale import g_interfaceScale  # best-effort
    _line("g_interfaceScale", repr(g_interfaceScale))
except Exception as e:
    _line("g_interfaceScale import", repr(e))

_line("done", "paste output")
