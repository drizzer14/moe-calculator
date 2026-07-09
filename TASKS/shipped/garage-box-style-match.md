# Research: Garage widget — match the setup-slot box style EXACTLY (2nd pass)

_Submitted: "Second pass on exactly matching the style of the crew/equipment/directive/ammo/consumables boxes. First pass yielded bad results, degrading the visuals and not delivering anything of value. When I say 'match styles exactly', it means to look for the in-game CSS." · Status: shipped_

> **Supersedes** `TASKS/garage-widget-ammo-border.md` (the 1st pass — border-texture swap only).
>
> ⚠️ **CORRECTION (read first):** the actual **hangar bottom-bar** crew/equipment/directive/ammo/
> consumable boxes are **Scaleform FLASH** (`AmmunitionPanel.swf`), **not** Gameface CSS. The
> `lobby/tanksetup/…/Container.css` values ported below are from the **full-screen tank-setup
> view**, a *different* surface — which is why porting "the CSS" to match the bottom-bar boxes has
> failed both passes. The Gameface values below are still a reasonable *visual approximation* (the
> two surfaces are meant to look alike), but the **authoritative source for the bottom-bar boxes is
> the SWF** — decompile `AmmunitionPanel.swf` for the real slot dimensions / fill / frame before
> treating any value here as exact. See memory `[[hangar-boxes-are-flash]]`.

## Summary

The garage widget (`#moe-root`) should read as one of WG's native garage boxes. The 1st pass
swapped only the border texture (`card_border` → `tanksetup/panel/toggle`) and **degraded the
look** — it delivered nothing usable. This 2nd pass grounds the match in the **actual in-game
CSS** for those boxes and matches the whole box (fill + frame + corners + hover), not just the
border.

## Findings — the in-game CSS (ported by value)

### The one box that matters: `SlotParts/Container`
The **shells (ammo), consumables, equipment (optional devices), and directives (battle boosters)
slots are ALL the same component** — `lobby/tanksetup/common/SlotParts/Container/Container.css`
(the `toggle` texture is referenced 10× across `tanksetup/`, always via this Container). So
"match all of them" collapses to matching **one** box. Verbatim (hashes stripped):

```css
/* the slot box itself — 54rem square, flat 45%-black fill */
.Container_base_ {
    display: flex; justify-content: center; align-items: center;
    min-width: 54rem; height: 54rem;
    position: relative;
    background-image: linear-gradient(rgba(0,0,0, .45), rgba(0,0,0, .45));
    cursor: pointer;
    /* NO border-radius — the box is square */
}

/* the frame (9-slice bevel with a baked-in thin black outer rim) */
.Container_base__toggle_ {
    border-image-source: url('R.images.gui.maps.icons.tanksetup.panel.toggle');
    border-image-slice: 4 fill;
    border-image-width: 4rem;
    /* border-image-repeat unset -> defaults to `stretch` (WG does NOT tile it) */
    cursor: pointer;
}

/* hover = WG COMPOSITES a white layer OVER the dark fill (it brightens, ~ +15–20%) */
.Container_base__hangar_:hover {
    background-image: linear-gradient(rgba(0,0,0,.45),rgba(0,0,0,.45)),
                      linear-gradient(rgba(255,255,255,.15),rgba(255,255,255,.15));
}
.Container_base__toggle_:hover {
    background-image: linear-gradient(rgba(255,255,255,.2),rgba(255,255,255,.2));
}

/* optional inner sheen some states carry */
box-shadow: inset 0 0 12rem rgba(255,255,255, .05);
/* selected state = gold ring (NOT needed for the widget): 0 0 0 1rem rgba(249,201,111,.5) */
```

- **Texture** `R.images.gui.maps.icons.tanksetup.panel.toggle` → `gui/maps/icons/tanksetup/panel/toggle.png`
  (**30×20 px, 561 B**, in `gui-part1.pkg`). Light cream 9-slice bevel with a **thin black outer
  rim baked into the outermost pixel** — that rim IS the "outer black border" the 1st report
  wanted; you get it free from the texture, no extra CSS border. A copy is already saved at
  **`TASKS/refs/panel_toggle.png`**. (`border.png`, 56×56 orange, is the *selected/hover* frame —
  do NOT use it.)

### Crew boxes are IDENTICAL to the others (per user)
The crew tankman slots share the same box visual as the setup slots — same 54rem box with the
`linear-gradient(rgba(0,0,0,.45))` fill (`crew/TankmanContainerView`, `crew/widgets/TankmanInfo`).
Only the **tooltips** differ (crew tankman tooltip vs the ammo/module blocks tooltip) — a separate
concern, NOT part of this box-styling task. (The `components/button/back_*` / `popover_bg`
textures in `HangarCrewWidget`/`CrewWidget` are the crew panel's *action buttons*, not the slot.)
So all five box types the user named map to the ONE `Container` box above — match that.

### The panel behind the slots (alternative target for a WIDE bar)
The widget is a **wide, short bar** (315rem wide, ~40rem tall), whereas `Container` is a 54rem
**square**. The container the slots sit in (`AmmunitionPanel.css` / `HangarAmmunitionSetup.css`)
uses a panel background that may read better on a wide box:
```css
background: linear-gradient(180deg, rgba(255,255,255,.1) 0%, rgba(255,255,255,0) 100%) #393830; /* darker */
/* also seen: … #4d4c45 (lighter); */  border-radius: 3rem;
```
This is a real design fork — see Open questions.

## Root cause of the 1st pass looking bad (hypotheses, from the value deltas)

The current `#moe-root` (MoECalculator.css:20–86) differs from the real box on **five** axes; the
1st pass fixed only the texture, leaving the visual clashes:
1. **`border-radius: 2rem` (line 62) vs square** — a rounded box under a square 9-slice bevel
   mismatches; the bevel corners get clipped / the rim rounds oddly.
2. **`opacity: 0.5` on the frame (line 83)** — halves the bevel weight; WG draws it at full opacity.
3. **`repeat` tiling (line 82) vs `stretch`** — tiling a 30×20 corner-bevel across a wide bar
   repeats the rim mid-edge; WG stretches the 9-slice so only the center fills.
4. **Fill `rgba(10,10,10,.28)` (line 59) vs `rgba(0,0,0,.45)`** — the widget fill is fainter/warmer.
5. **Inverted hover** (line 92 fades the dark fill OUT to transparent) — WG does the OPPOSITE
   (composites white ON, brightening). The mod's inversion is deliberate but reads non-native.
6. **Aspect ratio** — even done right, a bevel authored for a 54rem square stretched across a
   315rem-wide bar can look thin/odd on the long edges. Verify in-game; if bad, prefer the panel
   background (above) over the slot bevel for the wide shape.

## Suggested approach

Port the `Container` box **exactly**, then eyeball the wide-aspect caveat:
1. Bundle the texture as a bare sibling (`border-image` only paints a relative sibling — `img://`
   / `data:` silently drop): copy `TASKS/refs/panel_toggle.png` →
   `src/res/gui/gameface/mods/14th_ua/MoECalculator/panel_toggle.png`.
2. `#moe-root`: `background: linear-gradient(rgba(0,0,0,.45),rgba(0,0,0,.45));` (or keep the flat
   `rgba(0,0,0,.45)`); **drop `border-radius`** (square); keep `padding`.
3. `#moe-root::before`: `border: 4rem solid transparent; border-image: url(panel_toggle.png) 4 fill / 4rem;`
   — **remove `opacity: 0.5` and the `20 / 5rem repeat` line.** (Optional inner sheen:
   `box-shadow: inset 0 0 12rem rgba(255,255,255,.05)` on `#moe-root`.)
4. Hover: decide (Open questions) — either adopt WG's native brighten (composite
   `linear-gradient(rgba(255,255,255,.15),…)` over the fill) or keep the current fade-out.
5. **Then look at it in-game** beside a real slot; if the stretched bevel reads wrong on the wide
   bar, switch the frame to the panel background (`#393830` + `3rem` radius, no border-image).

## Touch points
- `src/res/gui/gameface/mods/14th_ua/MoECalculator/MoECalculator.css` — `#moe-root` (fill,
  radius, hover ~59–92) and `#moe-root::before` (frame ~72–86).
- `src/res/gui/gameface/mods/14th_ua/MoECalculator/panel_toggle.png` — NEW sibling texture.
- `tools/dev/sync_gameface.py` `ASSETS` (line 27) — add `"panel_toggle.png"`; **retire
  `"card_border.png"`** here + delete the file IF nothing else uses it (grep: MoEBattle.css only
  *mentions* it in comments as precedent — it doesn't load the file; MoECalculator.css:82 is the
  only real use, which this change removes).
- `build/build_wotmod.py` — no change (walks `src/`, packages the new PNG automatically).

## Verification
- Hot-reload the garage surface (no relaunch needed):
  `& "<py3>" tools\dev\sync_gameface.py "D:/Games/World_of_Tanks_EU" 2.3.0.1` → in-game switch to
  Tech Tree and back to Garage.
- Put `#moe-root` directly beside a real shell/consumable/equipment slot (bottom of garage) and
  compare frame weight, cream bevel, black outer rim, corners, fill tone — at **1× AND 2×**
  interface scale. Re-shoot the `TASKS/refs/comparison_boxes_vs_mod.png` side-by-side.
- If `border-image` doesn't paint → the sibling PNG isn't loading (check filename/case + that it
  deployed).
- `pytest` stays green (no Python touched).

## Open questions
- **Slot box vs panel background** for the wide bar? Match the square `Container` bevel, or the
  `AmmunitionPanel` panel bg (`#393830` + `3rem` radius)? Decide from the in-game side-by-side.
- ~~Crew scope~~ — resolved: crew boxes are identical to the setup slots (same `Container` box);
  only their tooltips differ (out of scope here). All five named types = the one box.
- **Hover**: keep the widget's current fade-to-clear, or adopt WG's native brighten-on-hover?
- **Fill tone**: adopt WG's exact `rgba(0,0,0,.45)`, or keep the current warmer/fainter tone?

## Cross-references
- `wotmod-gameface-widget` skill → "Matching WG's look: read the client's own Gameface CSS" +
  "Native chrome: border-image from a sibling PNG" (the extraction recipe + sibling-PNG trick).
- `TASKS/garage-widget-ammo-border.md` — the superseded 1st-pass note (border-only).
- `TASKS/refs/panel_toggle.png` — the extracted slot texture (ready to copy in).
