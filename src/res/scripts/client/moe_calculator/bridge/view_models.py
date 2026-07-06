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
    def __init__(self, properties=5, commands=0):
        super(MarkTickVM, self).__init__(properties=properties, commands=commands)

    def _initialize(self):
        super(MarkTickVM, self)._initialize()
        self._addNumberProperty("percent", 0)          # 0  fixed axis position 65/85/95
        self._addNumberProperty("markCount", 0)        # 1  1/2/3
        self._addNumberProperty("damageRequired", 0)   # 2  combined dmg for this mark (0 = unknown)
        self._addBoolProperty("reached", False)        # 3  player already holds this mark
        self._addStringProperty("icon", "")            # 4  nation mark art url ("" = generic)

    def setPercent(self, v):
        self._setNumber(0, v)

    def setMarkCount(self, v):
        self._setNumber(1, v)

    def setDamageRequired(self, v):
        self._setNumber(2, v)

    def setReached(self, v):
        self._setBool(3, v)

    def setIcon(self, v):
        self._setString(4, v)


class MoEVM(ViewModel):
    def __init__(self, properties=10, commands=0):
        super(MoEVM, self).__init__(properties=properties, commands=commands)

    def _initialize(self):
        super(MoEVM, self)._initialize()
        self._addBoolProperty("visible", True)         # 0  false hides the bar
        self._addStringProperty("nation", "")          # 1  nation id ('germany', ...)
        self._addNumberProperty("marks", 0)            # 2  current marks 0..3
        self._addNumberProperty("curPercent", 0)       # 3  current percentile (float)
        self._addNumberProperty("curAvgDamage", 0)     # 4  current moving-avg combined dmg
        self._addNumberProperty("fill", 0)             # 5  bar fill 0..100 (== curPercent)
        self._addBoolProperty("hasData", False)        # 6  external thresholds loaded
        self._addNumberProperty("carouselRows", 1)     # 7  1 single / 2 double (positioning)
        self._addBoolProperty("carouselSmall", False)  # 8  double-row: small vs tall adaptive
        self._addArrayProperty("ticks", Array())       # 9  [MarkTickVM] * 3, ascending

    def setVisible(self, v):
        self._setBool(0, v)

    def setNation(self, v):
        self._setString(1, v)

    def setMarks(self, v):
        self._setNumber(2, v)

    def setCurPercent(self, v):
        self._setNumber(3, v)

    def setCurAvgDamage(self, v):
        self._setNumber(4, v)

    def setFill(self, v):
        self._setNumber(5, v)

    def setHasData(self, v):
        self._setBool(6, v)

    def setCarouselRows(self, v):
        self._setNumber(7, v)

    def setCarouselSmall(self, v):
        self._setBool(8, v)

    def getTicks(self):
        return self._getArray(9)

    @staticmethod
    def getTicksType():
        return MarkTickVM
