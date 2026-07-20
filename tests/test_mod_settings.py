# -*- coding: utf-8 -*-
"""Tests for the settings module's pure merge logic. merge_settings is the only piece that
must be correct without the game: it turns whatever ModsSettingsAPI hands back (or nothing)
into the booleans the bridges read. The MSA registration/glue is not unit-tested (it needs
the client)."""
import sys
import types

import pytest

from moe_calculator.bridge import mod_settings
from moe_calculator.bridge.mod_settings import (
    merge_settings, DEFAULTS, GARAGE_KEY, BATTLE_KEY, BATTLE_ALT_KEY,
    COUNTED_ASSIST_KEY, LINKAGE, SETTINGS_VERSION, battle_alt_key_enabled,
    battle_enabled, counted_assistance_enabled,
    POS_X_KEY, POS_Y_KEY, POS_W_KEY, POS_H_KEY, FOLLOW_CAROUSEL_KEY, POS_MAX,
    clamp_pos, pos_x, pos_y, pos_w, pos_h, follow_carousel, set_position)
from moe_calculator.adapter import settings_i18n


def _defaults_with(over):
    """A fresh copy of the full 9-key DEFAULTS with `over` (a dict) applied -- keeps the
    exact-equality merge assertions readable now that DEFAULTS carries the position group.
    Takes a dict (not **kwargs) because the keys are runtime varName strings, not identifiers."""
    out = dict(DEFAULTS)
    out.update(over)
    return out


@pytest.fixture(autouse=True)
def _restore_settings():
    """Each test that mutates the module-global cache restores it afterwards."""
    saved = dict(mod_settings._settings)
    yield
    mod_settings._seed(saved)


def test_defaults_when_empty_or_none():
    # No saved store (fresh install / MSA absent) -> both widgets on, Alt-peek and the
    # counted-assistance row off (both opt-in), the drag position at auto (0/0/0/0) and
    # Follow Carousel Mode on.
    assert merge_settings(None) == DEFAULTS
    assert merge_settings({}) == DEFAULTS
    assert DEFAULTS == {GARAGE_KEY: True, BATTLE_KEY: True, BATTLE_ALT_KEY: False,
                        COUNTED_ASSIST_KEY: False,
                        POS_X_KEY: 0, POS_Y_KEY: 0, POS_W_KEY: 0, POS_H_KEY: 0,
                        FOLLOW_CAROUSEL_KEY: True}


def test_overlays_known_keys():
    out = merge_settings({GARAGE_KEY: False, BATTLE_KEY: True, BATTLE_ALT_KEY: True,
                          COUNTED_ASSIST_KEY: True})
    # Only the four bool flags were supplied -> the position group keeps its auto defaults.
    assert out == _defaults_with({GARAGE_KEY: False, BATTLE_KEY: True, BATTLE_ALT_KEY: True,
                                  COUNTED_ASSIST_KEY: True})
    out2 = merge_settings({GARAGE_KEY: True, BATTLE_KEY: False, BATTLE_ALT_KEY: False,
                           COUNTED_ASSIST_KEY: False,
                           POS_X_KEY: 640, POS_Y_KEY: 360, POS_W_KEY: 1920, POS_H_KEY: 1080,
                           FOLLOW_CAROUSEL_KEY: False})
    # A full store overlays every key, position coords coerced to clamped ints.
    assert out2 == {GARAGE_KEY: True, BATTLE_KEY: False, BATTLE_ALT_KEY: False,
                    COUNTED_ASSIST_KEY: False,
                    POS_X_KEY: 640, POS_Y_KEY: 360, POS_W_KEY: 1920, POS_H_KEY: 1080,
                    FOLLOW_CAROUSEL_KEY: False}


def test_partial_dict_fills_missing_with_defaults():
    # Only one key present -> the others fall back to their defaults.
    out = merge_settings({GARAGE_KEY: False})
    assert out == _defaults_with({GARAGE_KEY: False})


def test_unknown_keys_ignored():
    out = merge_settings({GARAGE_KEY: False, "bogus": 123, "settingsVersion": 9})
    assert out == _defaults_with({GARAGE_KEY: False})
    assert "bogus" not in out


def test_values_coerced_to_bool():
    out = merge_settings({GARAGE_KEY: 0, BATTLE_KEY: 1, BATTLE_ALT_KEY: 1,
                          COUNTED_ASSIST_KEY: 1})
    assert out[GARAGE_KEY] is False
    assert out[BATTLE_KEY] is True
    assert out[BATTLE_ALT_KEY] is True
    assert out[COUNTED_ASSIST_KEY] is True


def test_non_dict_input_degrades_to_defaults():
    assert merge_settings("nonsense") == DEFAULTS
    assert merge_settings(42) == DEFAULTS
    assert merge_settings([GARAGE_KEY]) == DEFAULTS


def test_returns_fresh_dict_not_defaults_alias():
    # Must not hand back a reference to DEFAULTS (a caller mutating it would corrupt the base).
    out = merge_settings({})
    out[GARAGE_KEY] = False
    assert DEFAULTS[GARAGE_KEY] is True


def test_battle_alt_key_default_off_and_getter():
    # Getter reads the live cache. _seed replaces it wholesale; _apply overlays.
    mod_settings._seed(DEFAULTS)
    assert battle_alt_key_enabled() is False
    mod_settings._apply({BATTLE_ALT_KEY: True})
    assert battle_alt_key_enabled() is True
    mod_settings._apply({BATTLE_ALT_KEY: 0})
    assert battle_alt_key_enabled() is False


def test_counted_assistance_default_off_and_getter():
    # The counted-assistance row ships OFF (opt-in) and the getter tracks live changes.
    mod_settings._seed(DEFAULTS)
    assert counted_assistance_enabled() is False
    mod_settings._apply({COUNTED_ASSIST_KEY: True})
    assert counted_assistance_enabled() is True
    mod_settings._apply({COUNTED_ASSIST_KEY: 0})
    assert counted_assistance_enabled() is False


# --- the foreign-broadcast bug: a payload with none of our keys must NOT reset us ----------

def test_apply_preserves_current_for_absent_keys():
    # Reproduces the bug: MSA fires our onSettingsChanged for OTHER mods' changes, handing a
    # payload with none of our keys. That must NOT snap our flags back to defaults.
    mod_settings._seed({GARAGE_KEY: True, BATTLE_KEY: False, BATTLE_ALT_KEY: True})
    mod_settings._apply({"showElite": True, "posX": 1920})  # a foreign mod's settings dict
    assert battle_enabled() is False           # preserved, NOT reset to default True
    assert battle_alt_key_enabled() is True     # preserved, NOT reset to default False


def test_apply_overlays_only_present_keys():
    mod_settings._seed({GARAGE_KEY: True, BATTLE_KEY: True, BATTLE_ALT_KEY: False})
    mod_settings._apply({BATTLE_KEY: False})   # only one of our keys present
    assert battle_enabled() is False           # applied
    assert mod_settings.garage_enabled() is True   # untouched
    assert battle_alt_key_enabled() is False       # untouched


def test_apply_ignores_non_dict():
    mod_settings._seed({GARAGE_KEY: True, BATTLE_KEY: False, BATTLE_ALT_KEY: True})
    for junk in (None, "x", 42, [BATTLE_KEY]):
        mod_settings._apply(junk)
        assert battle_enabled() is False and battle_alt_key_enabled() is True


def test_on_changed_ignores_foreign_linkage():
    mod_settings._seed({GARAGE_KEY: True, BATTLE_KEY: False, BATTLE_ALT_KEY: True})
    # A foreign linkage carrying our-looking keys must be ignored entirely.
    mod_settings._on_changed("com.someone.othermod",
                             {BATTLE_KEY: True, BATTLE_ALT_KEY: False})
    assert battle_enabled() is False and battle_alt_key_enabled() is True
    # Our own linkage applies.
    mod_settings._on_changed(LINKAGE, {BATTLE_KEY: True})
    assert battle_enabled() is True


# --- _template() structure (two columns + grouped In-Battle master/children) --------------
# _template() is buildable game-closed: settings_i18n.panel_text() falls back to English (no
# `helpers`), and _grouped_column1 hits its FALLBACK branch (gui.aslainMenu absent) which is
# exactly the manual masterVarName binding we assert below.

def _varnames(controls):
    return [c["varName"] for c in controls]


def test_template_settings_version_is_5():
    # Bumped 4 -> 5 when the drag-to-reposition controls landed (new varNames + a new
    # column-2 layout), so the bump reaches an existing install and MSA rebuilds the panel.
    assert SETTINGS_VERSION == 5
    assert mod_settings._template()["settingsVersion"] == 5


def test_template_column1_is_grouped_master_and_two_children():
    tmpl = mod_settings._template()
    col1 = tmpl["column1"]
    # Exactly three controls, in order: In-Battle master, Alt child, counted-assist child.
    assert _varnames(col1) == [BATTLE_KEY, BATTLE_ALT_KEY, COUNTED_ASSIST_KEY]


def test_template_column2_garage_then_positioning_group():
    # Column 2 = the standalone In-Garage master, then the drag-position group: a positioning
    # Label header (no varName), the X/Y numeric steppers, and the Follow Carousel checkbox.
    col2 = mod_settings._template()["column2"]
    assert [c["type"] for c in col2] == [
        "CheckBox", "Label", "NumericStepper", "NumericStepper", "CheckBox"]
    # The varName-bearing controls, in order (the Label header has no stored value).
    assert [c["varName"] for c in col2 if "varName" in c] == [
        GARAGE_KEY, POS_X_KEY, POS_Y_KEY, FOLLOW_CAROUSEL_KEY]
    # The Label header carries no varName (it is not a persisted value).
    assert "varName" not in col2[1]


def test_template_steppers_are_bounded_manual_entry():
    # Each position stepper spans [0, POS_MAX], allows manual input and steps by 1 px so a
    # typed 0 returns the widget to auto and a nudge isn't rounded away.
    col2 = mod_settings._template()["column2"]
    steppers = [c for c in col2 if c["type"] == "NumericStepper"]
    assert [c["varName"] for c in steppers] == [POS_X_KEY, POS_Y_KEY]
    for s in steppers:
        assert s["minimum"] == 0
        assert s["maximum"] == POS_MAX
        assert s["canManualInput"] is True
        assert s["snapInterval"] == 1


def test_template_children_bind_to_battle_master():
    # The two children carry masterVarName == the battle master's varName so MSA groups +
    # greys them out under the master. Proven via the manual-binding fallback branch (no
    # gui.aslainMenu under pytest -- see _grouped_column1).
    col1 = mod_settings._template()["column1"]
    _master, alt_child, counted_child = col1
    assert alt_child["masterVarName"] == BATTLE_KEY
    assert counted_child["masterVarName"] == BATTLE_KEY
    # The master itself is NOT bound to anything.
    assert "masterVarName" not in col1[0]


def test_template_control_defaults_match_defaults_dict():
    # Each value-bearing control's initial `value` mirrors its DEFAULTS entry (varName ==
    # DEFAULTS key). The Label header carries no varName/value and is skipped. Covers both the
    # checkboxes and the numeric steppers (steppers default to 0 = auto).
    tmpl = mod_settings._template()
    for c in tmpl["column1"] + tmpl["column2"]:
        if "varName" not in c:            # a Label header -- not a stored value
            assert c["type"] == "Label"
            continue
        assert c["type"] in ("CheckBox", "NumericStepper")
        assert c["value"] == DEFAULTS[c["varName"]]


def test_grouped_column1_uses_aslain_helper_when_present(monkeypatch):
    # When Aslain's templates.createControlsGroup exists, _grouped_column1 delegates to it
    # (master, children, indent=True) instead of the manual fallback.
    calls = {}

    def _fake_group(master, children, indent=False):
        calls["args"] = (master, list(children), indent)
        return ["GROUPED", master] + list(children)

    fake_templates = types.ModuleType("gui.aslainMenu.templates")
    fake_templates.createControlsGroup = _fake_group
    fake_aslain = types.ModuleType("gui.aslainMenu")
    fake_aslain.templates = fake_templates
    fake_gui = types.ModuleType("gui")
    fake_gui.aslainMenu = fake_aslain
    monkeypatch.setitem(sys.modules, "gui", fake_gui)
    monkeypatch.setitem(sys.modules, "gui.aslainMenu", fake_aslain)
    monkeypatch.setitem(sys.modules, "gui.aslainMenu.templates", fake_templates)

    master = {"varName": BATTLE_KEY}
    children = [{"varName": BATTLE_ALT_KEY}, {"varName": COUNTED_ASSIST_KEY}]
    out = mod_settings._grouped_column1(master, children)
    assert out[0] == "GROUPED"                      # the helper's return is used verbatim
    assert calls["args"] == (master, children, True)  # called with indent=True
    # The helper owns the binding, so we did NOT set masterVarName by hand here.
    assert "masterVarName" not in children[0]


# --- COL*_KEYS stay in lockstep with the built template order (so _sync_template_text walks
# the stored template correctly) -----------------------------------------------------------

def test_col_keys_lockstep_with_template_order():
    # _sync_template_text zips tmpl[col] with settings_i18n.COL*_KEYS and writes panel_text()[key]
    # onto each control. That only lands text on the right control if the built template's column
    # order matches the key tuples. Prove it: each control's rendered text == panel_text()[key].
    tmpl = mod_settings._template()
    text = settings_i18n.panel_text()
    for col, keys in (("column1", settings_i18n.COL1_KEYS),
                      ("column2", settings_i18n.COL2_KEYS)):
        controls = tmpl[col]
        assert len(controls) == len(keys), (
            "%s length drifted from COL keys" % col)
        for control, key in zip(controls, keys):
            assert control["text"] == text[key]["text"]
            assert control.get("tooltip") == text[key].get("tooltip")


def test_sync_template_text_walks_built_template_in_lockstep():
    # End-to-end for the sync path: build a stored template exactly as register() would, drift
    # every control's text, then _sync_template_text must restore each to panel_text()[key] --
    # proving the COL*_KEYS walk lands the right string on the right control.
    tmpl = mod_settings._template()
    for c in tmpl["column1"] + tmpl["column2"]:
        c["text"] = u"STALE"
        c["tooltip"] = u"STALE"
    saved = {"called": False}

    class _FakeApi(object):
        state = {"templates": {LINKAGE: tmpl}}

        def saveState(self):
            saved["called"] = True

    mod_settings._sync_template_text(_FakeApi())
    text = settings_i18n.panel_text()
    for col, keys in (("column1", settings_i18n.COL1_KEYS),
                      ("column2", settings_i18n.COL2_KEYS)):
        for control, key in zip(tmpl[col], keys):
            assert control["text"] == text[key]["text"]
            assert control["tooltip"] == text[key]["tooltip"]
    assert saved["called"] is True   # something changed -> state persisted


# --- drag-to-reposition: clamp_pos, accessors, set_position, follow_carousel, reset --------

def test_clamp_pos_bounds():
    # 0 = auto/unseeded; negatives and non-numeric collapse to 0; over-ceiling clamps down.
    assert clamp_pos(0) == 0
    assert clamp_pos(-1) == 0
    assert clamp_pos(-9999) == 0
    assert clamp_pos(123) == 123
    assert clamp_pos(POS_MAX) == POS_MAX
    assert clamp_pos(POS_MAX + 1) == POS_MAX
    assert clamp_pos(10 ** 9) == POS_MAX
    # Non-numeric / None -> 0 (a bad measurement never pins).
    assert clamp_pos(None) == 0
    assert clamp_pos("abc") == 0
    assert clamp_pos([1, 2]) == 0
    # Numeric strings / floats coerce through int().
    assert clamp_pos("640") == 640
    assert clamp_pos(360.9) == 360


def test_position_accessors_round_trip():
    mod_settings._seed(dict(DEFAULTS))
    # Auto default: every coordinate 0.
    assert (pos_x(), pos_y(), pos_w(), pos_h()) == (0, 0, 0, 0)
    mod_settings._apply({POS_X_KEY: 640, POS_Y_KEY: 360, POS_W_KEY: 2560, POS_H_KEY: 1440})
    assert pos_x() == 640
    assert pos_y() == 360
    assert pos_w() == 2560
    assert pos_h() == 1440


def test_position_accessors_clamp_a_bad_stored_value():
    # A getter re-clamps whatever is cached, so a corrupt store never leaks a bad px out.
    mod_settings._seed(dict(DEFAULTS))
    mod_settings._settings[POS_X_KEY] = -50
    mod_settings._settings[POS_Y_KEY] = POS_MAX + 500
    assert pos_x() == 0
    assert pos_y() == POS_MAX


def test_follow_carousel_default_true_and_getter():
    mod_settings._seed(dict(DEFAULTS))
    assert follow_carousel() is True
    mod_settings._apply({FOLLOW_CAROUSEL_KEY: False})
    assert follow_carousel() is False
    mod_settings._apply({FOLLOW_CAROUSEL_KEY: 1})   # coerced to bool
    assert follow_carousel() is True


class _FakeMsa(object):
    """A stand-in ModsSettingsAPI sink: returns a stored dict from getModSettings and records
    the full dict written by updateModSettings + whether saveState flushed it."""
    def __init__(self, current):
        self._current = current
        self.written = None
        self.saved = False

    def getModSettings(self, linkage, template):
        return dict(self._current)

    def updateModSettings(self, linkage, data):
        self.written = data

    def saveState(self):
        self.saved = True


def test_set_position_writes_full_dict_preserving_enabled(monkeypatch):
    # set_position must write the WHOLE settings dict (MSA replace-not-merge) and preserve the
    # host-managed 'enabled' toggle + any foreign host keys, then flush with saveState().
    mod_settings._seed(dict(DEFAULTS))
    fake = _FakeMsa({"enabled": False, "someHostKey": 7})
    monkeypatch.setattr(mod_settings, "_primary_api", lambda: fake)

    set_position(100, 200, 1920, 1080)

    assert fake.saved is True                 # persisted to disk
    data = fake.written
    assert data is not None
    # host keys preserved (not clobbered by our partial write)
    assert data["enabled"] is False
    assert data["someHostKey"] == 7
    # our position coords written
    assert data[POS_X_KEY] == 100
    assert data[POS_Y_KEY] == 200
    assert data[POS_W_KEY] == 1920
    assert data[POS_H_KEY] == 1080
    # the FULL flag set is present too (replace-not-merge -> nothing of ours dropped)
    for key in DEFAULTS:
        assert key in data
    # live cache + accessors reflect the new pin
    assert (pos_x(), pos_y(), pos_w(), pos_h()) == (100, 200, 1920, 1080)


def test_set_position_adds_enabled_when_host_omits_it(monkeypatch):
    # If the stored dict lacks 'enabled', the write must still guarantee it (a missing
    # 'enabled' blanks Aslain's whole panel).
    mod_settings._seed(dict(DEFAULTS))
    fake = _FakeMsa({})
    monkeypatch.setattr(mod_settings, "_primary_api", lambda: fake)
    set_position(10, 20)
    assert fake.written["enabled"] is True


def test_set_position_clamps_and_survives_absent_msa(monkeypatch):
    # No MSA present -> the position still applies this session (cache + accessors), just not
    # persisted; negative/oversized inputs are clamped on the way in.
    mod_settings._seed(dict(DEFAULTS))
    monkeypatch.setattr(mod_settings, "_primary_api", lambda: None)
    set_position(-5, POS_MAX + 100, w=1920, h=1080)
    assert pos_x() == 0                 # clamped
    assert pos_y() == POS_MAX           # clamped
    assert pos_w() == 1920
    assert pos_h() == 1080


def test_on_reset_forces_auto_position_and_follow_on():
    # The per-mod Reset must snap the position back to auto (0/0/0/0) and Follow Carousel Mode
    # back ON, overriding any stale pin the host reset snapshot may still carry.
    mod_settings._seed({GARAGE_KEY: True, BATTLE_KEY: True,
                        POS_X_KEY: 500, POS_Y_KEY: 300, POS_W_KEY: 1920, POS_H_KEY: 1080,
                        FOLLOW_CAROUSEL_KEY: False})
    mod_settings._on_reset(LINKAGE, {POS_X_KEY: 999, POS_Y_KEY: 888,
                                     FOLLOW_CAROUSEL_KEY: False})
    assert (pos_x(), pos_y(), pos_w(), pos_h()) == (0, 0, 0, 0)
    assert follow_carousel() is True


def test_on_reset_ignores_foreign_linkage():
    # onResetMod fires globally; a foreign mod's reset must not wipe our pin / follow flag.
    mod_settings._seed({GARAGE_KEY: True, BATTLE_KEY: True,
                        POS_X_KEY: 500, POS_Y_KEY: 300,
                        FOLLOW_CAROUSEL_KEY: False})
    mod_settings._on_reset("com.someone.othermod", {})
    assert pos_x() == 500
    assert pos_y() == 300
    assert follow_carousel() is False


def test_coerce_types_per_key():
    # Position keys coerce to clamped ints; every other key coerces to bool.
    assert mod_settings._coerce(POS_X_KEY, "640") == 640
    assert mod_settings._coerce(POS_Y_KEY, -3) == 0
    assert mod_settings._coerce(GARAGE_KEY, 0) is False
    assert mod_settings._coerce(FOLLOW_CAROUSEL_KEY, 1) is True


# --- settingsVersion-bump migration: preserve saved values across a register() bump ---------

class _FakeMsaApi(object):
    """Models Aslain MSA's settingsVersion-bump behavior for the migration path.

    getModSettings returns None while the template's settingsVersion exceeds the stored one
    (the wipe path register()'s else-branch reacts to); once setModTemplate records the new
    version it returns the current stored dict. setModTemplate resets the stored dict to the
    template's varName defaults (preserving the host-owned 'enabled' toggle) and returns them.
    The raw previously-stored values live at .state['settings'][LINKAGE] until setModTemplate
    overwrites them."""

    def __init__(self, stored=None, stored_version=0):
        settings = {LINKAGE: dict(stored)} if stored is not None else {}
        self.state = {"settings": settings, "templates": {}}
        self._stored_version = stored_version
        self.saved = 0
        self.updated = 0
        self.registered_cb = None
        self.template_cb = None

    @staticmethod
    def _defaults_from_template(template):
        d = {}
        for col in ("column1", "column2"):
            for c in template.get(col, []):
                if "varName" in c:
                    d[c["varName"]] = c.get("value")
        d["enabled"] = template.get("enabled", True)
        return d

    def getModSettings(self, linkage, template=None):
        cur = (self.state.get("settings") or {}).get(linkage)
        if cur is None:
            return None
        if template is not None and template.get("settingsVersion", 0) > self._stored_version:
            return None
        return cur

    def setModTemplate(self, linkage, template, callback):
        self.template_cb = callback
        defaults = self._defaults_from_template(template)
        prev = (self.state.get("settings") or {}).get(linkage) or {}
        if "enabled" in prev:
            defaults["enabled"] = prev["enabled"]
        self.state.setdefault("settings", {})[linkage] = defaults
        self._stored_version = template.get("settingsVersion", 0)
        return defaults

    def registerCallback(self, linkage, callback):
        self.registered_cb = callback

    def updateModSettings(self, linkage, data):
        self.updated += 1
        self.state.setdefault("settings", {})[linkage] = dict(data)

    def saveState(self):
        self.saved += 1


@pytest.fixture
def _run_register(monkeypatch):
    """Run register() against a fake api: patch _primary_api to it, neutralize the
    reset/text-sync loops (out of scope for migration), reset the one-shot _registered guard,
    and restore it after."""
    saved_registered = mod_settings._registered

    def _run(api):
        monkeypatch.setattr(mod_settings, "_primary_api", lambda: api)
        monkeypatch.setattr(mod_settings, "_candidate_apis", lambda: [])
        mod_settings._registered = False
        mod_settings.register()

    yield _run
    mod_settings._registered = saved_registered


def test_migration_preserves_user_values_drops_removed_key_and_seeds_new_default(_run_register):
    # Old v4 dict with non-default checkbox choices, a legacy key removed from the template,
    # and none of the v5 position keys -> migration must keep the survivors, drop the legacy
    # key, and leave the new position/followCarousel keys at their fresh defaults.
    old = {
        "enabled": True,
        GARAGE_KEY: False,
        BATTLE_KEY: False,
        BATTLE_ALT_KEY: True,
        COUNTED_ASSIST_KEY: True,
        "legacyGoneVarName": 7,
    }
    api = _FakeMsaApi(stored=old, stored_version=4)
    _run_register(api)

    assert mod_settings.garage_enabled() is False
    assert mod_settings.battle_enabled() is False
    assert mod_settings.battle_alt_key_enabled() is True
    assert mod_settings.counted_assistance_enabled() is True
    # New-to-v5 keys were absent from the old dict -> fresh defaults.
    assert mod_settings.pos_x() == 0 and mod_settings.pos_y() == 0
    assert mod_settings.follow_carousel() is True
    # The removed legacy key never leaks into our cache.
    assert "legacyGoneVarName" not in mod_settings._settings
    # Persisted exactly once (reset + overlay coalesce into one debounced write).
    assert api.updated == 1
    assert api.saved == 1
    written = api.state["settings"][LINKAGE]
    assert written[GARAGE_KEY] is False
    assert written[BATTLE_ALT_KEY] is True
    assert "enabled" in written and written["enabled"] is True
    assert "legacyGoneVarName" not in written


def test_migration_preserves_host_enabled_false(_run_register):
    # A user who disabled the mod via the host 'enabled' toggle must stay disabled across
    # migration (the host key survives the template reset and the re-write).
    old = {"enabled": False, GARAGE_KEY: False}
    api = _FakeMsaApi(stored=old, stored_version=4)
    _run_register(api)
    assert api.state["settings"][LINKAGE]["enabled"] is False


def test_fresh_install_yields_defaults_without_spurious_persist(_run_register):
    # No stored settings -> old_raw empty -> migration overlay skipped: defaults everywhere and
    # NO updateModSettings / saveState.
    api = _FakeMsaApi(stored=None, stored_version=0)
    _run_register(api)
    assert mod_settings.garage_enabled() is DEFAULTS[GARAGE_KEY]
    assert mod_settings.pos_x() == 0 and mod_settings.pos_y() == 0
    assert api.updated == 0
    assert api.saved == 0
    # Fresh-install path registered the template and wired its callback.
    assert api.template_cb is mod_settings._on_changed


def test_same_version_load_does_not_migrate(_run_register):
    # getModSettings returns the stored dict (version matches) -> saved-truthy branch runs
    # (_seed + registerCallback), and the migration/setModTemplate else-branch is never entered.
    stored = {"enabled": True, GARAGE_KEY: False, BATTLE_ALT_KEY: True,
              POS_X_KEY: 700, POS_Y_KEY: 300}
    api = _FakeMsaApi(stored=stored, stored_version=SETTINGS_VERSION)
    _run_register(api)
    assert mod_settings.garage_enabled() is False
    assert mod_settings.battle_alt_key_enabled() is True
    assert mod_settings.pos_x() == 700 and mod_settings.pos_y() == 300
    assert api.registered_cb is mod_settings._on_changed
    assert api.template_cb is None
    assert api.updated == 0
    assert api.saved == 0
