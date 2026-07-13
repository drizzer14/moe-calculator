# -*- coding: utf-8 -*-
"""Localize the mod's OWN settings-panel prose with bundled translation tables.

The ModsSettingsAPI panel (see ``bridge/mod_settings.py``) is the one user-facing
surface the mod can't localize through the game's resource strings: its two checkbox
labels and tooltips are mod-invented prose with no in-game equivalent (unlike the widget
text, which ``adapter/i18n.py`` resolves by reusing WG's own strings -- see that module).
So we ship our own ``{lang: {key: entry}}`` tables and pick the block matching the client's
active language, exactly the pattern the wotmod-architecture skill recommends for a mod's
own strings. Mirrors the sibling Garage Progress Bar mod's ``settings_i18n`` mechanism.

Everything here is PURE and unit-tested EXCEPT ``client_language()`` -- the one call
that reads the engine (``helpers.getClientLanguage()``), guarded so the module still
imports (and the resolver still runs) under pytest with the game closed.

English (``_PANEL['en']``) is the always-complete master. Every other language is
overlaid onto it PER KEY: a key a language hasn't translated falls back to the English
text for that key alone (and is underscore-marked when ``i18n.MARK_UNTRANSLATED`` is on,
matching the widget's diagnostic). An unknown client code degrades to full English.

NOTE on terminology: the non-English blocks use each locale's natural wording for
"widget", "Garage", "battle" and "Marks of Excellence". The official Marks-of-Excellence
noun per language is still worth a spot-check against a running client before a release; the
mechanism supports any code and never breaks on an unverified one.

Ukrainian code CONFIRMED: the EU 2.3.0.1 client's ``#settings:LANGUAGE_CODE`` resolves to
``'uk'`` (verified against ``res/text/lc_messages/settings.mo`` + the client's own
``dog_tag_composer.SUPPORTED_LANGUAGES``, which lists ``'uk'``, never ``'ua'``). So the
``'uk'`` table key matches ``getClientLanguage()`` directly; the ``ua`` alias below never
fires on this client and is kept only as defense for an odd client build.
"""
from moe_calculator._compat import LOG_CURRENT_EXCEPTION
from moe_calculator.adapter import i18n

# The default client language + the value returned when the engine read fails.
DEFAULT_LANGUAGE = u"en"

# getClientLanguage() code quirks -> our table keys. The EU client returns 'uk' for
# Ukrainian (confirmed -- see module docstring), so this ua->uk alias is defensive only;
# extend if a client variant surfaces a non-standard code (Chinese/Portuguese, region suffix).
_ALIASES = {
    u"ua": u"uk",
}


def _norm(code):
    """Normalize a client language code to a table key (pure, engine-free).

    ``None``/empty -> u"". Otherwise lowercase, ``-`` -> ``_``, apply ``_ALIASES``, and
    if the full code isn't a known block fall back to the primary subtag
    (``"pt_br"`` -> ``"pt"``). The result is not guaranteed to be a ``_PANEL`` key --
    ``resolve`` treats an unknown key as "English"."""
    if not code:
        return u""
    c = code.strip().lower().replace(u"-", u"_")
    c = _ALIASES.get(c, c)
    if c in _PANEL:
        return c
    # Try the primary subtag (before the first "_"), also through the alias map.
    base = c.split(u"_", 1)[0]
    base = _ALIASES.get(base, base)
    return base


def _row(label, header=None, body=None):
    """A panel entry: a label plus an optional (header, body) tooltip. Parts are kept
    separate so the ``{HEADER}/{BODY}`` markup is assembled ONCE in ``_render`` rather
    than baked into every translation string."""
    e = {u"label": label}
    if header is not None or body is not None:
        e[u"ttHeader"] = header or u""
        e[u"ttBody"] = body or u""
    return e


# Ordered key list for the single column -- the wire order of the controls in the MSA
# template. Used by mod_settings to walk a stored template in lockstep. There is no second
# column (COL2_KEYS empty), unlike the sibling's position steppers.
COL1_KEYS = (u"garageWidget", u"battleWidget", u"battleAltKey", u"countedAssist")
COL2_KEYS = ()


# The translation tables, lang-major so each language is one contiguous, translator-
# editable block. 'en' is the master (every key present); the rest are overlaid per key.
_PANEL = {
    u"en": {
        u"garageWidget": _row(
            u"Garage Widget Enabled", u"Garage widget",
            u"Shows the Marks of Excellence percentile bar in the Garage, on the "
            u"selected vehicle. Uncheck to hide it."),
        u"battleWidget": _row(
            u"Battle Widget Enabled", u"Battle widget",
            u"Shows the live Marks of Excellence overlay during battle. Uncheck to "
            u"hide it."),
        u"battleAltKey": _row(
            u"Battle Widget on Alt Key", u"Battle widget (Alt)",
            u"Shows the live Marks of Excellence overlay only while the Alt key is "
            u"held. Has no effect while Battle Widget Enabled is on."),
        u"countedAssist": _row(
            u"Enable Counted Assistance", u"Counted assistance",
            u"Adds a third row to the battle overlay showing your counted assistance: the "
            u"higher of tracking, spotting or stun assist, with an icon for whichever is "
            u"leading. Off by default."),
    },

    u"de": {
        u"garageWidget": _row(
            u"Garage-Widget aktiviert", u"Garage-Widget",
            u"Zeigt die Marken-Prozentanzeige in der Garage beim ausgewählten Fahrzeug. "
            u"Zum Ausblenden abwählen."),
        u"battleWidget": _row(
            u"Gefechts-Widget aktiviert", u"Gefechts-Widget",
            u"Zeigt die Live-Marken-Anzeige im Gefecht. Zum Ausblenden abwählen."),
        u"battleAltKey": _row(
            u"Gefechts-Widget auf Alt-Taste", u"Gefechts-Widget (Alt)",
            u"Zeigt die Live-Marken-Anzeige nur, solange die Alt-Taste gehalten wird. "
            u"Ohne Wirkung, wenn „Gefechts-Widget aktiviert“ an ist."),
        u"countedAssist": _row(
            u"Angerechnete Unterstützung aktiviert", u"Angerechnete Unterstützung",
            u"Fügt der Gefechtsanzeige eine dritte Zeile mit deiner angerechneten "
            u"Unterstützung hinzu: dem höheren Wert aus Ketten-, Aufklärungs- oder "
            u"Betäubungsunterstützung, mit einem Symbol für den führenden Wert. "
            u"Standardmäßig aus."),
    },

    u"fr": {
        u"garageWidget": _row(
            u"Widget du garage activé", u"Widget du garage",
            u"Affiche la barre de centile des marques d'excellence dans le garage, sur le "
            u"véhicule sélectionné. Décochez pour la masquer."),
        u"battleWidget": _row(
            u"Widget de bataille activé", u"Widget de bataille",
            u"Affiche la superposition des marques d'excellence en direct pendant la "
            u"bataille. Décochez pour la masquer."),
        u"battleAltKey": _row(
            u"Widget de bataille sur la touche Alt", u"Widget de bataille (Alt)",
            u"Affiche la superposition des marques d'excellence en direct uniquement "
            u"tant que la touche Alt est maintenue. Sans effet lorsque « Widget de "
            u"bataille activé » est activé."),
        u"countedAssist": _row(
            u"Assistance comptabilisée activée", u"Assistance comptabilisée",
            u"Ajoute une troisième ligne à la superposition de bataille indiquant votre "
            u"assistance comptabilisée : la plus élevée entre l'assistance par chenilles, "
            u"par détection ou par étourdissement, avec une icône pour celle qui domine. "
            u"Désactivé par défaut."),
    },

    u"es": {
        u"garageWidget": _row(
            u"Widget del garaje activado", u"Widget del garaje",
            u"Muestra la barra de percentil de las marcas de excelencia en el garaje, en "
            u"el vehículo seleccionado. Desmarca para ocultarla."),
        u"battleWidget": _row(
            u"Widget de batalla activado", u"Widget de batalla",
            u"Muestra la superposición de marcas de excelencia en directo durante la "
            u"batalla. Desmarca para ocultarla."),
        u"battleAltKey": _row(
            u"Widget de batalla con la tecla Alt", u"Widget de batalla (Alt)",
            u"Muestra la superposición de marcas de excelencia en directo solo mientras "
            u"se mantiene pulsada la tecla Alt. No tiene efecto cuando «Widget de "
            u"batalla activado» está activo."),
        u"countedAssist": _row(
            u"Asistencia contada activada", u"Asistencia contada",
            u"Añade una tercera fila a la superposición de batalla que muestra tu "
            u"asistencia contada: la mayor entre la asistencia por orugas, por detección "
            u"o por aturdimiento, con un icono para la que predomine. Desactivado por "
            u"defecto."),
    },

    u"it": {
        u"garageWidget": _row(
            u"Widget del garage attivo", u"Widget del garage",
            u"Mostra la barra di percentile dei marchi di merito nel garage, sul veicolo "
            u"selezionato. Deseleziona per nasconderla."),
        u"battleWidget": _row(
            u"Widget di battaglia attivo", u"Widget di battaglia",
            u"Mostra la sovrapposizione dei marchi di merito in tempo reale durante la "
            u"battaglia. Deseleziona per nasconderla."),
        u"battleAltKey": _row(
            u"Widget di battaglia con il tasto Alt", u"Widget di battaglia (Alt)",
            u"Mostra la sovrapposizione dei marchi di merito in tempo reale solo mentre "
            u"si tiene premuto il tasto Alt. Nessun effetto quando «Widget di battaglia "
            u"attivo» è attivo."),
        u"countedAssist": _row(
            u"Assistenza conteggiata attiva", u"Assistenza conteggiata",
            u"Aggiunge una terza riga alla sovrapposizione di battaglia che mostra la tua "
            u"assistenza conteggiata: la più alta tra assistenza ai cingoli, "
            u"all'avvistamento o allo stordimento, con un'icona per quella prevalente. "
            u"Disattivato per impostazione predefinita."),
    },

    u"pl": {
        u"garageWidget": _row(
            u"Widżet w garażu włączony", u"Widżet w garażu",
            u"Pokazuje pasek percentyla znaków doskonałości w garażu, na wybranym "
            u"pojeździe. Odznacz, aby ukryć."),
        u"battleWidget": _row(
            u"Widżet w bitwie włączony", u"Widżet w bitwie",
            u"Pokazuje nakładkę znaków doskonałości na żywo podczas bitwy. Odznacz, aby "
            u"ukryć."),
        u"battleAltKey": _row(
            u"Widżet w bitwie na klawiszu Alt", u"Widżet w bitwie (Alt)",
            u"Pokazuje nakładkę znaków doskonałości na żywo tylko podczas przytrzymania "
            u"klawisza Alt. Nie działa, gdy „Widżet w bitwie włączony“ jest włączony."),
        u"countedAssist": _row(
            u"Zaliczone wsparcie włączone", u"Zaliczone wsparcie",
            u"Dodaje trzeci wiersz nakładki bitewnej pokazujący twoje zaliczone wsparcie: "
            u"wyższą z wartości wsparcia przez unieruchomienie, wykrycie lub ogłuszenie, z "
            u"ikoną dla przeważającej. Domyślnie wyłączone."),
    },

    u"cs": {
        u"garageWidget": _row(
            u"Widget v garáži zapnutý", u"Widget v garáži",
            u"Zobrazuje percentilovou lištu znaků cti v garáži u vybraného vozidla. "
            u"Zrušením zaškrtnutí ji skryjete."),
        u"battleWidget": _row(
            u"Widget v bitvě zapnutý", u"Widget v bitvě",
            u"Zobrazuje živý překryv znaků cti během bitvy. Zrušením zaškrtnutí jej "
            u"skryjete."),
        u"battleAltKey": _row(
            u"Widget v bitvě na klávese Alt", u"Widget v bitvě (Alt)",
            u"Zobrazuje živý překryv znaků cti pouze při podržení klávesy Alt. Nemá "
            u"účinek, když je zapnuto „Widget v bitvě zapnutý“."),
        u"countedAssist": _row(
            u"Započtená asistence zapnuta", u"Započtená asistence",
            u"Přidá do bojového překryvu třetí řádek zobrazující tvou započtenou "
            u"asistenci: vyšší z asistence pásy, průzkumem nebo omráčením, s ikonou pro "
            u"převažující. Ve výchozím nastavení vypnuto."),
    },

    u"ru": {
        u"garageWidget": _row(
            u"Виджет в ангаре включён", u"Виджет в ангаре",
            u"Показывает полосу процентиля отметок классности в ангаре на выбранной "
            u"машине. Снимите галочку, чтобы скрыть."),
        u"battleWidget": _row(
            u"Виджет в бою включён", u"Виджет в бою",
            u"Показывает наложение отметок классности в реальном времени в бою. Снимите "
            u"галочку, чтобы скрыть."),
        u"battleAltKey": _row(
            u"Виджет в бою по клавише Alt", u"Виджет в бою (Alt)",
            u"Показывает наложение отметок классности в реальном времени только пока "
            u"удерживается клавиша Alt. Не действует, когда включён «Виджет в бою»."),
        u"countedAssist": _row(
            u"Засчитанное содействие включено", u"Засчитанное содействие",
            u"Добавляет в наложение боя третью строку с вашим засчитанным содействием: "
            u"большее из содействия гусеницами, разведкой или оглушением, со значком для "
            u"преобладающего. По умолчанию выключено."),
    },

    u"uk": {
        u"garageWidget": _row(
            u"Віджет в ангарі увімкнено", u"Віджет в ангарі",
            u"Показує смугу процентиля позначок класності в ангарі на вибраній машині. "
            u"Зніміть позначку, щоб сховати."),
        u"battleWidget": _row(
            u"Віджет у бою увімкнено", u"Віджет у бою",
            u"Показує накладання позначок класності в реальному часі в бою. Зніміть "
            u"позначку, щоб сховати."),
        u"battleAltKey": _row(
            u"Віджет у бою по клавіші Alt", u"Віджет у бою (Alt)",
            u"Показує накладання позначок класності в реальному часі лише поки "
            u"утримується клавіша Alt. Не діє, коли увімкнено «Віджет у бою»."),
        u"countedAssist": _row(
            u"Увімкнути зараховану допомогу", u"Зарахована допомога",
            u"Додає третій рядок до накладання в бою: показує зараховану допомогу — більше "
            u"з допомоги гусеницями, засвітом чи оглушенням, з піктограмою відповідного "
            u"типу. Вимкнено за замовчуванням."),
    },

    u"hu": {
        u"garageWidget": _row(
            u"Garázs-widget engedélyezve", u"Garázs-widget",
            u"Megjeleníti a kiválósági jelek percentilis sávját a garázsban, a "
            u"kiválasztott járművön. Vedd ki a pipát az elrejtéshez."),
        u"battleWidget": _row(
            u"Csata-widget engedélyezve", u"Csata-widget",
            u"Megjeleníti az élő kiválósági jelek átfedést a csatában. Vedd ki a pipát az "
            u"elrejtéshez."),
        u"battleAltKey": _row(
            u"Csata-widget az Alt billentyűre", u"Csata-widget (Alt)",
            u"Csak az Alt billentyű nyomva tartása közben jeleníti meg az élő kiválósági "
            u"jelek átfedést. Nincs hatása, ha a „Csata-widget engedélyezve“ be van "
            u"kapcsolva."),
        u"countedAssist": _row(
            u"Beszámított segítés engedélyezve", u"Beszámított segítés",
            u"Egy harmadik sort ad a csataátfedéshez, amely a beszámított segítésedet "
            u"mutatja: a lánctalpas, felderítő vagy kábító segítés közül a nagyobbat, a "
            u"vezető típus ikonjával. Alapértelmezetten kikapcsolva."),
    },

    u"tr": {
        u"garageWidget": _row(
            u"Garaj widget'ı etkin", u"Garaj widget'ı",
            u"Seçili araçta, garajda üstünlük işaretleri yüzdelik çubuğunu gösterir. "
            u"Gizlemek için işareti kaldır."),
        u"battleWidget": _row(
            u"Savaş widget'ı etkin", u"Savaş widget'ı",
            u"Savaş sırasında canlı üstünlük işaretleri katmanını gösterir. Gizlemek için "
            u"işareti kaldır."),
        u"battleAltKey": _row(
            u"Alt tuşuyla savaş widget'ı", u"Savaş widget'ı (Alt)",
            u"Canlı üstünlük işaretleri katmanını yalnızca Alt tuşu basılı tutulurken "
            u"gösterir. „Savaş widget'ı etkin“ açıkken etkisi yoktur."),
        u"countedAssist": _row(
            u"Sayılan yardım etkin", u"Sayılan yardım",
            u"Savaş katmanına, sayılan yardımını gösteren üçüncü bir satır ekler: palet, "
            u"tespit veya sersemletme yardımından en yükseği, öndeki için bir simgeyle. "
            u"Varsayılan olarak kapalı."),
    },
}


def resolve(lang):
    """The merged ``{key: entry}`` for ``lang`` (PURE, engine-free -- the testable core).

    Each key comes from ``lang``'s block if present, else falls back to the English
    entry FOR THAT KEY. An unknown/empty code yields the full English bundle."""
    en = _PANEL[DEFAULT_LANGUAGE]
    tbl = _PANEL.get(_norm(lang)) or {}
    out = {}
    for k in en:
        out[k] = tbl.get(k, en[k])
    return out


def _render(entry, mark=False):
    """Turn one panel ``entry`` into the ``{"text", "tooltip"}`` the MSA template wants,
    assembling the ``{HEADER}/{BODY}`` markup once. A label-only entry (no ``tt*``) has
    no ``tooltip`` key. When ``mark`` (an English fallback and ``i18n.MARK_UNTRANSLATED``
    is on) the text/tooltip are underscore-tagged, matching the widget's diagnostic."""
    out = {u"text": entry.get(u"label", u"")}
    if u"ttHeader" in entry or u"ttBody" in entry:
        out[u"tooltip"] = u"{HEADER}%s{/HEADER}{BODY}%s{/BODY}" % (
            entry.get(u"ttHeader", u""), entry.get(u"ttBody", u""))
    if mark:
        out[u"text"] = i18n._mark(out[u"text"])
        if u"tooltip" in out:
            out[u"tooltip"] = i18n._mark(out[u"tooltip"])
    return out


def build(lang):
    """The rendered panel text for ``lang``: ``{key: {"text", "tooltip"}}`` (PURE).

    A key the language didn't translate is rendered from English and marked (when
    ``i18n.MARK_UNTRANSLATED`` is on) so English leaks are spottable in-client."""
    en = _PANEL[DEFAULT_LANGUAGE]
    tbl = _PANEL.get(_norm(lang)) or {}
    out = {}
    for k, en_entry in en.items():
        translated = k in tbl
        out[k] = _render(tbl.get(k, en_entry), mark=not translated)
    return out


def client_language():
    """The client's active language code, normalized to a table key -- the ONE engine
    read here. Guarded + lazy-imported so the module still imports under pytest and a
    missing/renamed helper degrades to English rather than raising into MSA setup."""
    try:
        import helpers
        return _norm(helpers.getClientLanguage()) or DEFAULT_LANGUAGE
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return DEFAULT_LANGUAGE


def panel_text():
    """The rendered panel text for the CLIENT's active language (public entry point for
    mod_settings). English on any read failure."""
    return build(client_language())
