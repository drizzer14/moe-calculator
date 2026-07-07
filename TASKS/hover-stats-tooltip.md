# Research: Hover tooltip — full stats breakdown (localized, with icons)

_Submitted: "Tooltip on widget hover that breaks down all stats with localizeable text and
icons" · Status: open_

## Summary
On garage-widget hover (the round-4 whole-widget hover already exists), show a tooltip that
breaks down all MoE stats as rows of **icon + localized label + value**. This is the first
feature needing **user-facing text**, so it also introduces the mod's localization plumbing.

> **Reusable how-to lives in the harness (added this session) — don't re-derive it here:**
> - Tooltip mechanics (build your own HTML tooltip, don't hook WG's `getToolTipMgr`; hidden
>   `pointer-events:none` node, top z-index, show/position on hover, edge-clamp): see
>   **wotmod-gameface-widget → "Tooltips (build your own — don't hook WG's)"**.
> - Localization (Python resolves per `helpers.getClientLanguage()`, bundled `{key:{lang:…}}`
>   dict via `helpers.getLocalizedData`, push strings into the VM; JS never hardcodes English):
>   see **wotmod-architecture → "Localization (Python side)"** and **wotmod-gameface-widget →
>   "Localization (render side)"**.

## What data already exists (mostly a re-presentation)
The VM already carries the values — the tooltip is largely relabeling existing fields:
- `curAvgDamage`, `curPercent` (current combined damage + %), `marks` (0–3), `hasData`.
- `ticks[]` each with `percent` (65/85/95), `markCount` (1/2/3), `damageRequired`, `reached`.
- the 100% goalpost damage (the `end`/`D100` value).
What's **not** in the VM yet and may be worth adding (else compute in JS): **damage to next
mark** = `ticks[nextUnreached].damageRequired − curAvgDamage`.

## Proposed tooltip contents ("all stats")
Rows (each = `img://` icon + localized label + value); confirm the exact set with the user:
- Current combined damage · current % (with the zone colour).
- Marks earned (0–3).
- Per mark 1/2/3: `NN% · <damageRequired>` and reached/not (✓), + damage-to-go for the next.
- 100% goalpost damage.
- (Optional) damage needed for the next mark.

## Localization — introduce it here (project specifics)
No i18n infra exists yet (the widget is number-only). Add it per the harness pattern:
- **NEW `adapter/i18n.py`** — a bundled `LABELS = {key: {'en':…, 'ru':…, …}}` dict + a
  `labels_for(lang)`-style resolver using `helpers.getClientLanguage()` (fall back `'en'`).
  Pure/guarded so it imports under pytest. Ship at least `en` + the languages lebwa ships
  (`ru`, `de`, `pl`, `uk`) to match the audience.
- **Push the labels as ONE JSON bundle prop** (`labels`) on the VM (idiomatic — the JS
  Lifecycle note already expects a JSON labels/i18n bundle parsed with a missing-key-safe
  helper), rather than a string prop per label. Add the prop in `bridge/view_models.py`
  (`MoEVM`) + marshal in `gameface_bridge.py:push()`. Resolve once per language (cache).
- Re-push on nothing new (language doesn't change mid-session) — resolve at attach/first push.

## Front-end (per the harness Tooltips section)
- Build a hidden `.moe-tooltip` node in `ensureRoot()` (`MoECalculator.js`); populate it in
  `render()` from the model values + the parsed `labels` bundle.
- **Trigger:** the widget already captures hover (`#moe-root { pointer-events:auto }`, round 4)
  — attach `mouseenter`/`mouseleave` on `#moe-root` to toggle the tooltip (a whole-widget
  hover, so a fixed panel beside/above the widget is fine; no cursor-follow needed). Edge-clamp
  so it never leaves the screen. Keep the tooltip `pointer-events:none`.
  - (Note: the harness Tooltips guidance assumes the JS-driven-hover-on-a-hot-layer model; this
    mod took the `pointer-events:auto` + hover route in round 4, so trigger off `#moe-root`
    hover directly — same outcome.)
- Icons: reuse the existing damage glyph + mark glyphs (`mark_1/2/3`); add percent/marks
  glyphs via `img://` as needed (`background-image` divs, not `<img>`).
- Don't rebuild the tooltip's host node every render (it drops the open tooltip mid-hover).

## Touch points
- NEW `adapter/i18n.py` (+ a unit test for the resolver).
- `bridge/view_models.py` — add the `labels` string prop to `MoEVM`.
- `bridge/gameface_bridge.py` — resolve + marshal `labels` in `push()`.
- `MoECalculator.js` — `.moe-tooltip` DOM in `ensureRoot()`, populate in `render()`, hover
  toggle on `#moe-root`.
- `MoECalculator.css` — `.moe-tooltip` styling (hidden default, `pointer-events:none`, high
  z-index, rows).

## Verification
- Live in-garage: hover the widget → tooltip shows all rows with icons + values; leaves on
  mouseout; edge-clamped; does NOT steal drag-to-rotate.
- Switch the client language (or force one in `i18n.py`) → labels change; icons unchanged.
- New/played tanks both render sensibly (ties in with the "0/0%" fix and `hasData`).
- `pytest` covers the `i18n.py` resolver (fallback to `'en'`, unknown lang, missing key).

## Open questions
- Exact stat set + label wording for each row?
- Which languages to ship (en + ru/de/pl/uk)?
- Fixed panel beside the widget (assumed) vs. cursor-following?
- Add "damage to next mark" to the VM, or compute it in JS from `ticks` + `curAvgDamage`?
