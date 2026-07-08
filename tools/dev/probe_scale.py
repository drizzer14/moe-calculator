# -*- coding: utf-8 -*-
"""Phase-0 scale probe for the mod-positioning task (S1/S2/S3).

Prints everything the Python side can observe about resolution + interface scale, so we
can decide whether the mod must push a uiScale from Python at all, or whether the engine's
logical GUI space + rem already neutralize interface scale (making the current vw/vh /
self-calibrating anchors already scale-correct).

    py -3 tools/dev/repl_client.py "execfile(r'<abs>/tools/dev/probe_scale.py')"

HOW TO RUN (record ALL four combinations, paste the outputs back):
  A. In the GARAGE at interface scale 1x   -> screenSize + interfaceScale + (no battle win)
  B. In the GARAGE at interface scale 2x   -> screenSize + interfaceScale
  C. In a REPLAY / training room at 1x      -> also prints the battle window's logical space
  D. In a REPLAY / training room at 2x      -> compare the battle logical space vs C

What each line tells us:
  * screenSize            physical device px (e.g. 3840x2160).
  * interfaceScale.get()  the multiplier (1.0 / 2.0 / ...); .getIndex() the raw index.
  * battle logical space  the GUI-space extent move() operates in, recovered by the same
                          far-sentinel calibration battle_view._onReady uses. If this
                          extent is IDENTICAL at 1x and 2x, the logical space is
                          scale-invariant and vw/vh already neutralizes scale (no push
                          needed); if it CHANGES with scale, the anchor fraction must
                          become a function of interfaceScale (Phase 1 battle side).
  * surface size          the fixed Wulf window surface (self.size) at each scale.
"""


def _line(label, val):
    try:
        echo("[scale-probe] %-26s %s" % (label, val))
    except Exception:
        pass


# --- resolution -------------------------------------------------------------
try:
    import BigWorld
    _line("BigWorld.screenSize()", BigWorld.screenSize())
except Exception as e:
    _line("BigWorld.screenSize() FAIL", repr(e))

# --- interface scale --------------------------------------------------------
try:
    from helpers import dependency
    from skeletons.account_helpers.settings_core import ISettingsCore
    sc = dependency.instance(ISettingsCore)
    isc = sc.interfaceScale
    _line("interfaceScale.get()", isc.get())
    try:
        _line("interfaceScale.getIndex()", isc.getIndex())
    except Exception as e:
        _line("interfaceScale.getIndex() FAIL", repr(e))
    # Also confirm the settings-diff key we would react to in Phase 1.
    try:
        from account_helpers.settings_core import settings_constants as scst
        _line("GRAPHICS.INTERFACE_SCALE", scst.GRAPHICS.INTERFACE_SCALE)
    except Exception as e:
        _line("GRAPHICS.INTERFACE_SCALE FAIL", repr(e))
except Exception as e:
    _line("interfaceScale FAIL", repr(e))

# --- damage-log flags (Phase 2 sanity; harmless to read here) --------------
try:
    from account_helpers.settings_core import settings_constants as scst
    core = dependency.instance(ISettingsCore)
    dl = scst.DAMAGE_LOG
    flags = {
        "TOTAL_DAMAGE": core.getSetting(dl.TOTAL_DAMAGE),
        "BLOCKED_DAMAGE": core.getSetting(dl.BLOCKED_DAMAGE),
        "ASSIST_DAMAGE": core.getSetting(dl.ASSIST_DAMAGE),
        "ASSIST_STUN": core.getSetting(dl.ASSIST_STUN),
    }
    _line("DAMAGE_LOG summary flags", flags)
    _line("all-four-unticked?", not any(bool(v) for v in flags.values()))
except Exception as e:
    _line("DAMAGE_LOG flags FAIL", repr(e))

# --- battle window logical space (replay/training only) --------------------
try:
    from frameworks.wulf import PositionAnchor
    from moe_calculator.bridge import battle_view as bv
    if bv._active is None:
        _line("battle window", "not open (run this in a REPLAY/training room)")
    else:
        window = bv._active[0]
        _FAR = 1 << 20
        window.move(_FAR, _FAR, xAnchor=PositionAnchor.LEFT, yAnchor=PositionAnchor.TOP)
        max_x, max_y = window.position
        win_w, win_h = window.size
        _line("surface size (self.size)", (win_w, win_h))
        _line("max movable (self.position)", (max_x, max_y))
        _line("logical space (max+size)", (max_x + win_w, max_y + win_h))
        # Restore the default anchor so we don't leave the overlay parked in the corner.
        space_w, space_h = max_x + win_w, max_y + win_h
        x = min(max(0, int(bv._ANCHOR_VW * space_w)), max_x)
        y = min(max(0, int(bv._ANCHOR_VH * space_h)), max_y)
        window.move(x, y, xAnchor=PositionAnchor.LEFT, yAnchor=PositionAnchor.TOP)
        _line("restored to anchor", (x, y))
except Exception as e:
    _line("battle window probe FAIL", repr(e))

_line("done", "paste all outputs (garage 1x/2x + replay 1x/2x)")
