# Research: In-battle overlay — sign as a colored text GLOW, not colored text

_Submitted: "For in-battle widget, replace text color with colored text glow." · Status: shipped (commit `5953a72`)_

## Summary

Today the in-battle overlay signals good/bad by recoloring the TEXT itself green/red (live
damage vs projected avg; signed MoE delta). Change it so the numerals stay **white** and the
sign is carried by a **colored glow** (a green/red `text-shadow` halo) instead. Neutral/at-par
stays plain white. Same two elements are affected; this is a *how it's colored* change, not
*which metrics*.

## Findings — how sign color works today

- `MoEBattle.js` `colourBySign(el, sign)` (lines 64–68) toggles `.mb-up` (sign>0) / `.mb-down`
  (sign<0) on two elements in `render()`: the live-damage value `.mb-cd` (line 115) and the
  delta number `.mb-delta-num` (line 123). Neutral = no class.
- `MoEBattle.css`:
  - Base numerals are white with a soft DARK drop shadow for legibility over bright/dark map:
    `.mb-value { color:#fff; text-shadow: 0 0 1rem rgba(0,0,0,.5); }` (159–165); `.mb-delta`
    the same (176–181). `text-shadow` inherits, so `.mb-delta-num` picks up `.mb-delta`'s.
  - Sign states currently override only the **fill color** (186–194):
    ```css
    .mb-value.mb-up,  .mb-delta-num.mb-up   { color: #61bf22; }  /* green */
    .mb-value.mb-down,.mb-delta-num.mb-down { color: #c81400; }  /* red */
    ```
- The row icons already use a white glow: `.mb-ico { filter: drop-shadow(0 0 .5rem #fff); }`
  (146) — so a colored glow on the numbers would visually rhyme with the existing look.

**⚠ Palette discrepancy to resolve:** the deployed CSS uses green `#61bf22` / red `#c81400`
(flag_team pair), but `TASKS/shipped/in-battle-widget-colors.md` records green `#7BEC37` / red
`#D3443F` as "shipped." The file is source of truth (currently `#61bf22`/`#c81400`); confirm
which hex the glow should use (see Open questions + that note's full palette table).

## Suggested approach (pure CSS)

Stop overriding `color` in the sign states (let the base white win) and instead override
`text-shadow` with a colored glow — **keeping the dark drop shadow layered underneath** for
legibility (a colored halo alone gives no dark contrast over a bright background). `text-shadow`
takes a comma list; stacking two colored shadows at different radii reads as a stronger glow.

```css
.mb-value.mb-up,
.mb-delta-num.mb-up {
    color: #ffffff;                              /* stay white (was #61bf22) */
    text-shadow: 0 0 1rem rgba(0,0,0,.5),        /* keep dark legibility drop */
                 0 0 3rem rgba(97,191,34,.9),    /* green glow (#61bf22) */
                 0 0 6rem rgba(97,191,34,.6);    /* wider, softer second pass */
}
.mb-value.mb-down,
.mb-delta-num.mb-down {
    color: #ffffff;                              /* stay white (was #c81400) */
    text-shadow: 0 0 1rem rgba(0,0,0,.5),
                 0 0 3rem rgba(200,20,0,.9),      /* red glow (#c81400) */
                 0 0 6rem rgba(200,20,0,.6);
}
```
- Radii/alphas above are a STARTING point — tune in the overlay tuner (Verification). White text
  + a soft colored halo is inherently subtler than a colored fill; err toward a punchier glow so
  the sign still reads at a glance in a busy HUD.
- Neutral/at-par (no `.mb-up`/`.mb-down`) is unchanged: white + dark drop shadow only, no glow.
- No JS/Python change — `colourBySign()` already applies the classes; only the CSS meaning of
  those classes changes.

**Optional coherence:** if the glow reads well, consider tinting the row icons' white glow
(`.mb-ico` `drop-shadow #fff`, line 146) toward the same sign color — but the icons are fixed
per row (not sign-driven), so that's a separate aesthetic call, not part of this ask.

## Touch points

- `src/res/gui/gameface/mods/14th_ua/MoECalculator/MoEBattle.css` **only** — the `.mb-up`
  (186–189) and `.mb-down` (191–194) rules: drop the `color` override → `#fff`, add the colored
  `text-shadow`. Base `.mb-value`/`.mb-delta`/`.mb-sep` untouched.
- `MoEBattle.js` `colourBySign()` (64–68) — no change (documents where the classes come from).

## Verification

- Preview candidate glow color/radius/alpha in the **overlay browser tuner**
  (`tools/dev/gen_overlay_tuner.ps1` → `TASKS/refs/in-battle-overlay-tuner.html`) over the real
  4K battle backdrop — this window has **NO hot-reload** (resources pin at launch), so the tuner
  is the cheap iteration path before a rebuild.
- Then rebuild + **relaunch** (client CLOSED):
  `& "C:\Python27\python.exe" build\deploy_wotmod.py "D:/Games/World_of_Tanks_EU" 2.3.0.1`.
- In a battle/replay confirm: white numerals with a clearly green (above-avg / improving) or red
  (below-avg / dragging) halo, still legible over BOTH bright and dark map areas, at 1× AND 2×
  interface scale. Neutral state is plain white.
- No unit tests apply (pure presentation; `test_battle_builder` unaffected).

## Open questions

- **Glow color = which hex?** The current fill pair (`#61bf22`/`#c81400`) or the vivid pair from
  the colors note (`#7BEC37`/`#D3443F`)? A brighter, more saturated color usually glows better;
  the tuner settles it. Resolve the file-vs-note discrepancy above at the same time.
- **Glow strength** — how punchy? (radius, alpha, one vs two stacked shadows). Tradeoff: a glow
  is less immediately legible than a colored fill; if the sign must be unmistakable, a strong
  glow or keeping a *slight* color tint on the text may be needed — confirm the user truly wants
  the text fully white.
- Tint the row **icons'** glow to match, or leave them white? (Out of scope by default.)

## Cross-references

- `TASKS/shipped/in-battle-widget-colors.md` — the green/red palette (full `gui_colors.xml`
  table) + the deployed-hex vs note discrepancy.
- `TASKS/shipped/in-battle-moe-styling.md` — the overlay tuner + the no-hot-reload constraint.
