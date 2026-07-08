# Research: Garage widget frame must match the ammo-container border exactly

_Submitted: "In-garage widget must match ammo container border exactly. Currently, ammo container's border looks 2x thicker and has no outer black 1rem border." · Status: open_

## Summary

The garage widget's card frame doesn't match WG's ammunition-panel slot boxes (the shell /
consumable / equipment slots at the bottom of the garage). Compared to those slot boxes, the
widget's border reads too thin/faint and is missing the **thin black outer rim** the slot
frame has. Goal: reskin the widget frame to WG's own ammo-slot texture so it reads as native
chrome — same heft, same baked-in black outer edge.

Interpretation of the report: the ammo slot border is ~2× the visual weight of the widget's
current frame and carries an outer black ~1rem rim that the widget lacks. Both come from the
same root cause: the widget uses a *different, fainter* texture (`card_border.png` at
`opacity: 0.5`), not WG's slot texture.

## Findings — what the widget does today

`MoECalculator.css` → `#moe-root::before` (the frame layer, ~lines 72–85):

```css
#moe-root::before {
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    border: 5rem solid transparent;
    border-image: url(card_border.png) 20 / 5rem repeat;   /* ui_kit card_border, 64x64 */
    opacity: 0.5;                                           /* <- faint; halves the weight */
    pointer-events: none;
    z-index: 5;
}
```
The fill sits on `#moe-root` itself (~line 59): `background: rgba(10, 10, 10, 0.28);`
`border-radius: 2rem;` no drop shadow (comment: "the card_border frame carries the edge").

So the frame is (a) a *different* texture from the ammo slots, (b) drawn at half opacity, and
(c) `repeat`-tiled — all three make it lighter and rim-less versus the slot boxes.

## Findings — what WG's ammo slot boxes actually use

Ported by VALUE from the client's own Gameface CSS
(`lobby/tanksetup/AmmunitionPanel/AmmunitionPanel.css`, also identical in
`HangarAmmunitionSetup.css`). The slot box is a `*_base_*` element (54rem square) with a dark
fill, and an inner `*_base__toggle_*` element that draws the frame:

```css
/* the slot box fill (e.g. .ShellsSection_base_) */
background-image: linear-gradient(rgba(0,0,0, .45), rgba(0,0,0, .45));

/* the frame (e.g. .ShellsSection_base__toggle_, .Container_base__toggle_,
   .ToggleCamouflageSlot_base__toggle_ — all identical) */
border-image-source: url('R.images.gui.maps.icons.tanksetup.panel.toggle');
border-image-slice: 4 fill;
border-image-width: 4rem;
/* NB: border-image-repeat is NOT set -> defaults to `stretch` (WG does NOT tile it) */
```

- **Texture** `R.images.gui.maps.icons.tanksetup.panel.toggle` resolves to a standalone PNG:
  `gui/maps/icons/tanksetup/panel/toggle.png` — **30×20 px, 561 bytes**, present in
  `res/packages/gui-part1.pkg`. It is a light/cream 9-slice bevel frame with a **thin black
  outer rim** baked into the outermost pixel. That black rim IS the "outer black 1rem border"
  the report is asking for — you get it for free by using this texture; no separate CSS border
  needed. A copy is saved at **`TASKS/refs/panel_toggle.png`** for reference.
- WG draws it at slice `4 fill` / width `4rem`, **stretched** (not repeated). At 4rem width the
  outermost ~1px of the 4px corner scales to ~1rem of black rim — matching the report.
- `border.png` (56×56, orange) in the same folder is the *selected/hover* frame, NOT this. Don't
  use it.

## Root cause

The widget frame was styled to WG's generic **ui_kit `card_border`** texture (a faint thin
line, drawn at `opacity: 0.5`, `repeat`-tiled), whereas the ammunition slots use the
**`tanksetup/panel/toggle`** texture (a heavier cream bevel with a black outer rim, full
opacity, stretched). Different texture + half opacity = thinner, rim-less frame.

## Suggested approach

Swap the widget's frame texture to WG's slot texture and match its draw params. Starting point:

1. **Extract the texture** and bundle it as a bare sibling of the CSS (border-image ONLY paints
   a relatively-loaded sibling file — `img://` and `data:` URIs silently drop; same trick as
   `card_border.png`/`tooltip_bg.png`). Target path:
   `src/res/gui/gameface/mods/14th_ua/MoECalculator/panel_toggle.png`.
   ```powershell
   Add-Type -AssemblyName System.IO.Compression.FileSystem
   $zip=[IO.Compression.ZipFile]::OpenRead('D:\Games\World_of_Tanks_EU\res\packages\gui-part1.pkg')
   $e=$zip.Entries | ? { $_.FullName -eq 'gui/maps/icons/tanksetup/panel/toggle.png' }
   [IO.Compression.ZipFileExtensions]::ExtractToFile($e,'<...>\MoECalculator\panel_toggle.png',$true)
   $zip.Dispose()
   ```
   (Or just copy `TASKS/refs/panel_toggle.png` in — it's the same file.)

2. **Rewrite `#moe-root::before`** to match WG's params (drop `opacity`, drop `repeat` → stretch,
   `4 fill / 4rem`):
   ```css
   border: 4rem solid transparent;
   border-image: url(panel_toggle.png) 4 fill / 4rem;   /* stretch (default), full opacity */
   /* remove: opacity: 0.5;  and the `20 / 5rem repeat` card_border line */
   ```
   Because `toggle.png` has `fill`, its center fills the box — decide whether to keep
   `#moe-root`'s own `background: rgba(10,10,10,0.28)` or match WG's slot fill
   `linear-gradient(rgba(0,0,0,.45), rgba(0,0,0,.45))` for an exact tone match. WG's fill is
   darker; try WG's value if the report wants a pixel-exact match, else keep the current tone.
   Note the `::before` fill sits UNDER content — confirm text/bars stay legible.

3. Keep the frame on the `::before` pseudo (don't put `border-image` on `#moe-root` directly, or
   it'll clip the content box / fight `border-radius`). WG's slots have no `border-radius`; the
   widget's `2rem` radius on `#moe-root` may need dropping to read as a native square-cornered
   slot — eyeball it.

**Uncertainty:** "2× thicker" is a visual read, not a measured 2×. The dominant fix is the
texture swap + removing `opacity: 0.5` (that alone roughly doubles the apparent weight). Whether
4rem vs the old 5rem border-width needs further nudging is a live-eyeball call — start at WG's
`4rem` and compare side-by-side against a real slot box.

## Touch points

- `src/res/gui/gameface/mods/14th_ua/MoECalculator/MoECalculator.css` — `#moe-root::before`
  (frame) and possibly `#moe-root` (fill tone / border-radius).
- `src/res/gui/gameface/mods/14th_ua/MoECalculator/panel_toggle.png` — NEW bundled sibling
  texture (extract per above).
- `tools/dev/sync_gameface.py` — add `"panel_toggle.png"` to the `ASSETS` tuple (~line 27) or
  the hot-reload won't push it. (Optionally retire `"card_border.png"` if nothing else uses it —
  grep first; it may still be referenced.)
- `build/build_wotmod.py` — no change needed; it `os.walk`s `src/` so the new PNG is packaged
  automatically.

## Verification

- Hot-reload the garage widget (no relaunch needed for the garage surface):
  `& "<py3>" tools\dev\sync_gameface.py "D:/Games/World_of_Tanks_EU" 2.3.0.1` → in-game switch
  to Tech Tree and back to Garage.
- Put the widget directly beside a real ammo slot box (shell/consumable slots, bottom of
  garage) and confirm: same frame weight, same cream bevel, same thin black outer rim, corners
  match. Re-shoot `TASKS/refs/comparison_boxes_vs_mod.png`-style side-by-side.
- Confirm `border-image` actually paints (sibling-PNG trick): if the frame vanishes, the PNG
  isn't loading as a sibling — check the filename/case and that it deployed.
- Run `pytest` (no Python touched, should stay green) as a sanity check that nothing else moved.

## Open questions

- Match WG's slot **fill** tone exactly (`rgba(0,0,0,.45)`) or keep the current
  `rgba(10,10,10,.28)`? The report is about the *border*; confirm with the user whether the fill
  should change too.
- Drop `#moe-root`'s `2rem border-radius` to match WG's square slot corners, or keep it?
- Is `card_border.png` still used elsewhere after this swap? If not, remove it from the repo and
  from `sync_gameface.py` `ASSETS` in the same change.
