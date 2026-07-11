# MoE hover tooltip — SHIPPED (shared .wg-tooltip component; in-game LGTM; committed)

The garage hover tooltip reproduces the client's own **Marks-of-Excellence award tooltip**
(Vehicle statistics → Awards), keyed by mark count 0..3: the big nation mark art (marksOnGun
**180×180** atlas) top-right, the achievement **title**, the localized **current-ratio** line
(the percentile highlighted white), the **description** (how to earn the next mark), a
**divider**, and the 5-bullet **condition** block. All text is the client's own strings
(dumped from the live EU 2.3.0.1 client into `adapter/i18n.py`, pushed via `MoEVM.labels`).
`TOOLTIP_ENABLED = true`. **Verified in-game (LGTM) and committed.**

Env: WoT = `D:/Games/World_of_Tanks_EU`, **EU 2.3.0.1**. Py2.7 = `C:\Python27\python.exe`
(packaging); Py3.13 = system `python` (tests).

## Final design (this is what shipped)

**Shared `.wg-tooltip` / `.wg-tip-*` vocabulary, standalone copy.** The tooltip reuses the SAME
class names + CSS as the sibling **wgmod-research-progress** mod's tooltip, so both render
identically — but the mods stay STANDALONE: MoE ships its OWN copy of the rules, scoped to
`#moe-tooltip` (the sibling scopes the same classes under `#wgmod-root`), so two installed mods
never collide. The reusable recipe is documented in the **wotmod-gameface-widget** harness skill.
DOM: `#moe-tooltip.wg-tooltip > (.wg-tip-main.wg-tip-main-mark > (.wg-tip-text > .wg-tip-name +
.moe-tip-ratio) + .wg-tip-icon.wg-tip-icon-mark) + .moe-tip-descr + .wg-tip-div + .wg-tip-cond`.
MoE-local additions (not part of the shared set): `.wg-tip-icon-mark`/`.wg-tip-main-mark`,
`.wg-tip-icon-unearned`, `.moe-tip-ratio`/`.moe-tip-descr`, `.moe-tip-hi`, `.moe-tip-empty`.

**Mark-art icon:** the 180×180 source is a SQUARE canvas but the glyph inside is WIDE (rows
~25..153, ~25/27px transparent bands top/bottom). So the icon box takes the GLYPH aspect
(64×46, not 64×64) with `background-size:100% auto` + `background-position:center`, cropping the
bands — otherwise the square-in-square `contain` fit rendered the glyph vertically centred, ~9rem
below the box top (read as "icon lower than the title").

**Current-ratio white % — THE engine gotcha.** This Gameface/Coherent build has **NO inline
formatting**: a single text node wraps fine, but wrapping any run in a child element (span, font,
`<i>`, any `display` — inline included) puts it on its OWN line. Confirmed by a live DOM probe
(a default `<div>` is `block`; even inside a forced `display:block` container two `display:inline`
spans landed on different lines). **The only horizontal-layout primitive is flexbox.** So the
ratio line is a `display:flex; flex-wrap:wrap` container and `ratioHtml()` emits **one `<span>`
per WORD** (each a flex item that wraps like text); the `%` word carries `.moe-tip-hi` (white).
Word spacing = `margin-right` on each item (NOT `gap` — older Coherent may not support it). The
WG template's `%(color_tag_open/close)s` are marked with `\x01`/`\x02` sentinels, stripped during
tokenization. See [[hover-tooltip]].

**Chrome:** WG's 9-slice tooltip frame via `border-image-source: url('img://…/tooltip/
background_with_border.png')` (the **LONGHAND resolves `img://`** where the `border-image`
shorthand does not) over an `rgba(20,20,20,.95)` fallback + `0 0 32rem` shadow; `#ede6d9` title /
`#8e867d` body tokens; width-stretched `divider.png`. `tooltip_bg.png`/`tooltip_divider.png` stay
bundled as fallbacks.

**Layout tweaks (final):** description is a FULL-WIDTH paragraph (moved OUT of `.wg-tip-main` so
the icon's reserved column doesn't narrow it), `margin-bottom: 7rem`. `#moe-root` bottom padding
9→8rem (bottom-anchored, so this also lowers the bar ~1rem).

## Files (committed this session)
`MoECalculator.js`, `MoECalculator.css`, `adapter/i18n.py`, `tests/test_i18n.py`. 215 tests pass,
DEBUG ships False. Harness skill `wotmod-gameface-widget/SKILL.md` also updated (outside this repo).

## Remaining
1. **Rebuild the packaged `.wotmod`** with WoT CLOSED so it carries the final front-end and the
   `res_mods` overlay is cleared: `C:\Python27\python.exe build\deploy_wotmod.py --clean-overlay`.
   (Verified via hot-reloaded overlay only; source is committed ahead of the local package.)
2. Update the **moe-garage** project skill's "Hover tooltip" section (still says DISABLED).
3. Release bump if shipping (see wotmod-release).
