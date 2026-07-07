# Research: Damage icon renders too small (visible glyph fills ~¼ of its canvas)

_Submitted: "increase icon size" — the damage glyph next to the current-damage readout still
looks small even after enlarging its box · Status: **SHIPPED 2026-07-06** (front-end only, uncommitted)_

## Resolution (what shipped)
Took **option 2 (sharper source + zoom)** but with a correction. Measuring the candidates
revealed the `battleCondition/128` glyph's apparent crispness (the note's "49×50") was **glow
inflation**: its *solid* glyph is only 28×28, wrapped in a ~2900px soft radial glow (alpha
16-48) baked into the art. At `background-size: 260%` that glow became a murky haze behind the
glyph ("clean up the background"). Switched to `personal_missions_30/quest_type/128x128/
icon_battle_condition_damage.png` — the **same 28×28 glyph on FULLY transparent** pixels (~75
fringe px, no glow) — at the same `background-size: 260%`, so identical glyph size, clean bg.
No bundled asset needed. Also pulled the icon in: `margin-left` 6rem → **0rem** (per user).
Final CSS (`#moe-root .moe-cur-icon`): `width/height 22rem`, `margin-left 0rem`,
`vertical-align -5rem`, `background-size 260%`, quest_type/128 source. `background-size` is the
size knob if revisited; a **negative** `margin-left` is the lever to tighten past the glyph's
transparent padding.

---


## Summary
The damage icon was added and moved to the RIGHT of the current-damage number (user's picks,
shipped this session). The user then asked to make it bigger; the CSS box was grown 17rem →
22rem but the **visible glyph barely changed size**. Root cause: the chosen art is a small
glyph centred in a mostly-transparent canvas, so `background-size: contain` fits the *canvas*
(incl. the empty padding), leaving the actual glyph tiny. Fix = zoom past the padding
(`background-size` > 100%) and/or switch to a higher-res, tighter-cropped sibling asset.

## Findings — current state (shipped, uncommitted)
- **DOM** (`MoECalculator.js`, `ensureRoot()`): `.moe-cur-dmg` then `.moe-cur-icon` inside
  `.moe-cur` (icon is now to the RIGHT of the number).
- **CSS** (`MoECalculator.css`, `#moe-root .moe-cur-icon`):
  ```css
  display: inline-block;
  width: 22rem; height: 22rem;   /* square box (source is square) */
  margin-left: 6rem;             /* gap to the right of the number */
  vertical-align: -5rem;         /* baseline nudge */
  background-image: url(img://gui/maps/icons/personal_missions_30/quest_type/64x64/icon_battle_condition_damage.png);
  background-repeat: no-repeat; background-position: center; background-size: contain;
  ```
- The readout number (`.moe-cur`) is `16rem`.

## Root cause — measured opaque bounding boxes (live, via .NET alpha scan, A>16)
The `icon_battle_condition_damage` art is a small centred glyph in a big transparent frame:

| asset | canvas | opaque glyph | fill | zoom to fill box |
|---|---|---|---|---|
| `personal_missions_30/quest_type/64x64/...damage.png` **(current)** | 64×64 | **15×15** | **23%** | ~427% |
| `personal_missions_30/quest_type/128x128/...damage.png` | 128×128 | 28×28 | 22% | ~457% |
| `quests/battleCondition/128/icon_battle_condition_damage_128x128.png` | 128×128 | **49×50** | **38%** | ~261% |
| `quests/battleCondition/128_decor/icon_battle_condition_damage_128x128.png` | 128×128 | 58×56 | 45% | ~221% |
| `library/dossier/avgDamage40x32.png` (different glyph, for ref) | 40×32 | 36×26 | 90% | ~111% |

So at `background-size: contain` in a 22rem box, the current 64×64 source paints a glyph only
~23% as wide as the box — hence "still small." Growing the box grows the padding too.

## Suggested approach (pick one; keep the glyph the user chose)
1. **Cheapest — zoom past the padding, same asset.** Keep the path; replace
   `background-size: contain` with an explicit oversize, e.g. `background-size: 420%;`
   (glyph fills the box; transparent padding just crops off since `background-position:center`).
   Downside: the visible glyph is only 15px of real art zoomed ~4× → soft at large sizes.
2. **Recommended — same glyph, sharper source.** Switch to
   `img://gui/maps/icons/quests/battleCondition/128/icon_battle_condition_damage_128x128.png`
   (49×50 real glyph, 38% fill) and set `background-size: ~260%` to fill. Higher-res core →
   crisper than option 1. The `128_decor` variant (45% fill, ~220%) is fuller still but has a
   decorative ring — eyeball whether that reads as "damage" or as clutter at this size.
3. **Fallback — a natively tight glyph.** If zoom looks soft/off-centre, `dossier/avgDamage40x32`
   fills 90% at `contain` (no zoom, crisp) — but it's a *different* glyph the user did not pick;
   confirm before switching.

Whatever the zoom, re-check `width/height` and `vertical-align` so the (now larger) glyph still
sits on the number's baseline; the box can stay ~20–24rem with the zoom doing the enlarging.

## Touch points
- `MoECalculator.css` — `#moe-root .moe-cur-icon` (`background-image`, add `background-size`,
  tweak `vertical-align`).
- `MoECalculator.js` — only if the asset path changes (it's hard-coded in the CSS, so likely
  CSS-only).

## Verification
- Front-end only → hot-reload: `python tools\dev\sync_gameface.py "D:/Games/World_of_Tanks_EU" 2.3.0.1`
  then Tech Tree ↔ Garage. Eyeball the glyph size next to the number over a bright hangar.
- The live-screenshot loop (clipboard STA runspace, see `widget-polish-handoff.md`) if fine
  size-tuning is needed.

## Open questions
- Is a slightly soft glyph (option 1) acceptable, or is the sharper 128px source (option 2)
  worth the asset swap?
- Target size — fill the box, or a specific glyph height relative to the 16rem number?
