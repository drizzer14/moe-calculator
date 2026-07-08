_Status: shipped_

> **STATUS 2026-07-07 (late): mostly SUPERSEDED.** The styling below is largely DONE and applied.
> Since this was written: font is the REAL MoEBattle extracted from `fontlib.swf` (bundled as one
> `MoEBattle.ttf` @font-face `MoEBattle` 600, **confirmed loading**); px/rem recalibrated to
> **2.0** (not 1.95/2.27); approximation fully stripped; checker backdrop is a raster `checker.png`.
> **The only open visual nit = the checker renders as large squares (want a fine dither).**
> → START at **TASKS/in-battle-checker-squares.md**; full state in memory `in-battle-moe.md`.
> The tuner artifact (recalibrated, opens at the current baseline) is the same URL below.

# In-battle MoE — styling (clean-session handoff, updated 2026-07-07)

_Supersedes the earlier version of this file. The overlay is functionally live and the
input-steal bug is FIXED. Remaining: finish the visual tune (in a **browser tuner**, because
this window has NO in-session hot-reload), then apply + bundle the font + relaunch-verify +
commit. Everything is still UNCOMMITTED._

## What's DONE + live-verified this session

- **Input-steal FIXED (user-confirmed live).** The overlay window was at `WindowLayer.OVERLAY`
  (11) — above the modal in-battle menu (`INGAME_MENU` = `TOP_WINDOW` 10, `isModal=True`), so a
  full-screen window above it ate the keyboard. Moved to `WindowLayer.WINDOW` (7), below the menu.
  `bridge/battle_view.py::MoEBattleWindow`. Deployed; user confirmed "input is not stolen anymore."
- **Layout reworked** to mimic WG's personal-efficiency panel (`MoEBattle.js`): two rows, icon +
  value, NO text labels.
  - Row 1: `[barrel_mark icon]  DMG / AVG` — DMG **red** if < AVG, **white** if ==, **green** if > AVG.
  - Row 2: `[improve icon]  %  (delta)` — delta **red** if −, **white** if 0, **green** if +.
  - Icons: `img://.../personal_missions_30/quest_type/128x128/icon_battle_condition_barrel_mark.png`
    (row1) + `..._improve.png` (row2). These fill only ~23% of the PNG → need `background-size: 260%`.

## THE EXACT FONT (identified)

The battle logs + efficiency panel are **Flash (Scaleform)**, font alias `$FieldFont` →
**`MoEBattle`** (titles `MoEBattle`) per `res/gui/flash/fontconfig.xml`. "MoEBattle
BT" = a clone of **Univers Condensed**. It's embedded in the Flash `fontlib.swf`, NOT a Gameface
ttf, so Gameface can't use it directly — we must **bundle a ttf**. Gameface supports mod `@font-face`
(that's how PFDINMax loads). User picked "free Univers lookalike", then supplied the real thing:
**`D:\Downloads\univers\UniversCnRg.ttf` + `UniversCnBold.ttf`** (staged in `TASKS/refs/fonts/`).
Plan: bundle these two as one `@font-face` family (weight ≤500 → Rg, ≥600 → Bold).

## CRITICAL: no in-session hot-reload for this window

Reopen AND `Window.reload()` both serve the **launch-time cached document** — resources are pinned
at client launch. So every CSS/JS tweak needs a FULL RELAUNCH. (The garage widget hot-reloads only
because OpenWG *re-injects* its assets; our standalone registered window has no such path.) => we
tune in a **browser** instead and apply once.

## The browser tuner (how we're iterating now)

Artifact: **https://claude.ai/code/artifact/dd355c07-2811-4dc1-abab-deca6b80bfc4**
(saved offline: `TASKS/refs/in-battle-overlay-tuner.html`; generator: `tools/dev/gen_overlay_tuner.ps1`).
Real 4K battle backdrop @0.42× + real overlay markup + **real Univers Condensed inlined**, calibrated
**1 rem ≈ 1.95 px @3840** (measured off the green "415" in-game). Controls (slider + number box each):
position, per-element type size/weight/letter-spacing, margins (negative allowed), icon size/zoom/glow,
row gradient (linear/radial + angle/size/centre + 3 stops), **left-clip mask**, number shadow. Font is
Univers Condensed only (weight ≤500=Rg, ≥600=Bold). "Copy CSS values" emits margin-based CSS with the
gradient on a masked `.mb-row::before`. To regen after edits: run the generator, re-publish to the SAME
artifact URL. Backdrop is `TASKS/refs/tuner-backdrop.jpg` (has our overlay baked in → faint ghost).

## CSS applicability — VERIFIED against WG production CSS + sibling mods

| feature | verdict | evidence |
|---|---|---|
| flex `gap`/row-gap/column-gap | ❌ NOT supported | WG 1 use in 6597 flex; use **margins** |
| margins incl. NEGATIVE | ✅ | garage uses `-0.5rem` |
| `linear-gradient(deg,…,alpha)` | ✅ | sibling `WGModResearch.css:243` |
| `radial-gradient(rx% ry% at cx% cy%,…)` | ✅ | WG 169× |
| `filter: drop-shadow` (stacked) | ✅ | garage + sibling |
| `text-shadow` (layered) | ✅ | garage |
| `mask-image: linear-gradient` | ✅ | WG 159× (used for the left-clip) |
| `::before/::after` + `position:absolute` | ✅ | sibling `wg-track::after` |
| `font-weight`, `letter-spacing`, `background-size %` | ✅ | garage/sibling |

**`MoEBattle.css` currently still uses flex `gap` + a root gradient — it MUST be rewritten to
margins + per-row `::before` gradient when applying the final values.**

## Latest tuned values (user, pre-font-finalize) — NOT yet in MoEBattle.css

```
#moe-battle-root { left: 14vw; top: 78.8vh; font-family: "Univers Condensed", sans-serif; padding: 0; }
.mb-row  { position: relative; padding: 8rem 32rem; margin-bottom: -12.5rem; }
.mb-row::before { content:""; position:absolute; inset:0;
  background: radial-gradient(80% 47% at 26% 48%, rgba(0,0,0,0.28) 32%, rgba(0,0,0,0) 87%, rgba(0,0,0,0) 0%);
  -webkit-mask/mask: linear-gradient(90deg, transparent <clipStart>%, #000 <clipEnd>%);  /* soft left-clip */ }
.mb-row > span { position: relative; }
.mb-ico  { width:16rem; height:16rem; background-size:260%; margin-right:4.5rem; filter: drop-shadow(0 0 0.5rem #fff); }
.mb-sep, .mb-value.mb-avg, .mb-delta { margin-left: 4.5rem; }
.mb-value{ font-size:16.5rem; font-weight:500; letter-spacing:-0.05em; text-shadow:0 0 1rem rgba(0,0,0,0.5); }
.mb-sep  { font-size:17rem; font-weight:400; }
.mb-delta{ font-size:14rem; font-weight:700; text-shadow:0 0 1rem rgba(0,0,0,0.5); }
```
(Still finalizing font weight + left-clip in the tuner.)

## Remaining steps
1. Finish tuning in the browser → grab final "Copy CSS values".
2. Rewrite `MoEBattle.css`: margins (no flex gap), per-row `::before` gradient + left-clip mask,
   `@font-face "Univers Condensed"` (bundled ttfs, 400/500→Rg 600/700→Bold) at the top.
3. Bundle the fonts: put `UniversCnRg.ttf` + `UniversCnBold.ttf` under the mod's gameface dir
   (e.g. `.../MoECalculator/fonts/`); make `sync_gameface.py` + the build include `.ttf`. (Licensing:
   user-supplied Univers — their call for release.)
4. Rebuild (`C:\Python27\python.exe build/deploy_wotmod.py "D:/Games/World_of_Tanks_EU" 2.3.0.1`) +
   RELAUNCH (Python + fonts + CSS all need it) → verify: renders over HUD, font correct, colours,
   position vs panel, **menu input still fine**.
5. Metric sanity-check in a LIVE battle (replay baseline is empty = BUG B; only combined dmg is real there).
6. Commit (whole in-battle feature + prior garage/tooltip/widget-polish are all still uncommitted).

## Key files
- `bridge/battle_view.py` — window layer fix (WINDOW).
- `MoEBattle.js` — 2-row DMG/AVG + %(delta), barrel_mark/improve icons, `colourBySign`.
- `MoEBattle.css` — **needs the margin + ::before + mask + @font-face rewrite** with final values.
- `tools/dev/gen_overlay_tuner.ps1` + `TASKS/refs/in-battle-overlay-tuner.html` — the tuner.
- `TASKS/refs/fonts/UniversCn{Rg,Bold}.ttf` — the fonts to bundle.
- `tools/dev/probe_battle_calib.py` — reload+pin synthetic (note: reload doesn't hot-reload; needs relaunch).
