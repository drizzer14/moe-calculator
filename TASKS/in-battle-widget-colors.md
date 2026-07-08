# Research: In-battle widget green/red — use WoT-native battle colors

_Submitted: "Use a different green for in-battle widget (one from icons)" + "Same for red, look for appropriate in-battle color" · Status: SHIPPED (pending relaunch eyeball)_

> **DONE 2026-07-07:** user picked (via the color-preview artifact) a custom mix —
> green **`#7BEC37`** (`greenColor` vivid alias) + red **`#D3443F`** (`redVehicleNameColor`).
> (Green was briefly `#61BF22` `flag_team_green`, then changed to the vivid alias.)
> Applied at `MoEBattle.css` `.mb-up`/`.mb-down`. Pure CSS swap; no JS/Python change.
> Not yet eyeballed in a live battle (no hot-reload for this window → needs relaunch).

## Summary

Recolor the in-battle overlay's positive/negative text (the "above avg" / "improving" green
and the "below avg" / "dragging" red) to colors that read as WG-native in the battle HUD,
replacing the current pastels. The premise was "one from icons" — but see Findings §B: the two
icon glyphs are **greyscale**, so there is no green to pull from them. The right source is
WoT's own battle color palette, which I extracted from the live client (exact hex below).

## Findings

### A. Current widget colors (what we're replacing)
- Green: **`#8fd18f`** (143,209,143) — `MoEBattle.css:173-176`
  (`.mb-value.mb-up`, `.mb-delta.mb-up`).
- Red: **`#e08585`** (224,133,133) — `MoEBattle.css:178-181`
  (`.mb-value.mb-down`, `.mb-delta.mb-down`).
- Applied to: the live-damage value vs projected avg (row 1) and the signed delta (row 2),
  toggled by `colourBySign()` in `MoEBattle.js:64-67`. White (`#ffffff`) is the neutral/at-par
  state (`.mb-value` / `.mb-delta`, `MoEBattle.css:147,164`).
- These pastels are close to WG's *vehicle-name* text green/red but washed out — hence the
  "use a different (more native) green" ask.

### B. "From icons" doesn't work — the glyphs are greyscale
- The row icons are `icon_battle_condition_barrel_mark.png` (row 1) and
  `..._improve.png` (row 2), `MoEBattle.js:34-35`, from
  `img://gui/maps/icons/personal_missions_30/quest_type/128x128/`.
- Sampling the actual PNGs (base64-embedded in `TASKS/refs/in-battle-icon-picker.html`) shows
  both are **monochrome line-art ~`#c8c8c8`** with **zero saturated/green pixels** — WG tints
  them at runtime; the art carries no color. So there is nothing to eyedrop from the icons.
  (The mod also renders them white via `filter: drop-shadow(... #fff)`, `MoEBattle.css:134`.)

### C. WoT's real battle palette (extracted from the live client) ✅
Pulled `gui/gui_colors.xml` out of `D:\Games\World_of_Tanks_EU\res\packages\gui-part2.pkg`
(BigWorld packed binary XML, magic `0x62A14E45`; decoded via the PackedSection algorithm — a
throwaway decoder, values verified below). RGBA is `R G B A` 0-255. **These are exact, from
the shipping client** (not community guesses):

| scheme (gui_colors.xml) | RGBA | hex | what WG colors with it |
|---|---|---|---|
| `greenColor` (alias `green`) | 123 236 55 | **`#7BEC37`** | the vivid HUD "green" alias |
| `redColor` (alias `red`) | 245 8 0 | **`#F50800`** | the vivid HUD "red" alias |
| `flag_team_green` (default) | 97 191 34 | **`#61BF22`** | ally 3D flag / team green |
| `flag_team_red` (default) | 200 20 0 | **`#C81400`** | enemy 3D flag / team red |
| `greenTextVehicleNameColor` | 173 208 153 | **`#ADD099`** | ally vehicle-**name** text |
| `greenTextLitVehicleNameColor` | 163 198 143 | **`#A3C68F`** | ally name text (lit/spotted) |
| `redVehicleNameColor` | 211 68 63 | **`#D3443F`** | enemy vehicle-**name** text |
| `redTextLitVehicleNameColor` | 201 58 53 | **`#C93A35`** | enemy name text (lit/spotted) |
| `greenStatusMarkerColor` | 221 255 153 | **`#DDFF99`** | status marker green |
| `textColorError` | 183 0 0 | **`#B70000`** | error text red |

Note: the current widget green `#8fd18f` is essentially a brighter `greenTextVehicleNameColor`
`#ADD099`. So "a different green" means moving *away* from the muted name-text green toward a
more saturated HUD green.

## Suggested approach

Two coherent pairings — pick in the overlay tuner (see Verification), don't hardcode blindly:

1. **Vivid HUD alias pair (recommended if the goal is "pops like the game's green"):**
   green **`#7BEC37`**, red **`#F50800`**. These are WG's literal `green`/`red` aliases — the
   most saturated, unambiguous "good/bad." `#F50800` is near-pure red; if it's too hot next to
   white numerals, step to `flag_team_red` **`#C81400`** or soften toward `#D3443F`.
   - Softer vivid variant: ally/enemy flag pair **`#61BF22`** / **`#C81400`**.
2. **Native battle-text pair (recommended if the goal is "legible, matches over-target text"):**
   green **`#ADD099`**, red **`#D3443F`** (or the lit variants `#A3C68F` / `#C93A35`). This is
   exactly what WG uses for vehicle-name text in the HUD — designed to stay readable over the
   map. Closest in spirit to the current look but properly on-palette.

Implementation is a **pure CSS edit** — swap the two hex values in `MoEBattle.css:176` (green)
and `:180` (red). No JS/Python change: `colourBySign()` already applies `.mb-up` / `.mb-down`.
Keep white for the at-par/zero state. Optionally also tint the row icons to the same green
instead of white (`MoEBattle.css:134` drop-shadow → a green glow, or a CSS filter/mask tint) if
the user wants the icons to carry the color too — but that's a separate visual call.

## Touch points
- `MoEBattle.css:173-181` — the `.mb-up` (green) and `.mb-down` (red) color rules. **Only edit.**
- (optional) `MoEBattle.css:125-136` `.mb-ico` — if tinting the icons to match.
- `MoEBattle.js:64-67` `colourBySign()` — no change; documents where the classes come from.

## Verification
- Reuse the **overlay browser tuner** (`tools/dev/gen_overlay_tuner.ps1` →
  `TASKS/refs/in-battle-overlay-tuner.html`) to preview candidate green/red over the real 4K
  battle backdrop before committing — this window has **no hot-reload** (full client relaunch
  per change; see `in-battle-moe-styling.md`), so previewing in the tuner is the cheap path.
- After choosing: edit the two hex, rebuild + relaunch, eyeball in a battle/replay that the
  above-avg (green) / below-avg (red) states read cleanly over bright and dark map areas.
- No unit tests apply (pure presentation).

## Open questions
- **Which pairing** — vivid alias (`#7BEC37`/`#F50800`) vs native name-text
  (`#ADD099`/`#D3443F`)? User preference; the tuner settles it in seconds.
- Should the **icons** also be tinted to the chosen green, or stay white? (Separate ask.)
- Do we want distinct greens for the two rows (damage-vs-avg vs MoE-delta), or one green for
  both? Current design uses one green + one red for both — keep unless the user wants otherwise.

## Cross-references
- `TASKS/in-battle-moe-styling.md` — the overlay tuner + the no-hot-reload constraint.
- Decoder + extracted `gui_colors.xml` were a throwaway; if the exact hex ever needs
  re-verifying, re-extract `gui/gui_colors.xml` from `res/packages/gui-part2.pkg` and decode
  the PackedSection (magic `0x62A14E45`).
