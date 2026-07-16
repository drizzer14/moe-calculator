# -*- coding: utf-8 -*-
"""The four user settings, laid out as two columns in the MSA panel: an "In-Battle Widget"
master (column 1) grouped with its "Show on Alt Key" + "Counted Assistance" children, and a
standalone "In-Garage Widget" checkbox (column 2).

Surfaced as ModsSettingsAPI (MSA) checkboxes in the game's in-game mod-settings menu. MSA
(Aslain's gui.aslainMenu preferred, izeberg.modssettingsapi as a legacy fallback) is a SOFT
dependency: we import it guarded, and if it is absent the mod simply uses the defaults (both
widgets enabled) with no settings panel -- never a crash. MSA owns persistence, so there is
no config file of ours.

This module owns the flag state and fans a change out to per-feature ``apply_settings``
callbacks (registered by the entry point). It imports NOTHING from the sibling bridges, so
``gameface_bridge`` / ``battle_bridge`` can import it for the flag getters without a cycle.

Panel prose is localized: every visible label/tooltip is pulled from
``settings_i18n.panel_text()`` at the client's active language (English fallback per key --
see that module). The control STRUCTURE (types, varNames, values, settingsVersion) is
language-independent; only the text follows the language. ``modDisplayName`` stays the
literal English brand.

``merge_settings`` is pure so it unit-tests without the game (defaults, partial dict, unknown
keys, reset, version drift).
"""
from moe_calculator._compat import LOG_CURRENT_EXCEPTION, LOG_DEBUG
from moe_calculator.adapter import settings_i18n

# MSA store key for this mod (reverse-domain id). Stable across versions so saved checkbox
# state survives upgrades.
LINKAGE = "com.14th_ua.moe_calculator"
MOD_DISPLAY_NAME = "14th_ua's MoE Calculator"

# Bump ONLY when the control layout / varName set changes (the host wipes saved values to
# defaults on a bump). Localizing text is text-only -- it does NOT bump this (the stored
# template text is refreshed in place by _sync_template_text instead).
SETTINGS_VERSION = 4

GARAGE_KEY = "garage_widget_enabled"
BATTLE_KEY = "battle_widget_enabled"
# The in-battle overlay's Alt-key mode, a CHILD of BATTLE_KEY (grouped under it via
# createControlsGroup): show the overlay only while Alt is held; when off the overlay is shown
# at all times. It has effect ONLY while BATTLE_KEY is on -- with the master off the overlay is
# never shown, so the child is inert (and MSA greys it out under the group). See
# battle_bar_visible: active == battle_enabled and (alt_held if alt_mode else True).
BATTLE_ALT_KEY = "battle_widget_alt_key"
# Optional third in-battle row: "counted assistance" = the higher of tracking / spotting / stun
# assist this battle (the assist that MoE credits). Opt-in (default OFF).
COUNTED_ASSIST_KEY = "counted_assistance_enabled"

# The two widgets ship ON; the Alt-peek mode and the counted-assistance row ship OFF (opt-in).
# merge_settings only ever overlays these known keys, so an MSA store from a newer/older template
# can never introduce or drop a flag we act on.
DEFAULTS = {GARAGE_KEY: True, BATTLE_KEY: True, BATTLE_ALT_KEY: False,
            COUNTED_ASSIST_KEY: False}

# Live flag state (seeded from MSA in register(); defaults until then / if MSA is absent).
_settings = dict(DEFAULTS)

# apply_settings callbacks the entry point subscribes (one per feature bridge).
_listeners = []

# True once we've registered with MSA. Kept so register() is idempotent AND self-healing:
# a failed attempt (MSA not loaded yet at our import time -- our id sorts before izeberg's)
# leaves this False, so a later register() (first hangar mount) retries until it sticks.
_registered = False


def merge_settings(saved):
    """Overlay only the known keys from `saved` onto DEFAULTS, coercing to bool. Pure.

    Tolerates None / non-dict / partial dicts / unknown extra keys (MSA replaces the whole
    dict, so a stale or foreign store must degrade to safe defaults, never raise)."""
    out = dict(DEFAULTS)
    if isinstance(saved, dict):
        for key in DEFAULTS:
            if key in saved:
                out[key] = bool(saved[key])
    return out


def garage_enabled():
    """Whether the hangar percentile-bar widget is enabled (default True)."""
    return bool(_settings.get(GARAGE_KEY, True))


def battle_enabled():
    """Whether the in-battle overlay is enabled (default True)."""
    return bool(_settings.get(BATTLE_KEY, True))


def battle_alt_key_enabled():
    """Whether the "show only while Alt held" peek mode is enabled (default False).

    Independent of battle_enabled(): the consumer (battle_bar_visible) applies the soft-gate
    so this is ignored while battle_enabled() is on."""
    return bool(_settings.get(BATTLE_ALT_KEY, False))


def counted_assistance_enabled():
    """Whether the optional in-battle "counted assistance" row is enabled (default False)."""
    return bool(_settings.get(COUNTED_ASSIST_KEY, False))


def add_change_listener(fn):
    """Register a zero-arg callback invoked (guarded) after the flags change."""
    if fn not in _listeners:
        _listeners.append(fn)


def _notify():
    for fn in list(_listeners):
        try:
            fn()
        except Exception:
            LOG_CURRENT_EXCEPTION()


def _seed(saved):
    """Replace the WHOLE flag state from an AUTHORITATIVE store (registration only), filling
    defaults for any key it omits. Used where `saved` fully defines our state."""
    global _settings
    _settings = merge_settings(saved)


def _apply(saved):
    """Overlay only the PRESENT known keys from `saved` onto the live cache IN PLACE; a key
    ABSENT from `saved` keeps its current value.

    This is the live-change path, and preserving current values is load-bearing: MSA fires the
    onSettingsChanged callback GLOBALLY, so `_on_changed` also runs for OTHER mods' changes,
    handed a payload that contains none of OUR keys. Merging that onto DEFAULTS (as a naive
    replace would) snapped every flag back to its default -- the bug where a foreign mod's
    settings sync silently re-enabled the always-on battle overlay, so it ignored
    "Battle Widget Enabled = off" + "on Alt Key = on". A foreign payload now no-ops here."""
    if not isinstance(saved, dict):
        return
    for key in DEFAULTS:
        if key in saved:
            _settings[key] = bool(saved[key])


def _checkbox(key, rendered):
    """One MSA CheckBox descriptor. `varName` matches a DEFAULTS key so the dict MSA returns
    maps straight through merge_settings; text/tooltip come from settings_i18n (English
    fallback per key)."""
    return {
        "type": "CheckBox",
        "text": rendered["text"],
        "value": DEFAULTS[key],
        "tooltip": rendered["tooltip"],
        "varName": key,
    }


def _grouped_column1(master, children):
    """Column 1 = the "In-Battle Widget" master with its two indented children, greyed out
    while the master is off.

    Prefer Aslain's templates.createControlsGroup(master, children, indent=True) -- it returns
    the flat [master, child1, child2] list and binds each child to the master (a masterVarName
    key = master's varName; the panel disables + indents the children while the master is off).
    FEATURE-DETECT + degrade: if that helper is absent (older MSA / izeberg fallback) we set
    masterVarName by hand -- which is exactly what the helper does -- so the children still list
    under the master and older builds that ignore the key simply show them as plain checkboxes."""
    try:
        from gui.aslainMenu import templates
        return templates.createControlsGroup(master, children, indent=True)
    except Exception:
        for child in children:
            child["masterVarName"] = master["varName"]
        return [master] + list(children)


def _template():
    """The MSA panel descriptor. Column 1 is the "In-Battle Widget" master grouped with its
    "Show on Alt Key" + "Counted Assistance" children; column 2 is the standalone "In-Garage
    Widget" checkbox. Every visible label/tooltip comes from settings_i18n at the client's
    language (English fallback)."""
    t = settings_i18n.panel_text()
    battle_master = _checkbox(BATTLE_KEY, t["battleWidget"])
    battle_alt = _checkbox(BATTLE_ALT_KEY, t["battleAltKey"])
    counted = _checkbox(COUNTED_ASSIST_KEY, t["countedAssist"])
    garage = _checkbox(GARAGE_KEY, t["garageWidget"])
    return {
        "modDisplayName": MOD_DISPLAY_NAME,
        "enabled": True,
        "settingsVersion": SETTINGS_VERSION,
        "column1": _grouped_column1(battle_master, [battle_alt, counted]),
        "column2": [garage],
    }


def _candidate_apis():
    """The settings-api instance(s) this client exposes, in PREFERENCE order. Aslain's
    gui.aslainMenu is probed FIRST (that is where the user's data now lives) with izeberg's
    gui.modsSettingsApi as the legacy fallback -- so a lingering izeberg install can never win
    over Aslain. With both present there are TWO separate objects; on a plain install just one.
    Return whichever import(s) succeed, de-duped, primary first."""
    apis = []
    try:
        from gui.aslainMenu import g_modsSettingsApi as a
        apis.append(a)
    except Exception:
        pass
    try:
        from gui.modsSettingsApi import g_modsSettingsApi as b
        if b not in apis:
            apis.append(b)
    except Exception:
        pass
    return apis


def _primary_api():
    """The preferred settings-api instance (Aslain first, else izeberg), or None if MSA is
    absent. This is the object register() drives getModSettings/setModTemplate/registerCallback
    through."""
    apis = _candidate_apis()
    return apis[0] if apis else None


def _sync_template_text(api):
    """Refresh a stored template's label/tooltip text to the client's active language.

    MSA stores a COPY of the template text at registration and renders from it; on an
    EXISTING install register() takes the saved-truthy branch and never re-applies the
    template text, so a language change would otherwise never show. This walks the stored
    template in lockstep with settings_i18n's column key order and overwrites each entry's
    text/tooltip from panel_text(), saving only if something changed. Idempotent: a no-op on
    a fresh install (text already matches). Guarded; text-only, no settingsVersion bump."""
    try:
        tmpl = (getattr(api, "state", None) or {}).get("templates", {}).get(LINKAGE)
        if not isinstance(tmpl, dict):
            return
        t = settings_i18n.panel_text()
        changed = False
        for col, keys in (("column1", settings_i18n.COL1_KEYS),
                          ("column2", settings_i18n.COL2_KEYS)):
            for comp, key in zip(tmpl.get(col) or [], keys):
                rendered = t.get(key) if isinstance(comp, dict) else None
                if not rendered:
                    continue
                if comp.get("text") != rendered["text"]:
                    comp["text"] = rendered["text"]
                    changed = True
                tip = rendered.get("tooltip")
                if tip is not None and comp.get("tooltip") != tip:
                    comp["tooltip"] = tip
                    changed = True
        if changed and hasattr(api, "saveState"):
            api.saveState()
            LOG_DEBUG("[moe] synced settings template text to client language")
    except Exception:
        LOG_CURRENT_EXCEPTION()


# Object ids of api instances we've already hooked onResetMod on, so retries never stack
# duplicate handlers.
_reset_hooked = set()


def _subscribe_reset(api):
    """Subscribe _on_reset to an api's onResetMod event (the panel 'reset to defaults'
    button, which fires onResetMod -- NOT onSettingsChanged), de-duped by object id. No-op if
    the api lacks onResetMod (pure izeberg) or is already hooked."""
    try:
        if api is None or not hasattr(api, "onResetMod"):
            return
        if id(api) in _reset_hooked:
            return
        api.onResetMod += _on_reset
        _reset_hooked.add(id(api))
    except Exception:
        LOG_CURRENT_EXCEPTION()


def register():
    """Register (or re-load) the settings panel with MSA and seed the flag state.

    Soft + idempotent + self-healing: a no-op once registered; if MSA is absent it
    logs-and-returns with defaults intact; MSA may load after us at startup, so a first
    failed attempt is retried on the first hangar mount. Guarded so it never raises into the
    mount path."""
    global _registered
    if _registered:
        return
    g_modsSettingsApi = _primary_api()
    if g_modsSettingsApi is None:
        LOG_DEBUG("[moe] ModsSettingsAPI absent -> both widgets default enabled")
        return
    try:
        template = _template()
        saved = g_modsSettingsApi.getModSettings(LINKAGE, template)
        if saved:
            _seed(saved)
            g_modsSettingsApi.registerCallback(LINKAGE, _on_changed)
        else:
            _seed(g_modsSettingsApi.setModTemplate(LINKAGE, template, _on_changed))
        # Wire the panel's "reset to defaults" button on whichever api(s) store our settings
        # (Aslain keeps a SEPARATE api object from izeberg's; subscribe on both, de-duped).
        for api in _candidate_apis():
            _subscribe_reset(api)
        # Refresh the stored template text to the client's active language (required for an
        # existing install whose stored template is a stale language). No-op on a fresh one.
        for api in _candidate_apis():
            _sync_template_text(api)
        _registered = True
        LOG_DEBUG("[moe] settings registered -> %r" % (_settings,))
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _on_changed(linkage, new_settings):
    """MSA onSettingsChanged callback: overlay our keys and fan out to the feature bridges so a
    checkbox change applies live.

    Linkage-scoped: MSA broadcasts this callback GLOBALLY (it fires for every mod's change, not
    just ours), so ignore events for other mods -- mirrors _on_reset. Even without the guard the
    _apply overlay would no-op a foreign payload, but skipping early also avoids a spurious
    _notify()/re-push and any chance of a foreign key colliding with one of ours."""
    try:
        if linkage != LINKAGE:
            return
        _apply(new_settings)
        LOG_DEBUG("[moe] settings changed -> %r" % (_settings,))
        _notify()
    except Exception:
        LOG_CURRENT_EXCEPTION()


def _on_reset(linkage, defaults):
    """Panel 'reset to defaults' button. The host fires onResetMod (NOT onSettingsChanged),
    globally across every mod, so this is linkage-scoped. Restore our defaults and fan out."""
    try:
        if linkage != LINKAGE:
            return
        _seed(defaults if defaults else DEFAULTS)
        LOG_DEBUG("[moe] settings reset -> %r" % (_settings,))
        _notify()
    except Exception:
        LOG_CURRENT_EXCEPTION()
