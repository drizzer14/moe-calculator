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

## The 4 controls

`SETTINGS_VERSION = 3`. Each `varName` == the `DEFAULTS` key, so the dict MSA returns maps
straight through `merge_settings`. Bump `SETTINGS_VERSION` **only** when the control layout /
varName set changes (the host wipes saved values on a bump) — localizing text is text-only and
does NOT bump it.

| Control | key / `varName` | default | getter | consumed by |
|---|---|---|---|---|
| Garage Widget Enabled | `garage_widget_enabled` | ON | `garage_enabled()` | `bridge/gameface_bridge.py` (garage widget presence) |
| Battle Widget Enabled | `battle_widget_enabled` | ON | `battle_enabled()` | `bridge/battle_bridge.py` (always-on overlay) |
| Show only on Alt (peek) | `battle_widget_alt_key` | OFF | `battle_alt_key_enabled()` | `bridge/battle_bridge.py` soft-gate |
| Counted Assistance row | `counted_assistance_enabled` | OFF | `counted_assistance_enabled()` | `battle_bridge` → `BattleMoEVM.assistVisible` → JS row 3 |

The getters import NOTHING from the sibling bridges, so `gameface_bridge` / `battle_bridge` read
them without a cycle. Live state seeds from MSA in `register()`; defaults until then / if MSA absent.

## Registration — soft dep, idempotent, self-healing

MSA (`izeberg.modssettingsapi`, bundled `installer/vendor/…_1.7.0.wotmod`, also shipped by Aslain)
is a **SOFT dependency**: `register()` imports it guarded and, if absent, logs-and-returns with
defaults intact (both widgets on) and no panel — never a crash. There is no config file of ours;
MSA owns persistence.

`register()` is **idempotent + self-healing** (`_registered` latch): our reverse-domain id
`com.14th_ua.moe_calculator` sorts before `izeberg`'s, so MSA may not be loaded at our import time;
a first failed attempt leaves the latch False and is retried on the first hangar mount
(`gameface_bridge.attach()` calls `register()` again). The entry point also subscribes the two
feature bridges' `apply_settings` as change listeners.

With Aslain installed there are TWO api objects (`gui.modsSettingsApi` + `gui.aslainMenu`);
`_candidate_apis()` returns whichever import(s) succeed, de-duped, so reset-hooks + template-text
sync run on both.

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

## Alt-peek ⟂ always-on

`battle_widget_alt_key` is **mutually exclusive** with `battle_widget_enabled`: the Alt-peek flag is
ignored while the always-on battle widget is ON. The gate lives in the battle consumer
(`battle_bridge.battle_bar_visible`), not in MSA — MSA 1.7.0 has no per-control disabled field, so
the checkbox stays clickable; its value just has no effect while `battle_enabled()` is on.

## Panel prose (defer to `wotmod-i18n-settings`)

Every visible label/tooltip comes from `adapter/settings_i18n.panel_text()` at the client's active
language (English master + per-key fallback; `COL1_KEYS` = the wire order MSA and
`_sync_template_text` walk in lockstep, `COL2_KEYS` empty). `modDisplayName` stays the literal
English brand. THE gotcha — MSA caches a COPY of the template text at registration, so on an
EXISTING install a client-language change never shows unless `_sync_template_text` rewrites the
stored template text in place (text-only, NO `settingsVersion` bump) — is the harness rule; see
`wotmod-i18n-settings` for the full mechanism and the `uk`-not-`ua` EU quirk.
