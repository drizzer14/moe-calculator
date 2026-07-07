# Research: In-battle overlay — checker backdrop renders as large squares (want fine dots)

_Submitted: "Handoff to a clean session where you'll need to fix large squares in a checker." · Status: shipped_

> **Shipped 2026-07-07.** `checker.png` regenerated at **2px cells** (4×4 tile) via new
> `tools/dev/gen_checker.py`; CSS keeps `background-size: auto` → native fine dither. The backdrop
> was then reworked into a fixed two-layer stack (background-gradient underlay + clip, under the
> dots dither), the tuner rebuilt to match (cell-size slider + dither magnifier, mode toggle
> removed), and `-webkit-mask` dropped (WG's Gameface CSS uses unprefixed `mask`). All deployed.

## Summary

The in-battle MoE overlay's backdrop is meant to mimic WG's efficiency-panel **halftone dither**
(a fine ~2px checkerboard that reads as faint dots). It currently renders as **large squares**
(~8px cells) — too coarse. Everything else about the overlay is done and looks right; this is the
last visual nit before commit.

## Context — the overlay is otherwise finished (all UNCOMMITTED)

The in-battle overlay is a res_map-registered Gameface WINDOW over the battle HUD
(`bridge/battle_view.py`, layer=WINDOW=7). Front-end = `MoEBattle.js` + `MoEBattle.css` +
`MoEBattleView.html` under `src/res/gui/gameface/mods/14th_ua/MoECalculator/`. Two rows:
`[dmg icon] CD / AVG` and `[mark icon] % (delta)`, tri-state colours driven by JS.
Resolved earlier this session (see memory `in-battle-moe.md`):
- **Font** = real **MoEBattle** extracted from `gui/flash/fontlib.swf` via
  `tools/dev/swf_font_to_ttf.py`, subset to ~18 glyphs, bundled as **one** bare-sibling cut
  `MoEBattle.ttf`, `@font-face` family `MoEBattle` weight 600. **Confirmed loading in-game.**
- **px/rem ≈ 2.0 @3840** (measured off the real font); the tuner is calibrated to this.
- **Approximation fully stripped** (no `~`, no `approx` field). 42 tests pass, py2.7 compiles.

### Current final CSS (deployed) — `MoEBattle.css`
```
#moe-battle-root { left:13.8vw; top:78.7vh; font-family:"MoEBattle","Arial Narrow",sans-serif; padding:0; }
.mb-row { padding:8rem 32rem; margin-bottom:-13.5rem; }
.mb-row::before {                                   /* THE CHECKER — this is the bug */
  background: url(checker.png) repeat;
  background-size: auto;                            /* <-- native 8px cells = large squares */
  background-position: 0px 0px;
  image-rendering: pixelated;
  opacity: 0.19;
  -webkit-mask/mask: radial-gradient(56% 47% at 66% 48%, #000 0%, transparent 53%);
}
.mb-ico { width:17rem; height:17rem; background-size:260%; margin-right:4rem;
          filter:drop-shadow(0 0 0.5rem #fff); transform:translate(0,1rem); }
.mb-sep,.mb-value.mb-avg,.mb-delta { margin-left:4.5rem; }
.mb-value{ font-size:14rem; font-weight:600; letter-spacing:-0.05em; }
.mb-sep  { font-size:17rem; font-weight:600; }      /* dim via colour rgba(237,230,217,.45) */
.mb-delta{ font-size:14rem; font-weight:600; }
```

## Findings — how the checker is built today

- **`checker.png`** (`.../MoECalculator/checker.png`, 101 bytes) = a **16×16px** tile of **2×2
  cells at 8px each** (black on transparent). Generated ad-hoc this session (no committed generator).
- Loaded as a **bare-sibling raster** `background: url(checker.png) repeat` (the proven mod-asset
  scheme — `img://`/`data:` fail for this; the font + `card_border.png` confirm bare siblings work).
  `MoEBattle.css:90-96`.
- Shaped into a soft blob by the radial **mask** (the mask centre/size is the real "position" knob —
  NOT `background-position`, which only shifts tile phase and wraps every 16px).
- The tuner mirrors this: `tools/dev/gen_overlay_tuner.ps1` inlines the same tile as a base64
  `CHECKER_URI` data-URI and renders `background-size:auto` in "Dots" mode.

## Root cause

`background-size: auto` tiles `checker.png` at its **native pixel size → 8px cells** (the PNG's
cells are 8px). 8px cells on a 3840 HUD read as coarse squares, not WG's ~2px dither.

Why not just shrink with `background-size`? That was tried and is a dead end at both ends:
- **`background-size: 1.6rem`** (~3.2px tile → ~1.6px cells) rendered as the desired **small dots
  IN-GAME** (user liked it) — BUT it is **sub-pixel on the browser tuner's 0.42× stage**, so it's
  invisible there (you can't tune what you can't see). This mismatch caused a long back-and-forth.
- Downscaling an 8px-cell PNG to ~2px via `background-size` also risks aliasing/blur even with
  `image-rendering: pixelated`.

**Key constraint learned:** the browser tuner **cannot faithfully preview a fine ~2-3px dither**
(it's sub-pixel at 0.42× scale). So the checker MUST be verified in-game, not in the tuner.

## Suggested approach

Make the checker **natively fine** so `background-size: auto` yields small cells directly — no
rem/px scaling, crisp, renders in-game, and visible (small) in the tuner:

1. **Regenerate `checker.png` with 2px cells** (a 4×4px tile, 2×2 cells at 2px). Recipe:
   ```python
   from PIL import Image
   t = Image.new('RGBA', (4, 4), (0, 0, 0, 0)); px = t.load()
   for y in range(4):
       for x in range(4):
           if (x // 2 + y // 2) % 2 == 0:
               px[x, y] = (0, 0, 0, 255)     # 2px black cell / 2px transparent, seamless
   t.save('checker.png')
   ```
   Keep `background-size: auto` → **native 2px cells** ≈ WG's dither. Tune `opacity` (start ~0.19)
   and the mask to taste. Consider committing this as `tools/dev/gen_checker.ps1`/`.py` so it's reproducible.
2. **Sync the tuner**: regenerate the `CHECKER_URI` base64 in `gen_overlay_tuner.ps1` from the new
   PNG so the tuner preview matches (it'll show ~2px cells — small but present). Re-publish to the
   SAME artifact URL `https://claude.ai/code/artifact/dd355c07-2811-4dc1-abab-deca6b80bfc4`.
3. If 2px still reads wrong in-game, iterate the PNG cell size (3px?) — change the source PNG, not
   `background-size`. It's the one variable that keeps the pattern crisp.

Fallback if the raster ever stops loading (it currently does load): switch the url to
`img://gui/gameface/mods/14th_ua/MoECalculator/checker.png`.

## Touch points

- `src/res/gui/gameface/mods/14th_ua/MoECalculator/checker.png` — regenerate at 2px cells.
- `src/res/gui/gameface/mods/14th_ua/MoECalculator/MoEBattle.css:90-96` — the `.mb-row::before` checker (keep `auto`).
- `tools/dev/gen_overlay_tuner.ps1` — `CHECKER_URI` const + Dots mode (mirror the new PNG); republish.
- `tools/dev/sync_gameface.py` — already lists `checker.png`; build (`build_wotmod.py`) auto-bundles it.

## Verification

- **No in-session hot-reload for this window** (resources pin at client launch) → every change needs a
  full rebuild + RELAUNCH:
  `C:\Python27\python.exe build/deploy_wotmod.py "D:/Games/World_of_Tanks_EU" 2.3.0.1 --clean-overlay`
  (`--clean-overlay` so no stale res_mods overlay shadows the packaged CSS/PNG).
- **Push mock values** into the live overlay (client running, in a replay/battle):
  `python tools/dev/repl_client.py "execfile(r'<abs>/tools/dev/probe_battle_calib.py')"`
  → pins 3,141 / 2,718 / 84.73% / +1.5%.
- **Screenshot** to inspect: the client → clipboard; save via STA PowerShell
  (`[System.Windows.Forms.Clipboard]::GetImage()`), then crop/zoom the overlay (bottom-left, ~13.8vw/78.7vh
  on a 3840×2160 frame) with PIL to judge the dither. Verify in-game — the tuner can't show a 2px dither.
- Domain tests unaffected: `python -m pytest -q` (Python 3) → 42 pass.

## Open questions

- **Exact cell size** the user wants — WG's is ~2px @3840; confirm 2px reads right or go 3px.
- Whether to keep the checker in the tuner at all (it can only ever show it approximately) or accept
  "verify in-game" as the workflow.
