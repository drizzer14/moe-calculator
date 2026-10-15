---
name: moe-settings
description: Use when editing the 14th_ua MoE Calculator's SETTINGS subsystem — the ModsSettingsAPI (MSA) panel, its six bold category/group headers, Empty spacers, column 1 (Battle Calculator + a calcPreview Image, then the WHOLE Garage Widget group + its "Layout"/positioning group + a barPreview Image, as of the SETTINGS_VERSION 23→24 column swap) and column 2 (the WHOLE Progress Bar feature: Battle Progress + its three visibility children, the standalone Mode/HotKey-override/Automatic-Mode-Toggle/Scale controls, Transitions + its Events/Alt Press/Hold Duration slider children, and "Layout" (i18n key catBarPosition) + its Orientation/Alignment radios and its two shared X/Y steppers for the Ctrl+drag reposition), the standalone inline int-valued radios (Mode, Scale, Orientation, Alignment), the per-vehicle Mode-override HotKey and Automatic Mode Toggle threshold slider, the two live MSA preview Images, the flag getters the feature bridges read (including the master-folded transition getters, the "Always"-folded visibility getters, and the position getters/setter), MSA registration / soft-dep / self-heal, MSA 1.6.4's real conditional gating and its zero descriptor validation, when a change owes a SETTINGS_VERSION bump, or why a foreign mod's settings change must not touch our flags. For the reusable MSA panel MECHANICS (probe, register/migrate lifecycle, descriptor shapes, guards, bump rules) see the harness skill wotmod:msa-settings; for the panel prose translation see wotmod:i18n-settings; for feature internals see moe-garage / moe-battle.
---

# MoE Calculator — settings panel (feature)

The mod's user toggles, surfaced as ModsSettingsAPI (MSA) controls in the in-game mod-settings
menu. Shared mechanics live in the harness: **the api probe, the register/migrate lifecycle,
descriptor shapes + gating keys, the replace-not-merge rule and `saveState`, the linkage /
`enabled` guards, and the `settingsVersion` bump rules** → `wotmod:msa-settings`;
**panel-prose localization, `_sync_template_text`, `getClientLanguage` + the `uk`-not-`ua`
quirk** → `wotmod:i18n-settings`.
This skill is only the mod's concretes. All paths under `src/res/scripts/client/moe_calculator/`.

Owner module: `bridge/mod_settings.py` (flag state + MSA registration). Prose: `adapter/settings_i18n.py`.

## The controls (two-column panel, four categories, three grouped masters + four standalone radios + one standalone stepper pair + one standalone HotKey + one standalone threshold slider + two live preview Images)

`SETTINGS_VERSION` lives in `mod_settings.py` (read it there; it was 23 as of the v3.0.0-era pass
over this skill). Of the bumps since: 24-28, 30 and 31 are structural (see "The column swap (v24)"
below; **30 and 31 added the four per-bar caption checkboxes** — new varNames plus four column-2
rows right after Scale, forward bumps, saved values all carried by `register()`'s bump branch,
pinned by a v30→v31 migration test in `tests/test_mod_settings.py`); 28→29 is a stored-value
self-heal with no template/row change — see `mod_settings.py`'s comment block above the constant. Each `varName` ==
the `DEFAULTS` key, so the dict MSA returns maps
straight through `merge_settings`. Bump `SETTINGS_VERSION` **only** when the control layout /
varName set changes (the host wipes saved values back to defaults on a bump, and `register()`'s
migration branch carries the user's values across) — localizing plain label/tooltip text is
text-only and does NOT bump it. The full bump history is the comment block above the constant;
read it there rather than restating it. **The bump is always FORWARD, even to revert a layout** —
the host acts only on `new > stored`.

⚠️ Don't be misled by `wotmod:msa-settings`' (correct) general rule that a pure layout move is
NOT structural to MSA's `_settingsStructure`. That is about MSA; **this repo's `register()` takes
the saved-truthy path on an existing install and never calls `setModTemplate` at all**, so a
forward bump is the only thing that can re-lay-out a store we've already written — structural or
not. Same for *deleting* a text key, which `_sync_template_text` can never do.

The panel is **two columns** (a third does not render in Aslain's panel at all — tried, reverted),
so a **CATEGORY is not a column** but a bare `Label` header row (`_label()`, no `varName`)
followed by that feature's controls, with an **`Empty` spacer row** (`_empty()`) between
categories. Because the header names the feature, each master's own label is just **"Enabled"**
(was "Show" before v14).
Built in `_template()`:

**`SETTINGS_VERSION` 23 → 24 SWAPPED the two columns** (see "The column swap (v24) and what rode
in after it" below) — column 1 is now the Battle Calculator + everything garage-related, column 2
is the WHOLE Progress Bar feature. The bullet list below is in **current (post-v31) column order**;
where a sub-bullet's own history predates the swap it still says "column1" for what is now
column 2 — read those as **feature-relative**, not literal-column, until the swap section.

- **column1 = one category (Battle Calculator), one live preview Image, then the WHOLE Garage
  Widget feature (its own master + "Layout" group) and a second live preview Image.**
  1. `Label` **"Battle Calculator"**, then the `battle_widget_enabled` master + two indented
     children ("Alt Press", "Counted Assistance Row");
  2. the **`calcPreview` live `Image`** (v25) — a pre-baked PNG preview of the in-battle corner
     overlay, swapped via `updateImage` as the driving settings (Counted Assistance, live values)
     change; not a stored setting (absent from `DEFAULTS`);
  3. `_empty()`, `Label` **"Garage Widget"**, the standalone `garage_widget_enabled` master, an
     `_empty()`, then the **"Layout"** group (`positioning`) — a `Label` header, the "Follow
     Carousel Mode" checkbox, a non-bold **"Position"** sub-label, and the `posX`/`posY`
     `NumericStepper`s;
  4. the **`barPreview` live `Image`** (added in column 2 at v25, MOVED here at v26→27 so both
     previews sit together) — a preview of whichever centre-screen bar Mode currently selects,
     also not a stored setting.
- **column2 = the WHOLE Progress Bar feature** (moved here from column 1 at v23→24), one group,
  one grouped-Transitions splice, four standalone radios/controls, and a "Layout" group:
  1. `Label` **"Battle Progress"**, then the `progress_bar_enabled` master + its three
     **VISIBILITY** children ("Events", "Alt Press", "Always") — the first two then **trade** the
     group binding for an **AND gate** via `_gate_and()` (see below);
  2. the standalone `inline` **"Mode"** radio, then (v26) the standalone **`HotKey`** control
     "Mode Override" (`progress_variant_hotkey`, default chord `[37]` = `Keys.KEY_K`) — the
     in-battle chord that flips the current vehicle's bar Mode — then (v28) the standalone
     **"Automatic Mode Toggle"** `Slider` (`progress_auto_toggle_threshold`, 0–100, default
     **100 = the DISABLE sentinel** since no percentile can reach past it) — the pre-battle MoE
     percentile at/above which a vehicle's bar Mode auto-toggles once — then the standalone
     `inline` **"Scale"** radio, then (v30/v31) FOUR standalone per-bar checkboxes, all default
     **True**, each with a tooltip and an 11-language row: **"Moving Average: show %"**
     (`PROGRESS_SHOW_PERCENT_KEY`), **"Moving Average: show change"** (`PROGRESS_SHOW_DELTA_KEY`),
     **"Damage Efficiency: show %"** (`EFFICIENCY_SHOW_PERCENT_KEY`) and **"Damage Efficiency: show
     change"** (`EFFICIENCY_SHOW_DELTA_KEY`) — read the key strings and getters in
     `mod_settings.py`, the i18n keys in `settings_i18n.COL2_KEYS`. The `%` pair is the
     parenthesised MoE % beside each bar's current-damage numeral, **folded in Python** into the
     VM's `-1` sentinel (`push_progress` / `push_efficiency` in `bridge/battle_bridge.py` send
     `curPercent` / `damagePercent` = `-1.0` when off — the JS draws only on `>= 0`; see
     `moe-progress`); the `change` pair rides a `showDelta` VM bool the JS reads as `!== false`.
     All are deliberately **ungated** (describe the
     bar itself, not when it shows), matching the pre-v13 reasoning for Mode/Scale;
  3. `_empty()`, `Label` **"Transitions"**, then the `progress_transitions_enabled` master + THREE
     children: two label-only checkboxes ("Events", "Alt Press") and, as of v17, a `Slider`
     ("Hold Duration (s)") — `progress_hold_seconds`, 1-30s, `snapInterval: 1`, `format:
     "{{value}} s"`, default 5. Its master's own label reads **"Enabled"** now, same as the
     other three masters (was "Transitions" before v17), but the `varName` is deliberately
     unchanged;
  4. `_empty()`, `Label` **"Layout"** (i18n key `catBarPosition`, header text renamed from "Bar
     Position" at v21 — the key is unchanged, a rename buys nothing since it's positional in
     `COL2_KEYS`), then two more **standalone `inline` radios** — "Orientation"
     (`progress_bar_orientation`: Horizontal `0` default / Vertical `1`) and "Alignment"
     (`progress_bar_alignment`: **Fixed `0` default / Free `1`** — collapsed from three options
     [Damage Log `0` / Minimap `1` / Free `2`] to two at v23, see "The Fixed-alignment redesign
     (v23)" below) — followed by the two `NumericStepper`s, `progress_bar_pos_x` /
     `progress_bar_pos_y`, mirroring the in-battle bar's Ctrl+drag reposition (see `moe-battle`).
     Orientation is standalone (no master, no condition), like Mode/Scale, so a bar's shape stays
     readable/editable while the feature is off. **The position steppers are NOT standalone as of
     v23** — they carry a hand-built `enableWhen`-shaped gate (`_gate_enable`,
     `mod_settings.py:1031`) against `progress_bar_alignment == PROGRESS_ALIGN_FREE`, so they grey
     out (never hide — a stepper that vanishes would reflow the rest of column 2, and MSA stores +
     pushes a greyed control's value regardless) whenever Alignment is Fixed. **One shared radio
     pair and one shared stepper pair serve BOTH bar variants** (they're mutually exclusive at
     runtime); the steppers store LOGICAL GUI px (interface-scale invariant, no `posW`/`posH`
     viewport pinning like the garage pair above). Under **Fixed** the pair is still an
     anchor-relative OFFSET composed via `anchor_offset` on top of whichever internal anchor
     Orientation selects (see "The Fixed-alignment redesign (v23)"); under **Free** the pair is an
     **anchor point**, not an offset, and the exact pair `(0, 0)` under Free still resolves to the
     orientation's default anchor (`bar_window.py:346-353`) — see `progress_bar_alignment()` below.
     Both this pair's steppers and the garage `posX`/`posY` pair above run
     **`-POS_MAX .. POS_MAX`** (was `0 .. POS_MAX` before v20) — the on-screen edge clamp was
     removed so a bar may be dragged past any screen edge; see the memory
     `[[unclamping-drag-is-constrained-by-the-auto-placement-sentinel]]`.

### The column swap (v24) and what rode in after it

**`SETTINGS_VERSION` 23 → 24** was a pure column swap: no `varName`, control type or option
changed shape, only which column each feature's rows render in — but `register()`'s saved-truthy
path never calls `setModTemplate` on an existing install, so the new column assignment (and the
`COL1_KEYS`/`COL2_KEYS` positional pairing `_sync_template_text` relies on) reaches nobody without
a forward bump. Four more bumps rode in after it, all confined to column 2 or the two preview
Images: **25** added the `calcPreview` / `barPreview` live preview `Image`s (`calcPreview` in
column 1's calculator group, `barPreview` originally at the tail of column 2's "Layout"); **26**
added the `progress_variant_hotkey` `HotKey` control (the first control here of that MSA component
type) right after the Mode radio; **27** moved `barPreview` out of column 2 to sit beside
`calcPreview` at the tail of column 1, so both live previews now share one column; **28** added the
`progress_auto_toggle_threshold` `Slider` right after the HotKey control and before Scale. See
`mod_settings.py`'s `SETTINGS_VERSION` comment block (the fullest in the file) for the full
reasoning behind each.

**The two near-identical child pairs are DIFFERENT AXES and the resemblance is deliberate:** the
visibility trio decides **WHEN** the bar comes up, the Transitions pair only **HOW** it moves once
it does. Don't conflate them.

| Control (EN label) | key / `varName` | column | default | getter | consumed by |
|---|---|---|---|---|---|
| *Battle Calculator* (header, **bold**) | — | column1 `Label` | — | — | — |
| Enabled | `battle_widget_enabled` | column1 group-1 master | ON | `battle_enabled()` | `bridge/battle_bridge.py` (overlay hard gate) |
| Alt Press | `battle_widget_alt_key` | column1 group-1 child | OFF | `battle_alt_key_enabled()` | `bridge/battle_bridge.py` peek modifier |
| Counted Assistance Row | `counted_assistance_enabled` | column1 group-1 child | **ON** (flipped in v13) | `counted_assistance_enabled()` | `battle_bridge` → `BattleMoEVM.assistVisible` → JS row 3 |
| calcPreview (live preview `Image`, no label) | `calcPreview` | column1, **not a stored setting** (v25) | — | `preview_sources()` | MSA `updateImage` — a baked PNG of the corner overlay |
| *Garage Widget* (header, **bold**) | — | column1 `Label` (moved here from column2 at v23→24) | — | — | — |
| Enabled | `garage_widget_enabled` | column1 (standalone) | ON | `garage_enabled()` | `bridge/gameface_bridge.py` (garage widget presence) |
| *Layout* (header, **bold**) | — | column1 `Label` | — | — | — |
| Follow Carousel Mode | `followCarousel` | column1 (sits ABOVE the steppers as of v14) | ON | `follow_carousel()` | garage widget carousel nudge |
| *Position* (sub-label, **not bold** — deliberately excluded from `HEADER_KEYS`) | — | column1 `Label` | — | — | — |
| Horizontal (left X) / Vertical (top Y) | `posX`, `posY` (+ non-user `posW`, `posH`) | column1, range `-POS_MAX..POS_MAX` (v20) | 0 = auto | `pos_x()` … `pos_h()` | garage widget placement / rescale |
| barPreview (live preview `Image`, no label) | `barPreview` | column1, **not a stored setting** (added v25 in column2, moved here v26→27) | — | `preview_sources()` | MSA `updateImage` — a baked PNG of whichever centre-screen bar Mode selects |
| *Battle Progress* (header, **bold**) | — | column2 `Label` (moved here from column1 at v23→24) | — | — | — |
| Enabled | `progress_bar_enabled` | column2 group-2 master | OFF | `progress_bar_enabled()` | `battle_bridge` (centre-screen transient, hard gate) |
| ↳ Events | `progress_show_events` | column2 group-2 child (**AND-gated**) | ON | `progress_show_events()` | `battle_bridge` — whether a damage/efficiency tick raises the bar |
| ↳ Alt Press | `progress_show_alt_key` | column2 group-2 child (**AND-gated**) | ON | *(none — folded into `progress_alt_held()`)* | — |
| ↳ Always | `progress_show_always` | column2 group-2 child | OFF | *(none — folded into BOTH getters)* | — |
| Mode — Damage Efficiency / Moving Average | `progress_bar_variant` | column2 **standalone**, `inline` (**RadioButtonGroup**, **int**) | `0` = Damage Efficiency | `progress_bar_variant()` | `battle_bridge` — picks which centre-screen window opens |
| Mode Override (HotKey chord) | `progress_variant_hotkey` | column2 **standalone**, `HotKey` (v26) | `[37]` = `Keys.KEY_K` | `progress_variant_hotkey()` | `bridge/battle_input.py` / `battle_bridge` — in-battle chord flips this vehicle's Mode |
| Automatic Mode Toggle (percentile threshold) | `progress_auto_toggle_threshold` | column2 **standalone**, `Slider` (0-100, int, v28) | `100` (the DISABLE sentinel) | `progress_auto_toggle_threshold()` | `variant_overrides.should_auto_toggle` — auto-flips a vehicle's Mode once at/above this pre-battle MoE percentile |
| Scale — Default / Large | `progress_bar_size` | column2 **standalone**, `inline` (**RadioButtonGroup**, **int**) | `0` | `progress_bar_size()` | both bars' `barSize` → `MoEBarTransient.applySize` (root-font 1.5× + `.mp-lg`) |
| Enabled (Transitions master) | `progress_transitions_enabled` | column2 group-3 **master** | ON | *(none — folded in below)* | never pushed to JS |
| ↳ Events | `progress_transitions_events` | column2 group-3 child | ON | `progress_transitions_events()` | `ProgressVM.transEvents` / `EfficiencyVM.transEvents` → `applyAnim` |
| ↳ Alt Press | `progress_transitions_manual` | column2 group-3 child | ON | `progress_transitions_manual()` | `…VM.transManual` → `applyAnim` (the Alt peek) |
| ↳ Hold Duration (s) | `progress_hold_seconds` | column2 group-3 child, `Slider` (1-30, int) | `5` | `progress_hold_seconds()` — **NOT** master-folded (a duration, not a flag) | both bars' `MoEBarTransient` hold timer |
| *Layout* (header, **bold**, v18, header text renamed from "Bar Position" at v21, key `catBarPosition` unchanged) | — | column2 `Label` | — | — | — |
| Orientation — Horizontal / Vertical | `progress_bar_orientation` | column2 **standalone**, `inline` (**RadioButtonGroup**, **int**, v21) | `0` = Horizontal | `progress_bar_orientation()` | `bar_window.BarHost._resolve` (orientation branch), front-end DOM build branch |
| Alignment — Fixed / Free | `progress_bar_alignment` | column2 **standalone**, `inline` (**RadioButtonGroup**, **int**, v21; collapsed 3→2 options at v23) | `0` = Fixed | `progress_bar_alignment()` | `bar_window.BarHost._resolve` (Fixed resolves internally by Orientation to the Damage-Log or Minimap anchor; Free is its own branch), `bar_window.BarHost.drag` (refuses the gesture outright unless Free) |
| Horizontal (left X) / Vertical (top Y) | `progress_bar_pos_x`, `progress_bar_pos_y` | column2 `NumericStepper`s, range `-POS_MAX..POS_MAX` (v20); **`enableWhen`-gated on Alignment==Free as of v23** (`_gate_enable`) | 0 = anchor-relative offset under Fixed; under **Free**, the pair is an anchor point and the exact 0/0 means AUTO (the orientation's default anchor) | `bar_pos_x()` / `bar_pos_y()` | `bar_window.BarHost.apply_position` (both bars, via `battle_bridge.apply_settings` → `progress_view`/`efficiency_view.apply_position()`) |

```python
# Column 1: Battle Calculator + EVERY garage-related group (moved here from column2 at v23->24),
# plus the two live preview Images (calcPreview at v25, barPreview moved in from column2 at v26->27).
# SIXTEEN slots.
COL1_KEYS = (u"catBattleCalc", u"battleWidget", u"battleAltKey", u"countedAssist",
             None,                                   # calcPreview Image (no i18n text)
             None,                                   # Empty spacer
             u"catGarage", u"garageWidget",
             None,
             u"positioning", u"followCarousel",
             None,
             u"positionSub", u"posX", u"posY",
             None)                                   # barPreview Image (no i18n text)
# Column 2: the WHOLE Progress Bar feature (moved here from column1 at v23->24), plus the HotKey
# mode-override control (v26), the Automatic Mode Toggle slider (v28) and the Show MoE % checkbox
# (v30; v31 split it into four per-bar checkboxes). Count the slots in settings_i18n.py.
COL2_KEYS = (u"catBattleProgress", u"progressBar",
             u"progressShowEvents", u"progressShowAlt", u"progressShowAlways",
             None,
             VARIANT_KEY, VARIANT_HOTKEY_KEY, u"progressAutoToggleThreshold", u"progressSize",
             u"progressShowPercent", u"progressShowDelta",
             u"efficiencyShowPercent", u"efficiencyShowDelta",
             None,
             u"catTransitions", u"progressTransitions",
             u"progressTransEvents", u"progressTransManual",
             None,
             u"progressHoldSeconds",
             None,
             u"catBarPosition", u"progressOrientation", u"progressAlignment",
             u"barPosX", u"barPosY")
```

**Counts (v31: `COL1_KEYS` 16 slots, `COL2_KEYS` 27 slots, `spacers == 9`; recount the two tuples in `adapter/settings_i18n.py`, they drift). `tipless == 8` carried over, not recounted — the per-bar rows all have tooltips so it is unchanged.**
Growth since v23 (26 / 9 at the time, described by the pre-swap layout further below): the v24
column swap itself changed only which keys sit in which tuple, not the total row count; v25 added
one `None` slot to each tuple (the two preview Images' sentinels); v26 added one slot to `COL2_KEYS`
(`VARIANT_HOTKEY_KEY`); v27 moved one `None` slot from `COL2_KEYS` to the tail of `COL1_KEYS`
(`barPreview`); v28 added one more slot to `COL2_KEYS` (`progressAutoToggleThreshold`); v30/v31 added
four COL2 slots (the per-bar show-%/show-change checkboxes, right after `progressSize`). `spacers`
grew 7 → 9 across this span (the two preview Images' own sentinels); `tipless` (8) is unchanged —
neither preview Image nor the HotKey/threshold controls are tooltip-less.

**Pre-v24, for historical reference, column 2 held the whole Garage Widget feature and column 1
held Battle Calculator + the WHOLE Progress Bar feature — the reverse of today.** Every paragraph
from here through "The Fixed-alignment redesign (v23)" below uses `COL1_KEYS` / `COL2_KEYS` **as
they applied AT THAT TIME** (pre-v24): `COL1_KEYS` meant Battle Calculator + Progress Bar (now
`COL2_KEYS`'s content, minus Battle Calculator which stayed in `COL1_KEYS`), `COL2_KEYS` meant
Garage Widget (now folded into `COL1_KEYS`). The v24 bump is what swapped which tuple holds which
feature; read "The column swap (v24)" section above for the swap itself.
**v14 grew `COL2_KEYS` 7 → 8**: Follow Carousel moved to sit right under the (now bold) "Layout"
header, and a new varName-less `"positionSub"` (**"Position"**) sub-label was inserted ahead of the
two steppers — deliberately **excluded** from `HEADER_KEYS` (below) so its lighter weight reads as a
sub-level under "Layout" rather than a third header. **`COL2_KEYS` (garage) had grown 8 → 9** by
v20 (a second `Empty` spacer heading "Position" the same way the first one headed "Battle
Progress") — this is the tuple that is now `COL1_KEYS`'s garage-related tail, post-v24.

**v17 added a `catTransitions` `Label` header** ahead of the Transitions master (previously the
group rode inside the "Battle Progress" category with no header of its own) plus the
`progress_hold_seconds` `Slider` as a fourth Transitions child — growing `COL1_KEYS` 17 → 19
(two more `None` spacers plus `catTransitions` and `progressHoldSeconds`) and `HEADER_KEYS`
four entries → five.

**v18 added a FOURTH column-1 category, `catBarPosition`** (header text "Bar Position" at the
time, renamed "Layout" at v21 — see below) — an `Empty` spacer + its own bold `Label` header,
then the two standalone `progress_bar_pos_x` / `progress_bar_pos_y` `NumericStepper`s (`barPosX`
/ `barPosY`) mirroring the in-battle bar's Ctrl+drag reposition. Appended at the very end (safe:
shifts nothing before it) — `COL1_KEYS` grows 19 → 23 and `HEADER_KEYS` five entries → six.

**v20** (the `-POS_MAX..POS_MAX` unclamp) also split the Transitions group's two switch children
from the ungrouped `progressHoldSeconds` slider with its own `None` spacer — `COL1_KEYS` grows
23 → 24, no `HEADER_KEYS` change.

**v21 (Orientation + Alignment) renamed the "Bar Position" header text to "Layout"** — the i18n
KEY stays `catBarPosition` (it's positional in `COL1_KEYS`/`HEADER_KEYS`; a key rename buys
nothing) — and spliced two new standalone `inline` radios, `progressOrientation` /
`progressAlignment`, in **AFTER** `catBarPosition` and **BEFORE** `barPosX`/`barPosY`, matching
`mod_settings._template()`'s wire order exactly. Inserting mid-column rather than appending is
safe **only** because a `SETTINGS_VERSION` bump (20 → 21) accompanies it. `COL1_KEYS` grows
24 → 26, `HEADER_KEYS` is unchanged at six (the new radios are ordinary rows, not headers).

### `HEADER_KEYS` — the bold category/group headers, and the double-wrap self-revert bug (v14, RESOLVED)

`settings_i18n.HEADER_KEYS = frozenset((u"catBattleCalc", u"catBattleProgress", u"catTransitions",
u"catBarPosition", u"catGarage", u"positioning"))` — the **six** header rows that render **bold**
(as of v18); `"positionSub"` is deliberately excluded (the non-bold sub-label under "Layout").

**The wrap lives in exactly ONE place: `settings_i18n.build()`**, applied to each `HEADER_KEYS`
entry **after** the untranslated-fallback mark (so a marked English leak stays visible inside the
bold, not stranded outside it):

```python
for k in HEADER_KEYS:
    out[k][u"text"] = u"<b>%s</b>" % out[k][u"text"]
```

`mod_settings._label(key, rendered)` then does nothing but read `key in settings_i18n.HEADER_KEYS`
to add the matching `useHTML: True`, and passes `rendered["text"]` through **verbatim** — it never
wraps anything itself.

**Why this has to be one site, not two:** `_sync_template_text()` runs on **every** `register()`
call, including the one that just built the freshly-bolded template. It compares the stored
`comp["text"]` against a **freshly re-rendered** `panel_text()[key]["text"]`. If `_label()` had
wrapped the markup itself while `panel_text()` returned it unwrapped, that comparison would see
`"<b>Battle Calculator</b>"` disagree with `"Battle Calculator"` on the very first `register()`,
overwrite the bold back out, and `saveState()` — silently, on every launch, with `useHTML` left
dangling `True` on now-plain text. **This is exactly the bug that shipped before the v14 fix**, and
the on-disk tell is `aslainmenu.dat` showing `{'text': 'Battle Calculator', 'useHTML': True}` with no
`<b>` in sight — the enabling key survived, the markup didn't. Whenever a `_label`/`_checkbox`/etc.
decoration is added, it MUST be applied inside `settings_i18n.build()`, never inside `_template()`.

**The regression test has to be a build-then-sync round trip**, not a one-shot "does `_label` emit
bold" assertion — the latter passes against the broken code because it only exercises `_label` in
isolation with already-wrapped input. `tests/test_mod_settings.py`'s
`test_sync_template_text_walks_built_template_in_lockstep` (and its neighbours around it) build the
template exactly as `register()` does, run `_sync_template_text()` against it, and assert the `<b>`
+ `useHTML` survive.

This bump (13 → 14) also carries the three masters' own label going "Show" → "Enabled" and the
position steppers regaining their axis-hint wording — both text-only changes that would otherwise
have ridden `_sync_template_text` for free, but travel with this bump regardless since it was already
forced by the header bold + column-2 regroup.

These are the wire order MSA and `_sync_template_text` walk in lockstep, and the pairing is
**positional** — `zip(tmpl[col], keys)`, so a reorder or an omission does not error, it retitles
the **wrong control** on every existing install. Every bare **category `Label`** earns a slot even
though it has no `varName`. **A row with no TEXT at all — an `Empty` spacer — takes a `None`
SENTINEL slot**, never a skip: `panel_text().get(None)` is falsy, so the sync walk's existing
`if not rendered: continue` handles it for free, whereas skipping a component by type would
consume the component *without* consuming its key and desync every control after it.
**Appending** to the end shifts nothing and is the safe move; inserting is not.

### Gating: two grouped masters, one AND gate, four ungated radios, and (v23) one peer-value gate

`createControlsGroup` sets exactly **one** `masterVarName` per child, so a master-under-a-master is
not expressible **through it**. **MSA 1.6.4 has real conditional gating** (capability section
below), so four shapes are in play:

1. **`_grouped_column1(master, children)`** — the default. One `masterVarName` per child.
2. **`_gate_and(control, ((var, value), …))`** — MSA's multi-condition form (`conditions` +
   `conditionsLogic: "AND"` + `masterIndent`), emitted by hand as plain keys. ⚠️ **`conditions`
   does NOT set `masterVarName`, so it REPLACES the group parenting** — `_gate_and` therefore
   `pop`s the now-dead `masterVarName` and the caller must include the group master as one of the
   conditions. `show_events` / `show_alt` are grouped under `PROGRESS_BAR_KEY` and then re-gated on
   `(PROGRESS_BAR_KEY == True) AND (PROGRESS_SHOW_ALWAYS_KEY == False)`, because they are also
   meaningless while "Always" is on.
3. **standalone** — no master, no condition. Mode, Scale and Orientation describe the bar itself
   rather than when it shows, they cost one row each because they are `inline`, and leaving them
   ungated keeps them readable while the feature is off (the same call already made for the
   column-2 steppers).
4. **`_gate_enable(control, master_var, value, condition="==")`** (v23, `mod_settings.py:1031`) —
   a single-condition `enableWhen`-shaped gate built by hand like `_gate_and`, used for exactly
   ONE pair: the position steppers `barPosX`/`barPosY` grey out (never hide — a hidden-then-shown
   stepper reflows the rest of column 1, and MSA stores + pushes a greyed control's value
   regardless) whenever `progress_bar_alignment != PROGRESS_ALIGN_FREE`. This is the *only*
   mechanism available to express "control B only makes sense once control A picks a specific
   value" — MSA's whole gating vocabulary is enable-or-hide only, it never assigns a peer's
   stored value (`[[msa-gating-is-enable-or-hide-only]]`), so a peer control cannot programmatically
   flip Alignment to Free when the user edits a stepper; the steppers are simply disabled until it
   already is. The Orientation/Alignment radios themselves stay standalone — the v18 "Layout"
   (`catBarPosition`) steppers used to be standalone for the identical "stay readable while the
   bar is off" reason, but v23 traded that for the gate above because an editable-but-meaningless
   stepper under Fixed was the worse of the two costs.

"Transitions under Progress Bar" is still a **third `_grouped_column1(...)` splice inside the same
category** — visually part of the Battle Progress block, with the accepted cost that **the
Transitions master is NOT greyed out while Progress Bar is off**. Harmless at runtime: the
`progress_bar_enabled()` gate means the flags have nothing to affect until the bar is on. (A
`_gate_and` on that master would grey it too, at the cost of the indent the group gives its
children — not attempted.)

### "Always" costs NO new code path — it is a permanently-held Alt

`MoEBarTransient.peekOn()` already pauses the run at its hold plateau **and** `clearTimeout(endT)`,
so a hold **never ends** while `altHeld` is true. `progress_alt_held(alt_held)` therefore just
reports `True` forever when "Always" is on — no fourth branch, no new CSS, no new VM field. It is
also why three new settings cost exactly **one** extra pushed bool: two collapse into the existing
`altHeld` push and the third folds into `progress_show_events()`.

### The visibility getters FOLD "ALWAYS" IN

MSA **still stores and still pushes a greyed control's value**, so a control being disabled in the
panel guarantees nothing at runtime. Every fold has to happen in Python:

```python
def progress_show_events():        # "Always" ON => the events flag must READ as on regardless
    return (bool(_settings.get(PROGRESS_SHOW_ALWAYS_KEY, False))
            or bool(_settings.get(PROGRESS_SHOW_EVENTS_KEY, True)))

def progress_alt_held(alt_held):   # ONE place, so the two bar variants can never disagree
    if bool(_settings.get(PROGRESS_SHOW_ALWAYS_KEY, False)):
        return True
    return bool(alt_held) and bool(_settings.get(PROGRESS_SHOW_ALT_KEY, True))
```

Keeping `progress_show_events()` true while pinned is also what keeps the bar's **numbers** live:
the JS commits new values on the same trigger it shows on.

### The two transition getters FOLD THE MASTER IN

`progress_transitions_enabled` has **no getter of its own and is never pushed to the widget**.
Both children's getters AND it together:

```python
return (bool(_settings.get(PROGRESS_TRANSITIONS_KEY, True))
        and bool(_settings.get(PROGRESS_TRANS_EVENTS_KEY, True)))   # …_MANUAL_KEY for the other
```

One place ANDs the group, so the JS can never honour a child while the master is off. The JS half
of the same discipline reads the pushed bools as `!== false` (absent ⇒ animated, the shipped
behaviour) — see `wotmod:gameface-widget` and the memory note on new VM bools.

### `bar_pos_x()` / `bar_pos_y()` and `set_bar_position()` — the Ctrl+drag position pair

`progress_bar_pos_x` / `progress_bar_pos_y` (`BAR_POS_X_KEY` / `BAR_POS_Y_KEY`, both frozen
`varName`s forever) store the in-battle bar's dragged top-left in **logical GUI px**, shared by
**both** bar variants — they're mutually exclusive at runtime, so one pair is one fewer settings
row rather than a duplicated pair per variant. `bar_pos_x()` / `bar_pos_y()` re-clamp on read
(`clamp_pos`, same `_POS_KEYS` branch of `_coerce` as the garage `posX`/`posY`).

### The Fixed-alignment redesign (v23) — Alignment collapses to Fixed/Free, all auto-set is deleted

**As of v23, `progress_bar_alignment` stores only two values: `PROGRESS_ALIGN_FIXED = 0` (default)
or `PROGRESS_ALIGN_FREE = 1`.** The old three-way radio (Damage Log `0` / Minimap `1` / Free `2`)
is gone from the panel. `PROGRESS_ALIGN_DAMAGE_LOG = 0` / `PROGRESS_ALIGN_MINIMAP = 1` survive in
`mod_settings.py` as **INTERNAL anchor selectors only** — nothing ever stores them any more, and
`clamp_variant`'s ceiling for `PROGRESS_ALIGNMENT_KEY` is `PROGRESS_ALIGN_FREE == 1`, so no legal
stored value can select the old Minimap-under-Fixed combination. **Fixed resolves purely by
Orientation** (`bar_window.BarHost._resolve`, `bar_window.py:277-360`): Horizontal → the Damage
Log anchor (`anchor_centred_reduced`), Vertical → the Minimap anchor (`anchor_minimap`) — the same
placement math as before, just no longer independently selectable. **`_resolve` branches on
`vertical` directly, never on a locally-reassigned "resolved anchor" variable** — `PROGRESS_ALIGN_
MINIMAP` and `PROGRESS_ALIGN_FREE` are BOTH `1` (two different, never-crossed vocabularies: stored
alignment vs. internal anchor selector), so re-testing a variable just set to `PROGRESS_ALIGN_
MINIMAP` against `== PROGRESS_ALIGN_FREE` would wrongly match
(`[[internal-constant-shares-value-with-different-stored-vocabulary]]`). Free is its
own third branch, unchanged from v22: the stored pair is an **anchor point** (bottom-centre
horizontal / bottom-right vertical — `domain/positioning.py`'s `free_top_left(pair, surface,
vertical)`, converted at placement time only, never written back), and the exact pair `(0, 0)`
under Free is still rewritten to Fixed's own mapping first — Free+0/0 is AUTO, not the screen
corner, and is also the "not yet materialised" marker (see `progress_bar_pos_frame` above).

**All Orientation↔Alignment auto-set is DELETED.** The maintainer tested in-client and found
flipping Orientation never visibly updated the Alignment radio; the root cause was NOT a broken
derivation — MSA's Aslain panel simply never subscribes to `onSettingsChanged` and only pushes
control values once, at panel open (`[[msa-panel-never-repaints-on-a-write-back]]`) — but rather
than build a repaint path, the maintainer restructured the feature so nothing needs to derive a
peer control's value at all. Neither radio derives the other any more. `_derive_layout(pre, post)`
(`mod_settings.py:1502`) keeps **exactly one rule**: an Orientation flip zeroes the stored X/Y
pair, because the two orientations use different surface geometries. Its signature dropped from
`(orientation, alignment, position)` to **`(orientation, position)`** — Alignment is no longer
part of it at all, in either direction. The `_deriving` re-entrancy latch is KEPT (a stale echo
racing the zeroing rule could still misread a settled `(newO, (0, 0))` as the user re-typing the
old coordinates), even though the mutual-derivation ping-pong hazard it was originally built for
is gone. `_derive_layout(s, s) == s` for any `(orientation, position)` pair remains the fixed-point
termination proof `_on_changed` relies on for a single write-back pass.

**Position is locked unless Alignment is Free — rule 4 (position-change forces Alignment := Free)
is deleted, not merely inert.** The X/Y steppers carry MSA's native `enableWhen`-shaped gate
(`_gate_enable`, greyed under Fixed, never hidden) and `bar_window.BarHost.drag()` refuses the
WHOLE gesture, checked at the very top before any cursor read or window move, on every phase,
while `progress_bar_alignment() != PROGRESS_ALIGN_FREE`. With both paths blocked, a stored
position can now only ever change while Alignment is *already* Free, by construction — so the old
rule has no reachable input left to fire on and was deleted from both `_derive_layout` and
`set_bar_position` (which no longer touches `PROGRESS_ALIGNMENT_KEY` at all).

**Deleted as provably dead** (v23): `PROGRESS_ANCHOR_X_SHIFT_LARGE` / `EFFICIENCY_ANCHOR_X_SHIFT_
LARGE`, `anchor_centred_reduced`'s `x_shift` parameter, `BarHost`'s `x_shift_large` constructor
argument and the view-construction threading, and `_resolve`'s horizontal+Minimap-under-vertical
sub-case. This machinery existed only to right-pin a VERTICAL bar resolving to the Damage Log
anchor under Large; that combination is now unreachable through the UI or any legal stored value
(Alignment only ever stores Fixed or Free, and Fixed always picks Minimap when vertical), so
`clamp_variant`'s ceiling of `1` for the alignment key structurally forecloses it — not just
"currently unused". `VERTICAL_ANCHOR_Y_SHIFT` / `_LARGE` (the −170 value) and the re-derived
horizontal `PROGRESS_ANCHOR_Y_SHIFT_LARGE`/`EFFICIENCY_ANCHOR_Y_SHIFT_LARGE` (values owned by `moe-progress`; read them in `domain/constants.py`) are KEPT —
rule 5's size-invariance still holds through `anchor_minimap` and `free_top_left`, and the JS files
cite the vertical shift constants as a wire-contract record even though placement no longer reads
them for a centred anchor.

**`SETTINGS_VERSION` 22 → 23** carries both the radio collapse and the stepper gate in one bump
(`mod_settings.py:232-288`, the fullest comment block in the file — read it before touching any of
this again). The Alignment index migration (`_migrate_pre_v23_alignment`, last in the migration
chain, after `_migrate_pre_v21_layout` / `_migrate_pre_v22_pos_frame`, both of which still read/
write the OLD 3-option encoding) maps the raw int explicitly: old `0` (Damage Log) → new `0`
(Fixed); old `1` (Minimap) → new `0` (Fixed); old `2` (Free) → new `1` (Free) — a genuine
collision, not a relabel, since the old raw `1` (Minimap) and the new raw `1` (Free) would
otherwise silently swap meaning.

**`_migrate_pre_v21_layout`** (unchanged by v23, runs first in the chain) is keyed on the absence
of `progress_bar_orientation`: a non-zero pre-v21 `(pos_x, pos_y)` implies the old absolute
placement, so it becomes (pre-v23) Alignment = Free with the coordinates carried verbatim; a zero
pair implies the shipped centred placement, so it becomes (pre-v23) Alignment = Damage Log, still
`(0, 0)`. `_migrate_pre_v23_alignment` then remaps whatever that produced onto the new 2-option
domain, so a chained pre-v21 install ends up in the right place after all three migrations run.

**Do NOT re-derive "Free is sticky" or the mutual auto-set from any older prose** —
`TASKS/in-battle-bar-layout-auto-set-redesign.md`'s rules 2/3, its 13-row transition table, and
DECISION 4/5 are SUPERSEDED (see that note's own updated status section). Rule 5
(size-invariance) DID ship and still holds.

`set_bar_position(x, y, persist=True)` is the write path, called from `bar_window.BarHost.drag`
on gesture end (`phase == "end"`). **The gesture itself has no JS and no wire protocol at
all** — Python owns it end to end: `adapter/battle_input.py` samples Ctrl + the left mouse
button off WG's own input dispatchers and `gui.g_mouseEventHandlers`, and `BarHost.drag` places
the window ABSOLUTELY from the live cursor position (`domain/positioning.cursor_top_left`) plus
a grab offset recorded at gesture start — never a delta. The previous design (a JS `setPosition`
command reporting a mouse delta for Python to add) is gone: both bar VMs are `commands=0`
again. See `moe-battle`'s Ctrl+drag notes and the memory
`[[absolute-cursor-placement-replaces-js-delta-drag-protocol]]` for why the delta protocol
could not work structurally. `set_bar_position` deliberately does **NOT** call `_notify()`,
unlike `set_position` (the garage twin): the bar host re-places its own window directly in the
same handler, so a fan-out would only cost every *other* feature a needless `apply_settings` +
re-push, at pointer rate during a live drag. `persist=False` (every mousemove) only updates the
in-memory value; `persist=True` (mouseup) additionally writes it through MSA so the panel
steppers track the drag and it survives the session.

Because a stepper edit or a panel Reset changes the stored value **without** going through
`set_bar_position`, `battle_bridge.apply_settings()` calls `progress_view.apply_position()` /
`efficiency_view.apply_position()` (thin aliases for `bar_window.BarHost.apply_position`) on
every settings change, so either path — drag or panel — moves the live bar.

### `_checkbox` / `_radio` / `_label` all omit a FALSY tooltip

All three descriptor helpers end with `tooltip = rendered.get("tooltip"); if tooltip: …`.
`_checkbox` used to hard-index `rendered["tooltip"]` and raised **`KeyError` inside `_template()`**
— i.e. inside `register()`'s guarded `try`, so the live symptom was **a client with no settings
panel at all** plus one logged traceback. The trigger is the **first label-only control of a given
TYPE**, which the Transitions children are, and (as of v18) the "Layout" (`catBarPosition`)
steppers are the first tipless `NumericStepper`s. Emitting `u""` is not a fix: `_sync_template_text`
only overwrites, never deletes. The tripwire is the exact `tipless == 8` counter in
`tests/test_mod_settings.py::test_sync_template_text_walks_built_template_in_lockstep` — the four
bare category headers (Battle Calculator / Battle Progress / Transitions / Garage Widget), the
Transitions group's two children (Events / Alt Press), and the two "Layout" steppers (`barPosX` /
`barPosY` — the header above them carries the Ctrl+drag tooltip instead, so the header itself is
NOT in this count; the v21 Orientation/Alignment radios both carry their own tooltip, so they
don't add to `tipless` either) — alongside `spacers == 9` (v21 shipped 7; the two preview Images'
own `None` sentinels at v25/v27 grew it to 9) for the `None`-sentinel `Empty`/Image rows.

The getters import NOTHING from the sibling bridges, so `gameface_bridge` / `battle_bridge` read
them without a cycle. Live state seeds from MSA in `register()`; defaults until then / if MSA absent.

## The non-bool settings: four radios + one slider

`progress_bar_variant`, `progress_bar_size`, and (as of v21) `progress_bar_orientation` /
`progress_bar_alignment` are the mod's **only** settings that are not plain bools, alongside the
`progress_hold_seconds` slider (a clamped int, not an index). MSA's `RadioButtonGroup` stores its
`value` as a **0-based option INDEX**:

- `PROGRESS_VARIANT_EFFICIENCY = 0` (the default), `PROGRESS_VARIANT_MOVING_AVERAGE = 1`.
  ⚠️ **The order FLIPPED in v13** and the stored raw int rides across **unchanged**, so an existing
  user's chosen bar swaps exactly once, silently — accepted deliberately, with no migration (one
  keyed on the old order would be indistinguishable from a fresh `0`);
- `PROGRESS_SIZE_DEFAULT = 0` (the shipped size), `PROGRESS_SIZE_LARGE = 1`;
- `PROGRESS_ORIENT_HORIZONTAL = 0` (the default — every existing user keeps it), `PROGRESS_ORIENT_VERTICAL = 1` (v21);
- `PROGRESS_ALIGN_FIXED = 0` (the default — every existing user keeps it), `PROGRESS_ALIGN_FREE = 1`
  (v21, **renumbered from `2` to `1` at v23** when the radio collapsed from three options to two —
  see "The Fixed-alignment redesign (v23)" above). `PROGRESS_ALIGN_DAMAGE_LOG = 0` /
  `PROGRESS_ALIGN_MINIMAP = 1` still exist as internal, never-stored anchor selectors.

`clamp_variant(v, max_index=PROGRESS_VARIANT_MOVING_AVERAGE)` is **shared** by all four radios;
each passes its own ceiling. `_coerce(key, value)` is a **six-way branch**, and the order matters:

```python
if key in _POS_KEYS:                 return clamp_pos(value)                       # px ints
if key == PROGRESS_VARIANT_KEY:      return clamp_variant(value)                   # radio index
if key == PROGRESS_SIZE_KEY:         return clamp_variant(value, PROGRESS_SIZE_LARGE)
if key == PROGRESS_ORIENTATION_KEY:  return clamp_variant(value, PROGRESS_ORIENT_VERTICAL)
if key == PROGRESS_ALIGNMENT_KEY:    return clamp_variant(value, PROGRESS_ALIGN_FREE)
if key == PROGRESS_HOLD_SECONDS_KEY: return clamp_hold_seconds(value)              # 1-30 int
return bool(value)                                                                 # everything else
```

Falling through to `bool()` would turn index `1` into `True`, round-trip that bool back into MSA
and destroy the setting. **`clamp_variant` must test `isinstance(v, bool)` FIRST** — `bool` is an
`int` subclass, so a plain `int()` silently passes `True` through as a legal `1`. Anything
non-numeric / negative / out-of-range / boolean falls back to `0` — the safe choice for all four
radios, since index 0 is in each case the behaviour the bar always had (or the "revert to
Horizontal / Damage Log" fallback for the two new ones). All four getters
(`progress_bar_variant()`, `progress_bar_size()`, `progress_bar_orientation()`,
`progress_bar_alignment()`) **re-clamp on read** (like the position getters), so a corrupt store
can never leak a bool or a stray index into the window picker or the widget.

`_radio()` (used for **all four** radios) builds the MSA descriptor dict **by hand** — the same shape
`templates.createRadioButtonGroup` emits (`type` / `text` / `varName` / `value` / `inline` /
`options`, plus `tooltip` only when there is one), verified against the decompiled vendored
`templates.pyc`. Two reasons, both load-bearing:

- `_template()` stays a pure, unit-testable dict with **no `gui.aslainMenu` import**;
- **`inline: True` is emitted as a plain KEY, never through the helper's `inline` KWARG.** The
  kwarg raises `TypeError` on MSA < 1.6.1; an unknown *key* just rides through, because MSA does
  no descriptor validation at all. So the repo gets the one-horizontal-row layout — which is what
  lets each radio (all four are 2-option as of v23; Alignment used to be 3-option pre-v23) cost
  one row instead of one stacked row per option — with the version floor structurally impossible.

An API that doesn't know `RadioButtonGroup` (the izeberg fallback) simply skips the control; the
`progress_bar_enabled` master above it is a plain `CheckBox` and keeps working, with
`progress_bar_variant()` reporting its `0` default.

### Why `progress_bar_enabled` is its OWN master (and the radios now sit outside)

A grouped child inherits **that group's master** as its `masterVarName`, so passing the progress
controls as children of the In-Battle group would grey the progress bar out whenever the
*unrelated* In-Battle Widget is off. That hazard is exactly why `progress_bar_enabled` used to sit
**outside** the group with no `masterVarName` at all. Giving it its **own** master — a **second
`_grouped_column1(...)` call whose flat list is spliced onto the first** — keeps the property: its
children grey out with `PROGRESS_BAR_KEY` and nothing else, and `PROGRESS_BAR_KEY` itself stays a
group MASTER, so it still carries no `masterVarName`. Keep the reasoning in `_template()`'s
comment. The **Transitions** master is the same move a third time.

**v13 moved the two radios OUT of that group** and made them standalone `inline` controls — see
the gating section above for why (they describe the bar, not when it shows).

### The option labels are structural (the blank-label episode, now resolved)

- **Option labels live in `settings_i18n._VARIANT_OPTIONS` / `_SIZE_OPTIONS` / `_ORIENTATION_OPTIONS`
  / `_ALIGNMENT_OPTIONS`** (the last two added at v21), `{lang: (opt0, opt1[, opt2])}` tables that
  must stay **BESIDE `_PANEL`, never inside it** — `_PANEL`'s keys are partitioned **positionally**
  by `COL1_KEYS` / `COL2_KEYS`, and an option tuple is not a label/tooltip row. `build()` attaches
  each tuple onto the rendered `VARIANT_KEY` / `progressSize` / `progressOrientation` /
  `progressAlignment` entry, where `_radio()` reads it. Fallback is **whole-tuple, not per-option**
  (the set's meaning is positional, so half-English is worse than all-English).
- Those labels are **STRUCTURAL to MSA**: Aslain folds the option tuple into `_settingsStructure`,
  and `_sync_template_text` rewrites only `text` / `tooltip` — **never `options[].label`**. So
  adding, removing, or merely re-wording/re-localizing an option reaches an existing install
  **only** through a `SETTINGS_VERSION` bump. Unlike every other string in `settings_i18n`. The
  v21 Orientation/Alignment options got their order right at introduction — see
  `[[reordering-a-radio-groups-options-is-a-silent-value-migration]]` for why there's no cheap fix
  later.
- **RESOLVED — all four radios are normal `_PANEL` rows** with real labels ("Mode", "Scale",
  "Orientation", "Alignment"). v10 had blanked the variant radio's label (`_row(u"")`) so its
  options read as direct children of the Progress Bar checkbox; v13 made Mode/Scale standalone
  `inline` controls, so each needed its own name back, and Orientation/Alignment were introduced
  standalone from the start at v21 (Alignment's own option TUPLE shrank 3→2 at v23, still fetched
  the same way). `build()` no longer synthesises a blank entry for `VARIANT_KEY`
  — it only bolts the option tuple onto the rendered row. **All four radios now carry a real
  tooltip** (a later maintainer override waived the "options say it all, so leave it tipless"
  invariant a prior test pass had protected) — Mode/Scale explain something the option words don't
  already say (timing, or Scale's meaning at all since nothing else in the panel spells it out),
  and Orientation/Alignment do the same. None of the four radios contribute to `tipless`; see the
  `tipless == 8` breakdown above.
- **Blanking that label cost the 9 → 10 bump, and un-blanking it rode the 12 → 13 one.** Text is
  *not* part of Aslain's `_settingsStructure` (and varName-less rows aren't collected at all), so
  strictly the empty label would have travelled text-only — but `_sync_template_text` can only
  **OVERWRITE** a key, never **DELETE** one, so a v9 install would have kept the stale "Bar Type"
  tooltip forever on a now-invisible row. Only `setModTemplate` replaces the stored control
  wholesale, and only a forward bump reaches it.

## Registration — soft dep, idempotent, self-healing

MSA (bundled `installer/vendor/aslain.modmenu_2.1.04.wotmod`, import surface
`gui.aslainMenu`; izeberg's `gui.modsSettingsApi` is only a legacy fallback) is a **SOFT
dependency**: `register()` imports it guarded and, if absent, logs-and-returns with defaults
intact (both widgets on) and no panel — never a crash. There is no config file of ours; MSA
owns persistence.

### What MSA 1.6.4 offers → `wotmod:msa-settings`

The vendor capability survey (real conditional gating beyond a group master, the pure
key-setter nature of `enableWhen*` / `conditions`, `createControlsGroup`'s single effect, the
14 component types, zero descriptor validation, varName-less rows excluded from
`_settingsStructure`, and the two-columns reality) is the **harness** rule — read
`wotmod:msa-settings`. The installed copy here is byte-identical to
`installer/vendor/aslain.modmenu_2.1.04.wotmod`; decompile it (`wotmod:debug-repl`'s
`uncompyle6` recipe, or live-REPL introspection if the build is obfuscated) rather than guessing
when a detail is missing.

Mod-relevant consequence: a boolean master's children grey out when it's off, but the disabled
state is **derived from a `masterVarName` / `conditions` binding**, not a per-control `disabled`
field — and a greyed control's value is **still stored and still pushed**, which is why every
"ignored while X is on" rule is folded Python-side below.

`register()` is **idempotent + self-healing** (`_registered` latch): MSA may not be loaded at
our import time (our reverse-domain id `com.14th_ua.moe_calculator` sorts early), so a first
failed attempt leaves the latch False and is retried on the first hangar mount
(`gameface_bridge.attach()` calls `register()` again). The entry point also subscribes the two
feature bridges' `apply_settings` as change listeners.

`_candidate_apis()` / `_primary_api()` are the harness probe verbatim (`wotmod:msa-settings` →
the probe): `gui.aslainMenu` first, the legacy `gui.modsSettingsApi` second and de-duped,
`register()` driving the primary while reset-hooks + template-text sync run on every candidate.

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

### Checklist: a new standalone MSA checkbox that drives a bar VM field

All of these, or it ships half-wired: (1) a `COL1_KEYS`/`COL2_KEYS` slot in `adapter/settings_i18n.py`
at the exact position the control sits in `_template()` (the sync zip is positional); (2) an
`_row(...)` in EVERY one of the 11 language blocks; (3) a
**forward** `SETTINGS_VERSION` bump (a new varName/row reaches an existing install no other way);
(4) the key in `DEFAULTS` plus a getter; (5) fold the getter in **Python** into the VM's `-1`
sentinel rather than letting the JS read the setting; the JS then reads the new field per
`[[new-vm-bool-must-be-read-as-not-false]]` (absent must not collapse to a state).

## Panel prose (defer to `wotmod:i18n-settings`)

Every visible label/tooltip comes from `adapter/settings_i18n.panel_text()` at the client's active
language (English master + per-key fallback; `COL1_KEYS` / `COL2_KEYS` are the wire order MSA and
`_sync_template_text` walk in lockstep — recount them in `settings_i18n.py` (16 and 27 as of v31; 26 and 9 immediately
pre-v24; the v24 column swap reassigned which tuple holds which feature, and v25/v26/v27/v28 each
grew one tuple by one slot, v30/v31 by four — see "The column swap (v24)" above), several of which are `None`
sentinels for the `Empty` spacers and the two preview Images. 11 language blocks. The six
`HEADER_KEYS` entries come out of
`build()` pre-wrapped in `<b>...</b>` — see the `HEADER_KEYS` section above for why that wrap must
live nowhere else.
`modDisplayName` stays the literal English brand. THE gotcha — MSA caches a COPY of the template
text at registration, so on an EXISTING install a client-language change never shows unless
`_sync_template_text` rewrites the stored template text in place (text-only, NO `settingsVersion`
bump) — is the harness rule; see `wotmod:i18n-settings` for the full mechanism and the
`uk`-not-`ua` EU quirk.

**Two mod-specific exceptions to "text is free":** all four radios' **option labels** are
structural (bump-only — see above), and **deleting** a text key (blanking a label) needs a bump too
because `_sync_template_text` overwrites but never removes. Renaming a **`varName`** is never free
either: `merge_settings` / `_apply` iterate `DEFAULTS` keys only with no rename/alias map, so a
rename silently resets every existing user's value. Rename the label, keep the key forever —
`progress_bar_enabled` is the shipped precedent (label went "Next Mark Progress Bar" → "Progress
Log" → "Progress Bar" → "Show"; the key never moved) — and `catBarPosition`'s header text going
"Bar Position" → "Layout" at v21 is the same move on a header key.

## Tests that guard this subsystem

Engine-free pytest (Python 3.13) — run the suite per `moe-build-release`:

- `tests/test_mod_settings.py` — `_coerce` / `clamp_variant` / `merge_settings` / `_apply`, the
  built template's per-column type + `varName` order, the label-only-tooltip regressions, and the
  `tipless == 8` / `spacers == 9` lockstep walk (the spacer branch also asserts the `None`-sentinel
  rows were left untouched).
- `tests/test_settings_i18n.py` — the `COL1_KEYS` / `COL2_KEYS` ↔ `_PANEL` partition and the
  untranslated-leak diagnostic.
- **`tests/test_view_models.py`** — the VMs' hand-numbered slot bookkeeping: `_add*Property` count
  vs each `__init__(properties=N)` default, and every `_set*` / `_getArray` index inside range.
  **Nothing else checks the declared count** (the recording fake VM ignores it), so a flag added to
  a VM without raising `properties` is otherwise green in pytest and broken only in the client.
- **`tests/test_progress_bridge.py`** (+ its sibling `tests/test_efficiency_bridge.py`) — the push
  marshalling for each bar's VM, including `test_push_writes_the_two_transition_flags_master_folded`,
  which is where the master-folding contract is actually pinned.

A layout/varName change also owes a look at `SETTINGS_VERSION` (see above) and, when it adds a
label-only row, at the exact `tipless` count.
