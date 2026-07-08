# HANDOFF: Garage widget box styling — resolved via live tuner (awaiting in-game sign-off)

**Status:** the box "chrome" was tuned by the USER in a browser artifact, the chosen values
were applied to `MoECalculator.css`, and hot-reloaded into `res_mods`. **UNCOMMITTED —
awaiting the in-game "lgtm"** (per the commit-after-sign-off rule).

> This file previously warned a clean session about a guess-and-check *failure*. That is
> **resolved**: instead of guessing, we built a live tuner and let the user pick the exact
> values. Keep that approach if more tuning is needed. (Old failure detail is in git history
> of this file if ever relevant.)

## The approach that worked — the box-style tuner

- **Artifact:** https://claude.ai/code/artifact/82344ffb-827c-46f7-9ba6-892764abf482
- Source HTML: session scratchpad `moe-box-tuner.html` (session-local — see "Regenerating"
  below if it's gone).
- The user tunes ONLY the box chrome (background / border / WG-frame / radius / padding /
  drop shadow / **inner shadow** / hover fades) over **their own full-res 3840×2160 hangar
  screenshot** and copies paste-ready **rem** CSS. Bar content is a fixed mock (not editable).
- **True in-game scale** (this was the key correctness fix, modeled on
  `TASKS/refs/in-battle-overlay-tuner.html`): the stage IS the 3840×2160 physical viewport;
  **1 in-game rem = interfaceScale px** (default **2.0 px/rem** @4K, adjustable slider). The
  box is authored internally at `1px = 1rem`, `#pv-scale` is `transform: scale(IS)`, and the
  `#game` 3840×2160 canvas is scaled `fit*zoom`, centered by mapping the box-centre to the
  stage-centre. The box auto-snaps to the real anchor (`right:46rem; bottom:calc(205.5rem+140px)`).

## Final applied CSS (`MoECalculator.css`, `#moe-root`)

```css
padding: 9rem 16rem 5rem 16rem;
background: rgba(10, 10, 10, 0.33);
border-radius: 0.5rem;
border: 1rem solid rgba(254, 235, 190, 0.2);          /* warm parchment hairline */
box-shadow: inset 0rem 0rem 1rem 0rem rgba(0, 0, 0, 0.33);
transition: background 0.25s ease, box-shadow 0.25s ease;
```
- The `#moe-root::before` **card_border.png 9-slice frame block was REMOVED** (replaced by the
  CSS `border`). `card_border.png` is still bundled beside the CSS but is now **unused** by the
  garage widget.
- Hover fades BOTH fill and inner shadow:
  `#moe-root:hover { background: rgba(10,10,10,0); box-shadow: inset 0rem 0rem 1rem 0rem rgba(0,0,0,0); }`
- Positioning / anchor / width / font / z-index / all bar-content CSS: **untouched**. JS: **untouched**.

## Deployed

`py tools\dev\sync_gameface.py "D:/Games/World_of_Tanks_EU" 2.3.0.1` → res_mods (garage
hot-reload; **no relaunch**). In-game: **toggle Tech Tree ↔ Garage** to re-inject.

## NEXT SESSION — do this

1. **Get the in-game verdict.** Two specific things to confirm:
   - ⚠️ **`inset` box-shadow renders in Coherent/Gameface — UNVERIFIED.** Outer `box-shadow`
     is known to render (the track + tooltip use it); **inset is not confirmed**. If the inner
     darkening or its hover fade does NOT show in-game, swap it for a **radial-gradient inner
     vignette** (a child `<div>`/`::after` with `background: radial-gradient(...)`, which
     Gameface always paints) — same look, engine-safe. Only that swap needs code; the rest is
     copy-paste from the tuner.
   - The warm hairline `border` at `0.2` alpha over the live hangar.
2. **On "lgtm": commit.** Scope = garage widget box chrome only (CSS `border` + inner shadow,
   drop `card_border` frame, hover dual-fade). Garage-only CSS — **no Python, no version bump**.
   Then the deploy → verify → commit loop for this item is done; prune this file + the
   `TASKS.md` backlog entry.
3. **If rejected:** re-open the tuner (URL above) for the user to re-tune and paste new values.

## Uncommitted state at handoff

- **Mine, for this commit:** `src/res/gui/gameface/mods/14th_ua/MoECalculator/MoECalculator.css`
  (box chrome; ~18 insertions / 38 deletions — mostly the removed `::before` block + comments).
- **Pre-existing dirty (NOT mine, do NOT fold into this commit):** `TASKS.md`,
  `TASKS/mod-positioning-handoff.md`, and assorted untracked `TASKS/*.md` notes.

## Regenerating / extending the tuner

The published artifact is **self-contained (~2 MB)**: it embeds the user's full-res
3840×2160 hangar JPEG + `card_border.png` as data URIs. If the scratchpad `moe-box-tuner.html`
is lost, rebuild it as a plain HTML page and inject the two data URIs (hangar screenshot from
the clipboard/PNG; `card_border.png` from the widget dir). Model recap: box `1px=1rem`;
`#pv-scale scale(IS)`; `#game` 3840×2160 scaled `fit*zoom`; box centred by centre→centre map;
controls emit rem CSS for `#moe-root` / `::before` / `:hover`. Border-image in the PREVIEW uses
the inlined data URI, but the emitted OUTPUT must say `url(card_border.png)` (bare sibling —
`img://`/`data:` fail for border-image in Coherent).

## Reference — if the user ever wants to MATCH the native ammo cell instead

The user did **not** go this route (they chose a custom hairline + inner-shadow look via the
tuner). Client Gameface CSS facts, if revisited, are in `TASKS/garage-box-style-match.md`:
resting slot cell = `linear-gradient(rgba(0,0,0,.45))` only, no bevel; `toggle.png` = gold
*button* state, `border.png` = coral highlight (NEITHER is the resting frame); section panels =
opaque `#4d4c45` + a faint white top sheen.
