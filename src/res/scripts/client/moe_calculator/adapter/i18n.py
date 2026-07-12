# -*- coding: utf-8 -*-
"""Localized labels for the widget's hover tooltip -- the mod's one source of
user-facing TEXT.

To speak every language the client supports, we REUSE WoT's own already-translated
strings wherever WG ships one (resolved via helpers.i18n.makeString against the client's
active-language string table), and bundle our own translations only for the few labels
WG has no reusable string for.

Resolution is fully guarded: under pytest (no game engine) every engine call fails and we
fall back to the bundled English text, so this module imports and unit-tests on plain
Python 3. In-client, labels() returns the client-language text.

Design: labels() returns a flat {key: text} dict; the bridge JSON-encodes it into the
`labels` VM prop and the widget JS renders it by key (the JS hardcodes no English). The
keys are the wire contract -- mirror them in MoECalculator.js. Resolved once and cached
(the client language does not change mid-session).

Adapter layer: guarded engine imports, unit-testable. 2/3-compatible.
"""
from moe_calculator._compat import LOG_CURRENT_EXCEPTION

DEFAULT_LANGUAGE = "en"

# DIAGNOSTIC: when on, untranslated (English-fallback) strings are underscore-tagged so
# they stand out in-client. Off for releases. Shared by settings_i18n (the settings-panel
# translation resolver) so its English leaks flag the same way. Flip to True only for dev.
MARK_UNTRANSLATED = False


def _mark(s):
    """Tag an untranslated (English-fallback) string so it stands out in-client."""
    return (u"_" + s) if (MARK_UNTRANSLATED and s) else s

# WG resource keys we reuse (verified LIVE against the EU 2.3.0.1 client -- each renders
# real translated text, not a key echo; the client resolves each to the active language).
# Keys drift per patch -- resolution is guarded, so a dropped/renamed key degrades to the
# bundled English fallback below rather than crashing or showing a raw key.
#   title     -> "Marks of Excellence"  (the MoE achievement's own name; NOT marksOnGunHeader,
#                which renders the unrelated label "Ranks by average damage:")
#   avgDamage -> "Average Damage"
#
# The hover tooltip reproduces the client's own MoE award tooltip (Vehicle stats -> Awards),
# so its text is the client's own achievement strings, keyed by the player's mark count:
#   title0..3 -> "Marks of Excellence" / "1|2|3 Mark(s) of Excellence"  (#achievements:marksOnGun{N})
#   descr0..3 -> the how-to-earn-the-next-mark blurb / "maximum obtained" (marksOnGun{N}_descr)
#   condition -> the multi-line rules block  (#achievements:marksOnGun_condition; '\n'-separated,
#                bullet chars baked into the string -- the JS splits on '\n')
#   ratio     -> the "current ratio is higher than N% of players" template
#                (#tooltips:achievement/marksOnGunCount; has %(color_tag_open)s / %(count)s /
#                %(color_tag_close)s placeholders + a literal %% -- the JS substitutes them).
# ("marks" is bundled, not reused: the only marks-count WG string is a whole templated
# sentence -- "#tooltips:achievement/marksOnGunCount" -- unusable as a compact row label.)
_WG_KEYS = {
    "title": "#achievements:marksOnGun0",         # tooltip header = "Marks of Excellence"
    "avgDamage": "#menu:tank_params/avgDamage",    # current-readout row label
    # native MoE award-tooltip text, keyed by mark count 0..3
    "title0": "#achievements:marksOnGun0",
    "title1": "#achievements:marksOnGun1",
    "title2": "#achievements:marksOnGun2",
    "title3": "#achievements:marksOnGun3",
    "descr0": "#achievements:marksOnGun0_descr",
    "descr1": "#achievements:marksOnGun1_descr",
    "descr2": "#achievements:marksOnGun2_descr",
    "descr3": "#achievements:marksOnGun3_descr",
    "condition": "#achievements:marksOnGun_condition",
    "ratio": "#tooltips:achievement/marksOnGunCount",
}

# English fallbacks for the WG-sourced labels, used when the engine/key is unavailable
# (under pytest, or if WG drops/renames a key). Verbatim from the EU 2.3.0.1 client.
_WG_FALLBACK_EN = {
    "title": "Marks of Excellence",
    "avgDamage": "Average Damage",
    "title0": "Marks of Excellence",
    "title1": "1 Mark of Excellence",
    "title2": "2 Marks of Excellence",
    "title3": "3 Marks of Excellence",
    "descr0": "To obtain one Mark of Excellence, displayed on the gun, the average damage caused by the player and average damage caused with the player's assistance must be higher than the results of 65% of players in this vehicle for the past 14 days.",
    "descr1": "To obtain two Marks of Excellence, displayed on the gun, the average damage caused by the player and average damage caused with the player's assistance must be higher than the results of 85% of players in this vehicle for the past 14 days.",
    "descr2": "To obtain three Marks of Excellence, displayed on the gun, the average damage caused by the player and average damage caused with the player's assistance must be higher than the results of 95% of players in this vehicle for the past 14 days.",
    "descr3": "The maximum number of Marks of Excellence is obtained.",
    "condition": u"• The player's average damage is updated after each battle based on the last 100 battles. \n• Obtained Marks are permanent and do not disappear even if the player's average damage decreases.\n• Mark can only be earned in Tier V–XI vehicles.\n• Display of Marks on your vehicles can be disabled in the game settings.\n• Marks can only be obtained in Random Battles.",
    "ratio": u"Current ratio is higher than the ratio of %(color_tag_open)s %(count)s%% %(color_tag_close)s\nplayers who fought in this vehicle for the past 14 days.",
}

# Our own strings, for concepts WG ships no reusable atom for. English is the fallback for
# any language not listed; ship the audience languages, degrade to en otherwise.
_BUNDLED = {
    # Marks-count row label. WG ships no compact "Marks" atom (its only marks string is a
    # full templated sentence), so we bundle it -- using the same mark-noun each language
    # already uses in "toNextMark" below, for internal consistency.
    "marks": {
        "en": "Marks",
        "ru": u"Отметки",
        "de": u"Marken",
        "pl": u"Znaki",
        "uk": u"Позначки",
    },
    "toNextMark": {
        "en": "To next mark",
        "ru": u"До следующей отметки",
        "de": u"Bis zur nächsten Marke",
        "pl": u"Do następnego znaku",
        "uk": u"До наступної позначки",
    },
    "goal": {
        "en": "Goal",
        "ru": u"Цель",
        "de": u"Ziel",
        "pl": u"Cel",
        "uk": u"Ціль",
    },
}

_cache = None


def _client_language():
    """The client's language code ('en'/'ru'/...), or DEFAULT_LANGUAGE out of client."""
    try:
        from helpers import getClientLanguage
        lang = getClientLanguage()
        return lang or DEFAULT_LANGUAGE
    except Exception:
        return DEFAULT_LANGUAGE


def _wg_text(res_key):
    """Resolve a WG resource key to client-language text, or None if unavailable.

    On a miss, makeString does NOT return the full "#ns:key" -- the live EU 2.3.0.1 client
    echoes back just the key TAIL (the part after the ':', e.g. "#achievements:foo" -> "foo").
    So a leading '#' is not a reliable miss signal; we also treat an exact tail-echo as a
    miss. A real translation equal to its own key tail is implausible for our keys."""
    try:
        from helpers import i18n
        text = i18n.makeString(res_key)
        if not text or text.startswith("#"):
            return None
        tail = res_key.split(":", 1)[1] if ":" in res_key else res_key
        if text == tail:
            return None
        return text
    except Exception:
        LOG_CURRENT_EXCEPTION()
    return None


def _bundled(key, lang):
    """Bundled translation for `key` in `lang`, falling back to English, then ''."""
    variants = _BUNDLED.get(key, {})
    return variants.get(lang) or variants.get(DEFAULT_LANGUAGE, "")


def labels():
    """Flat {key: localized text} dict for the tooltip. Resolved once, then cached."""
    global _cache
    if _cache is not None:
        return _cache
    lang = _client_language()
    out = {}
    for key, res_key in _WG_KEYS.items():
        out[key] = _wg_text(res_key) or _WG_FALLBACK_EN[key]
    for key in _BUNDLED:
        out[key] = _bundled(key, lang)
    _cache = out
    return out


def reset_cache():
    """Drop the cached resolution (tests; or a forced language change)."""
    global _cache
    _cache = None
