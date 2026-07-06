# -*- coding: utf-8 -*-
"""Wulf ViewModel definitions for the widget's data channel.

Two models: TickVM (one bar tick) and ResearchVM (the root model exposed as
`moe_calculatorModel`, holding the scalar fields + the ticks array + a reverse-channel
command).

IMPORTANT -- the numeric property indices below are HAND-MAINTAINED and MUST match the
_addXProperty registration order: `_setNumber(i, v)` / `_setString(i, v)` address the
i-th registered property, so reordering or inserting a property without renumbering
every setter silently mismaps fields. The JS reader reads these by NAME, so the names
are the contract with the widget. PC-only (needs the live frameworks.wulf).
"""
from frameworks.wulf import ViewModel, Array


class TickVM(ViewModel):
    def __init__(self, properties=6, commands=0):
        super(TickVM, self).__init__(properties=properties, commands=commands)

    def _initialize(self):
        super(TickVM, self)._initialize()
        self._addNumberProperty("position", 0)     # 0
        self._addNumberProperty("xpRequired", 0)   # 1
        self._addStringProperty("category", "")    # 2
        self._addStringProperty("name", "")        # 3
        self._addBoolProperty("affordable", False)  # 4
        self._addNumberProperty("actionId", 0)     # 5 (tech-tree int_cd; 0 = not clickable)

    def setPosition(self, v):
        self._setNumber(0, v)

    def setXpRequired(self, v):
        self._setNumber(1, v)

    def setCategory(self, v):
        self._setString(2, v)

    def setName(self, v):
        self._setString(3, v)

    def setAffordable(self, v):
        self._setBool(4, v)

    def setActionId(self, v):
        self._setNumber(5, v)


class ResearchVM(ViewModel):
    def __init__(self, properties=8, commands=2):
        super(ResearchVM, self).__init__(properties=properties, commands=commands)

    def _initialize(self):
        super(ResearchVM, self)._initialize()
        self._addStringProperty("mode", "")        # 0
        self._addNumberProperty("scaleMin", 0)     # 1
        self._addNumberProperty("scaleMax", 0)     # 2
        self._addNumberProperty("fillVehicle", 0)  # 3
        self._addNumberProperty("fillFree", 0)     # 4
        self._addArrayProperty("ticks", Array())   # 5
        self._addNumberProperty("spendableXp", 0)  # 6 (vehicle XP + free XP, for affordability)
        self._addBoolProperty("visible", True)     # 7 (false hides the bar)
        # Reverse channel: JS click handlers invoke these commands. Each returns a
        # command object that connect_commands() wires to a Python handler. Wulf
        # delivers the JS-supplied argument(s) to those handlers.
        self.researchUnlock = self._addCommand("researchUnlock")  # arg: tech-tree int_cd
        self.openResearch = self._addCommand("openResearch")      # no arg

    def setMode(self, v):
        self._setString(0, v)

    def setScaleMin(self, v):
        self._setNumber(1, v)

    def setScaleMax(self, v):
        self._setNumber(2, v)

    def setFillVehicle(self, v):
        self._setNumber(3, v)

    def setFillFree(self, v):
        self._setNumber(4, v)

    def getTicks(self):
        return self._getArray(5)

    def setSpendableXp(self, v):
        self._setNumber(6, v)

    def setVisible(self, v):
        self._setBool(7, v)

    @staticmethod
    def getTicksType():
        return TickVM
