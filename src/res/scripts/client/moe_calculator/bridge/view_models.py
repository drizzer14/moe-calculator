# -*- coding: utf-8 -*-
"""Wulf ViewModel definitions for the widget's data channel.

Two models: MarkTickVM (one milestone tick) and MoEVM (the root model exposed as
`moeData`, holding the scalar fields + the ticks array). v1 is read-only, so there are
no reverse-channel commands.

IMPORTANT -- the numeric property indices below are HAND-MAINTAINED and MUST match the
_addXProperty registration order: `_setNumber(i, v)` / `_setString(i, v)` address the
i-th registered property, so reordering or inserting a property without renumbering
every setter silently mismaps fields. The JS reader reads these by NAME, so the names
are the contract with the widget. PC-only (needs the live frameworks.wulf).
"""
from frameworks.wulf import ViewModel, Array


class MarkTickVM(ViewModel):
    def __init__(self, properties=4, commands=0):
        super(MarkTickVM, self).__init__(properties=properties, commands=commands)

    def _initialize(self):
        super(MarkTickVM, self)._initialize()
        self._addNumberProperty("percent", 0)          # 0  fixed axis position 65/85/95
        self._addNumberProperty("markCount", 0)        # 1  1/2/3
        self._addNumberProperty("damageRequired", 0)   # 2  combined dmg for this mark (0 = unknown)
        self._addBoolProperty("reached", False)        # 3  player already holds this mark
        # NOTE: no per-tick `icon` property -- the widget draws a flat, nation-agnostic glyph
        # (MoECalculator.js FLAT_MARK) for every tick, so the old nation-art URL was dead.

    def setPercent(self, v):
        self._setNumber(0, v)

    def setMarkCount(self, v):
        self._setNumber(1, v)

    def setDamageRequired(self, v):
        self._setNumber(2, v)

    def setReached(self, v):
        self._setBool(3, v)


class MoEVM(ViewModel):
    def __init__(self, properties=12, commands=0):
        super(MoEVM, self).__init__(properties=properties, commands=commands)

    def _initialize(self):
        super(MoEVM, self)._initialize()
        self._addBoolProperty("visible", True)         # 0  false hides the bar
        self._addStringProperty("nation", "")          # 1  nation id ('germany', ...)
        self._addNumberProperty("marks", 0)            # 2  current marks 0..3
        self._addRealProperty("curPercent", 0.0)       # 3  current percentile (float -- MUST be Real:
                                                       #    _setNumber casts to int() and drops the decimals)
        self._addNumberProperty("curAvgDamage", 0)     # 4  current moving-avg combined dmg
        self._addRealProperty("fill", 0.0)             # 5  bar fill 0..100 (== curPercent; Real for a
                                                       #    smooth sub-percent edge, same int() reason)
        self._addBoolProperty("hasData", False)        # 6  external thresholds loaded
        self._addNumberProperty("carouselRows", 1)     # 7  1 single / 2 double (positioning)
        self._addBoolProperty("carouselSmall", False)  # 8  double-row: small vs tall adaptive
        self._addArrayProperty("ticks", Array())       # 9  [MarkTickVM] * 3, ascending
        self._addNumberProperty("endDamageRequired", 0)  # 10  100th-pct dmg goalpost (0 = unknown)
        self._addStringProperty("labels", "")          # 11  JSON {key: localized text} for the tooltip

    def setVisible(self, v):
        self._setBool(0, v)

    def setNation(self, v):
        self._setString(1, v)

    def setMarks(self, v):
        self._setNumber(2, v)

    def setCurPercent(self, v):
        self._setReal(3, v)

    def setCurAvgDamage(self, v):
        self._setNumber(4, v)

    def setFill(self, v):
        self._setReal(5, v)

    def setHasData(self, v):
        self._setBool(6, v)

    def setCarouselRows(self, v):
        self._setNumber(7, v)

    def setCarouselSmall(self, v):
        self._setBool(8, v)

    def setEndDamageRequired(self, v):
        self._setNumber(10, v)

    def setLabels(self, v):
        self._setString(11, v)

    def getTicks(self):
        return self._getArray(9)

    @staticmethod
    def getTicksType():
        return MarkTickVM


class BattleMoEVM(ViewModel):
    """Root model for the in-battle overlay. It IS the registered MoEBattleView's own root
    ViewModel (the JS reads it with a root ModelObserver(), NOT via a nested submodel).
    Flat (no ticks array) -- the four readouts + gating flags. Read-only (no reverse-channel
    commands). Indices are hand-maintained to match the _addXProperty order; JS reads by NAME."""
    def __init__(self, properties=10, commands=0):
        super(BattleMoEVM, self).__init__(properties=properties, commands=commands)

    def _initialize(self):
        super(BattleMoEVM, self)._initialize()
        self._addBoolProperty("visible", False)          # 0  false hides the overlay
        self._addNumberProperty("combinedDamage", 0)     # 1  live CD this battle
        self._addNumberProperty("projAvgDamage", 0)      # 2  EWMA-projected avg incl. this CD
        self._addRealProperty("curPercent", 0.0)         # 3  MoE percentile of the projection (float --
                                                         #    MUST be Real: _setNumber casts to int())
        self._addRealProperty("pctDelta", 0.0)           # 4  signed delta vs pre-battle standing (float, Real)
        self._addBoolProperty("hasData", False)          # 5  threshold table usable (percent real)
        self._addBoolProperty("hasBaseline", False)      # 6  career baseline present; false (replay/
                                                         #    relogin) -> proj/percent/delta dashed out
        self._addNumberProperty("countedAssist", 0)      # 7  counted assistance = max(track, spot, stun)
        self._addStringProperty("assistKind", "assist")  # 8  which stream leads: track|spot|stun|assist
                                                         #    (selects the third-row icon)
        self._addBoolProperty("assistVisible", False)    # 9  "Enable Counted Assistance" setting; JS also
                                                         #    hides the row while countedAssist == 0

    def setVisible(self, v):
        self._setBool(0, v)

    def setCombinedDamage(self, v):
        self._setNumber(1, v)

    def setProjAvgDamage(self, v):
        self._setNumber(2, v)

    def setCurPercent(self, v):
        self._setReal(3, v)

    def setPctDelta(self, v):
        self._setReal(4, v)

    def setHasData(self, v):
        self._setBool(5, v)

    def setHasBaseline(self, v):
        self._setBool(6, v)

    def setCountedAssist(self, v):
        self._setNumber(7, v)

    def setAssistKind(self, v):
        self._setString(8, v)

    def setAssistVisible(self, v):
        self._setBool(9, v)
