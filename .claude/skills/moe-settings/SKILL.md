---
name: moe-settings
description: Use when editing the 14th_ua MoE Calculator's SETTINGS subsystem — the ModsSettingsAPI (MSA) panel, its 4 checkboxes (garage widget, battle widget, Alt-key peek, Counted Assistance), the flag getters the feature bridges read, MSA registration / soft-dep / self-heal, or why a foreign mod's settings change must not touch our flags. For the panel prose translation see the harness skill wotmod-i18n-settings; for feature internals see moe-garage / moe-battle.
---

# MoE Calculator — settings panel (feature)

The mod's four user toggles, surfaced as ModsSettingsAPI (MSA) checkboxes in the in-game
mod-settings menu. Shared mechanics live in the harness: **MSA structure, the replace-not-merge
rule, and `saveState`** → `wotmod-architecture` (ModsSettingsAPI); **panel-prose localization,
`_sync_template_text`, `getClientLanguage` + the `uk`-not-`ua` quirk** → `wotmod-i18n-settings`.
This skill is only the mod's concretes. All paths under `src/res/scripts/client/moe_calculator/`.

Owner module: `bridge/mod_settings.py` (flag state + MSA registration). Prose: `adapter/settings_i18n.py`.

## The 4 controls (two-column grouped panel)

`SETTINGS_VERSION = 4`. Each `varName` == the `DEFAULTS` key, so the dict MSA returns maps
straight through `merge_settings`. Bump `SETTINGS_VERSION` **only** when the control layout /
varName set changes (the host wipes saved values back to the unchanged defaults on a bump) —
localizing text is text-only and does NOT bump it. (The 3→4 bump was this two-column
restructure.)

The panel is **two columns**, built in `_template()`:
- **column1 = "In-Battle Widget"** — the `battle_widget_enabled` master grouped via
  `_grouped_column1()` (→ `templates.createControlsGroup(master, children, indent=True)`) with
  two **indented children** that grey out while the master is off: "Show on Alt Key" and
  "Counted Assistance". Feature-detect fallback: if the helper is absent (older MSA / izeberg),
  each child gets `masterVarName = battle_widget_enabled` set by hand (what the helper does).
- **column2 = "In-Garage Widget"** — the standalone `garage_widget_enabled` master, no children.

| Control (EN label) | key / `varName` | column | default | getter | consumed by |
|---|---|---|---|---|---|
| In-Garage Widget | `garage_widget_enabled` | column2 (standalone) | ON | `garage_enabled()` | `bridge/gameface_bridge.py` (garage widget presence) |
| In-Battle Widget | `battle_widget_enabled` | column1 master | ON | `battle_enabled()` | `bridge/battle_bridge.py` (overlay hard gate) |
| Show on Alt Key | `battle_widget_alt_key` | column1 child | OFF | `battle_alt_key_enabled()` | `bridge/battle_bridge.py` peek modifier |
| Counted Assistance | `counted_assistance_enabled` | column1 child | OFF | `counted_assistance_enabled()` | `battle_bridge` → `BattleMoEVM.assistVisible` → JS row 3 |

`settings_i18n.COL1_KEYS = (battleWidget, battleAltKey, countedAssist)`,
`COL2_KEYS = (garageWidget,)` — the wire order MSA and `_sync_template_text` walk in lockstep.

The getters import NOTHING from the sibling bridges, so `gameface_bridge` / `battle_bridge` read
them without a cycle. Live state seeds from MSA in `register()`; defaults until then / if MSA absent.

## Registration — soft dep, idempotent, self-healing

MSA (bundled `installer/vendor/aslain.modssettingsapi_1.6.4.wotmod`, import surface
`gui.aslainMenu`; izeberg's `gui.modsSettingsApi` is only a legacy fallback) is a **SOFT
dependency**: `register()` imports it guarded and, if absent, logs-and-returns with defaults
intact (both widgets on) and no panel — never a crash. There is no config file of ours; MSA
owns persistence.

The bundled **Aslain fork 1.6.4 DOES support child gating / grouping** (this is why the panel
can grey out the two In-Battle children under their master): `createControlsGroup(master,
children, indent=True)`, `enableWhen` / `visibleWhen` (with condition operators
`== != > >= < <=`), `enableWhenAll` / `enableWhenAny`, `visibleWhenAll` / `visibleWhenAny`, up
to **4 columns** (`column1..column4`), and 14 component types. A boolean master's children grey
out when it's off — but the disabled state is **derived from a `masterVarName` binding**, not a
literal per-control `disabled` field (this corrects an earlier note that claimed MSA had no
per-control disable at all).

`register()` is **idempotent + self-healing** (`_registered` latch): MSA may not be loaded at
our import time (our reverse-domain id `com.14th_ua.moe_calculator` sorts early), so a first
failed attempt leaves the latch False and is retried on the first hangar mount
(`gameface_bridge.attach()` calls `register()` again). The entry point also subscribes the two
feature bridges' `apply_settings` as change listeners.

With Aslain installed the mod's data lives in Aslain's own `gui.aslainMenu` object, a SEPARATE
instance from izeberg's `gui.modsSettingsApi`. `_candidate_apis()` probes `gui.aslainMenu`
FIRST and falls back to `gui.modsSettingsApi`, returning whichever import(s) succeed (de-duped,
preferred first) — so `_primary_api()` (which `register()` drives through) never lets a lingering
izeberg install win over Aslain, and reset-hooks + template-text sync still run on both when both
are present.

## The linkage-scoped, present-keys-only `_apply` rule (load-bearing)

MSA fires `onSettingsChanged` (and `onResetMod`) **GLOBALLY** — the callback runs for EVERY mod's
change, not just ours. Two defenses, both required:

- `_on_changed` / `_on_reset` are **linkage-scoped**: they early-return unless `linkage == LINKAGE`.
- `_apply(saved)` overlays **only the PRESENT known keys** onto the live cache in place; a key
  absent from `saved` keeps its current value. A naive replace-onto-`DEFAULTS` reintroduced a real
  bug: a foreign mod's global change handed us a payload with none of our keys, snapping every flag
  back to default — silently re-enabling the always-on battle overlay so it ignored
  "Battle Widget Enabled = off" + "Alt = on". A foreign payload now no-ops.

(`_seed` — the whole-state replace-filling-defaults — is used ONLY for the authoritative
registration/reset payload, never for the live-change path.)

## Master gate + Alt-peek modifier (the child model)

`battle_widget_enabled` is the **hard gate**; `battle_widget_alt_key` is a **peek modifier ON
an already-enabled overlay** (NOT mutually exclusive — that was the old, now-inverted rule). The
truth lives in `domain/battle_builder.battle_bar_visible` (pure, engine-free):

```
active == enabled and (alt_held if alt_mode else True)
```

- master **off** → overlay **never shown** (hard gate; `battle_bridge` doesn't even open the
  window — `_on_mount_refresh` early-returns, and the window-open gate keys on `battle_enabled()`
  alone).
- master **on** + Alt-child **off** → overlay **always shown**.
- master **on** + Alt-child **on** → overlay shown **only while Alt is held** (event-driven via
  `battle_input`, tracked in `_alt_held`).

The child greys out in the panel while the master is off (see `createControlsGroup` /
`masterVarName` above), and it's also inert at runtime — when `enabled` is false the `alt_mode`
term is never reached.

## Panel prose (defer to `wotmod-i18n-settings`)

Every visible label/tooltip comes from `adapter/settings_i18n.panel_text()` at the client's active
language (English master + per-key fallback; `COL1_KEYS` = the wire order MSA and
`_sync_template_text` walk in lockstep, `COL2_KEYS` empty). `modDisplayName` stays the literal
English brand. THE gotcha — MSA caches a COPY of the template text at registration, so on an
EXISTING install a client-language change never shows unless `_sync_template_text` rewrites the
stored template text in place (text-only, NO `settingsVersion` bump) — is the harness rule; see
`wotmod-i18n-settings` for the full mechanism and the `uk`-not-`ua` EU quirk.
