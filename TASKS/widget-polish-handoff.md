# MoE widget visual polish — handoff (post round 5)

Session handoff for continuing the **visual polish** of the MoE Calculator Gameface
widget. **Refine round 4** (`TASKS/widget-refine-round4.md`) and **round 5**
(`TASKS/widget-refine-round5.md`) plus a run of follow-up alignment tweaks are **applied
and synced** — working tree **UNCOMMITTED**.

> Numbering note: this doc's earlier "rounds 1–7" were a prior polish effort. The user
> tracks the current effort as *refine round 4* → *round 5* → … "Round N" = the refine
> numbering used in chat.

## ⭐⭐ SESSION UPDATE (2026-07-06, clean session) — what changed since round 5
All front-end only, **applied & synced, still UNCOMMITTED**. Read this block first.

1. **Band SIM harness BUILT and STILL ON** — `MoECalculator.js` bottom has a
   `const SIM = true` block (mockModel + BANDS cycle, 2500ms). **MUST set `SIM=false` or
   delete the whole `SIM HARNESS` comment block before committing.** Bands cycle
   white(40)/gold(74)/teal(90)/purple(97).
2. **Zone colours are now ALL authentic WG palette** (user asked to verify every colour
   comes from WoT — done by extracting all 500 client CSS files from `gui-part{1..4}.pkg`):
   - white `#ede6d9`, gold `#edcb9e` — already WG (unchanged; found across hangar/missions/battle_pass).
   - teal `#4fccbb` → **`#00eaff`** (WG's client-wide signature cyan, 300+ uses) — the mod's
     old teal appeared NOWHERE in WG CSS. User picked `#00eaff` from the WG teal family
     (others were `#127177` deep, `#009dcf` mid, `#1ae0b1` mint).
   - purple `#b06ee6` → **`#9160d0`** (WG lootbox-stats accent; the only real WG purple) —
     old purple was also absent from WG CSS.
   - Swapped in three places each: `.moe-zone-*.moe-fill` bg, `.moe-zone-* .moe-cur-pct` colour.
3. **Current percent RELOCATED** — pulled out of the top-left `dmg · pct` readout (removed
   `.moe-cur-sep`; damage now sits alone top-left). Briefly placed bottom-left, then per user
   moved to be the **last tick's top label**: `.moe-cur-pct` now sits in the icon band above
   the bar's **100% goalpost**, right-aligned (`left:100%` + `translateX(-100%)` + `margin-left:2rem`),
   **font 15.5rem**. This REPLACED the old static "100%" caption — `.moe-end-top` (element +
   CSS) was **deleted**. The 100% position is still marked by the `.moe-end` line + `.moe-end-label`
   damage number below.
4. **Glow REMOVED from the current-%** — the per-zone `.moe-cur-pct` rules are now **colour-only**;
   the element keeps just the plain dark legibility shadow (`0 1rem 0 rgba(13,14,16,.4), 0 0 3rem
   rgba(0,0,0,.55)`) from the base rule, same as the mark numbers. (The old per-zone tinted
   blooms — incl. gold's 3-layer WG bloom — are gone.)

**Open to eyeball next session** (SIM still cycling, so easy): does the wider current-%
label (e.g. "97.00%") at the 100% slot **overlap the 95% mark glyph** (at 80% of bar)? and
is `#00eaff` too neon next to the parchment/gold? Then remove SIM + commit.

The WG CSS extraction + palette classifier live in the scratchpad (`wgcss/`, `palette.py`)
if the colour hunt needs redoing.

---

## Band simulation harness (DONE — see SESSION UPDATE above; kept for reference)
The user wanted a **simulation of all four colour bands** to eyeball their colours and the
overall look together (white <65 / gold <85 / teal <95 / purple ≥95). The widget renders
purely from a pushed model, so this is **front-end only** (hot-reloads, no relaunch).

**Fidelity caveat — do it IN-CLIENT, not in a browser.** The bar's dot textures and the
mark glyphs are game art via `img://…`, and the face is `PFDINMax` registered by the
client — none of those resolve in a plain browser, so a browser stub only checks *hex
colours*, not "overall look." For overall look, render in the hangar with the real model
replaced by a mock.

**The mock model shape** (what `render(model)` consumes — `unwrap` is tolerant, a plain
object works; names mirror `bridge/view_models.py`'s `MoEVM`/`MarkTickVM`):
```js
function mockModel(pct, dmg) {
  return { moeData: {
    visible: true, curPercent: pct, curAvgDamage: dmg, fill: pct,
    endDamageRequired: 4200, carouselRows: 1, carouselSmall: false,
    ticks: [
      { percent: 65, markCount: 1, damageRequired: 2100, reached: pct >= 65 },
      { percent: 85, markCount: 2, damageRequired: 3000, reached: pct >= 85 },
      { percent: 95, markCount: 3, damageRequired: 3600, reached: pct >= 95 },
    ],
  }};
}
```
**Recommended harness — cycle the bands** (single `#moe-root`, so cycle rather than stack;
swap the real `engine.whenReady` subscription at the bottom of `MoECalculator.js` for this
behind a `const SIM = true` flag, and delete/flip it off before shipping):
```js
const BANDS = [[40,1500],[74,2400],[90,3200],[97,3900]]; // white / gold / teal / purple
let _bi = 0;
engine.whenReady.then(() => {
  render(mockModel(BANDS[_bi][0], BANDS[_bi][1]));
  setInterval(() => { _bi = (_bi+1)%BANDS.length; render(mockModel(BANDS[_bi][0], BANDS[_bi][1])); }, 2500);
});
```
Each band value pushes a percentile squarely inside that zone (also flips `reached` on the
ticks it passes, so you see reached vs unreached tones too). If a static side-by-side is
wanted instead of a cycle, the alternative is temporarily giving `ensureRoot()` a per-band
id + `position:static` and appending four — heavier; cycle is the cheap faithful option.
The zone colours to verify (CSS `.moe-zone-*`): white `#ede6d9` · gold `#edcb9e` · teal
`#4fccbb` · purple `#b06ee6` (fill bg + current-% readout + its per-zone glow).

## Reviewing live screenshots (the user can't paste images in chat)
The user copies a screenshot to the **clipboard** and says "go"/"look at the screenshot".
Pull it with an **STA runspace** (plain `Clipboard.GetImage()` returns MTA → "no image"):
```powershell
$out = "<scratchpad>\clip.png"
$ps = [PowerShell]::Create(); $ps.Runspace = [RunspaceFactory]::CreateRunspace()
$ps.Runspace.ApartmentState = 'STA'; $ps.Runspace.Open()
[void]$ps.AddScript(@"
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
`$img = [System.Windows.Forms.Clipboard]::GetImage()
if (`$img) { `$img.Save('$out', [System.Drawing.Imaging.ImageFormat]::Png); 'saved' } else { 'no image' }
"@)
$ps.Invoke(); $ps.Dispose()
```
Then `Read` the saved PNG. **Gotcha:** the clipboard often holds a STALE / unrelated image.
If a shot looks wrong or contradicts a just-synced change, ask the user to re-copy.

## Dev loop
**Front-end only (JS/CSS) — no relaunch** (this is all of round 5 + the band sim):
```
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" tools\dev\sync_gameface.py "D:/Games/World_of_Tanks_EU" 2.3.0.1
```
Then in-game switch to Tech Tree and back to the Garage. (WoT = `D:/Games/World_of_Tanks_EU`, EU 2.3.0.1.)

**Python (mount/data) changes — needs build+deploy+relaunch (client CLOSED):**
```
& "C:\Python27\python.exe" build\deploy_wotmod.py "D:/Games/World_of_Tanks_EU" 2.3.0.1
```
Only `wgc` running is fine for deploy; `WorldOfTanks.exe` must be closed. The res_mods
gameface overlay shadows the packaged JS/CSS — keep it for hot-reload; remove
`res_mods\2.3.0.1\gui\gameface\mods\14th_ua\` for a clean ship-verification.

**Unit tests (Python 3):** `& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" -m pytest -q` → **17 passing** (round 5 touched no Python, so unchanged).

## Reading WG's own CSS/textures (how to match the game exactly)
Documented in the **`wotmod-gameface-widget`** harness skill. Client front-end = plain ZIPs
at `<WoT>/res/packages/gui-part{1..4}.pkg`, CSS under `gui/gameface/_dist/production/{mono,lobby}/…`.
Extract by substring with .NET `System.IO.Compression.ZipFile` from PowerShell (`unzip`
wildcards silently match nothing on Git-Bash). Files are minified+hashed; pretty-print,
grep the idiom, port the *values* (never the hashed selector names).

## Round 5 — done (this session), front-end only
From `TASKS/widget-refine-round5.md` (see it for the research + the answered forks):
1. **Number shadows matched to WG's top-right widgets** — WG uses NO text-stroke, only
   layered `text-shadow`. Plain numbers (`.moe-cur` dmg, `.moe-tick-req`, `.moe-split-label`,
   `.moe-end-label`, `.moe-end-top`) → WG's hard dark drop `0 1rem 0 rgba(13,14,16,0.4)` +
   one `0 0 3rem rgba(0,0,0,0.55)` legibility blur (deliberate float deviation; far lighter
   than the old `4rem/0.9` halo). The current-% readout (`.moe-cur-pct`) → a **per-zone
   tinted glow following the band colour** (user's pick): gold = WG's exact 3-layer warm-gold
   `.Timer_label__accent` bloom; white/teal/purple = 2 soft colour blooms in the band hue +
   dark drop + legibility blur.
2. **Full-width bar, 5 EQUAL-WIDTH regions** — retired round-3's 25/75 two-section `barX`.
   New `barX` = piecewise map `PCT_STOPS=[0,50,65,85,95,100]`→`BAR_STOPS=[0,20,40,60,80,100]`
   (even fifths): 50 split→20%, marks 65/85/95→40/60/80%. `.moe-split`/`-label` moved 25→20%.
   Regions = **boundary lines only** (existing split + tick notches), no shaded bands.
3. **Hover brightens background only, not the frame** — already satisfied (`#moe-root::after`
   opacity fade; no `:hover::before`). Locked in; no code change.

## Follow-up alignment tweaks (after round 5, this session)
- **All mark numbers CENTRED on their ticks** — `.moe-tick-req` → `translateX(-50%)`; removed
  the old `.moe-tick-m1` right-align override. The "50%" caption was already centred.
- **100% damage number** — the lone exception: **right-aligned** to the tick
  (`translateX(-100%)`) + **`margin-left: 2rem`** (was tried at 4rem, nudged back to 2).
- **Right padding 42→18rem** (symmetric with left) so the **bar spans full width** — the big
  gutter only existed to hold the old right-extending 100% number.
- **New `.moe-end-top` "100%" label** above the 100% tick, in the icon band (`bottom:6rem`,
  matching `.moe-tick-icon`), **right-aligned like the damage number below** (`translateX(-100%)`,
  `margin-left:2rem`). `font-size: 15rem` (tried 20 = icon height, then /1.5 = 13.33, settled 15).
- **Readout order churn, then reverted:** tried percent-first, then splitting dmg-left /
  pct-right; **reverted to the original** — both together at the left, **damage first**
  (`dmg · pct`), `.moe-cur-sep` "·" restored. Do not re-split unless asked.

## Key learnings / gotchas (verified live)
- **Coherent honours CSS image masks** (`mask-image: url(img://…)`) — used for the tinted
  dotted fill. `img://` works in `background-image`/`mask-image`; **border-image** needs a
  bundled sibling file (`card_border.png`), not `img://`/`data:`.
- **Gradient `background-image` doesn't animate** in Coherent — for a hover fade use an
  `::after` overlay with an `opacity` transition.
- **Hover alpha:** WG's 15% white assumes their opaque dark box; over our semi-transparent
  panel use ~**0.07**.
- **No text-stroke on WG numbers** — every outline/glow there is layered `text-shadow`.
- **Font:** `PFDINMax` (+ `letter-spacing 0.02em`) resolves in the hangar doc.
- **VM property indices are hand-maintained** — `endDamageRequired` is index 10;
  `properties=11`. Adding a prop means bumping the count + numbering the setter.
- **`.moe-tick` / `.moe-end` are 0/1px anchors**; children `left:50%|100%` = the line,
  `translateX(-50%)` centres, `-100%` right-aligns. Icon band = `bottom:6rem` above the track.

## Tunable knobs — current values (MoECalculator.css unless noted)
| What | Selector / prop | Current |
|---|---|---|
| Panel width | `#moe-root width` | `315rem` |
| Panel padding | `#moe-root padding` | `11rem 18rem 9rem 18rem` (symmetric → full-width bar) |
| Panel fill | `#moe-root background` | `rgba(10,10,10,0.28)` |
| Frame | `#moe-root::before` | `card_border.png`, `5rem`, slice `20`, opacity 0.5 |
| Hover overlay | `#moe-root::after` | `rgba(255,255,255,0.07)`, opacity fade `0.18s`; frame untouched |
| Readout (dmg) | `.moe-head` / `.moe-cur` | left `18rem`, above bar; **damage ONLY now** (pct moved out; `.moe-cur-sep` removed) |
| Readout weight | `.moe-cur font-weight` | `400` |
| Readout shadow | `.moe-cur` | `0 1rem 0 rgba(13,14,16,.4), 0 0 3rem rgba(0,0,0,.55)` |
| Current-% label | `.moe-cur-pct` | **last tick's top label** (icon band, `bottom 6rem`, `left 100%`, `translateX(-100%)` `margin-left 2rem`), `15.5rem`; **NO glow** — colour-only per zone + plain dark shadow |
| % format | JS `pctText()` | `floor` to 2 decimals |
| Bar axis | JS `barX()` | 5 equal fifths; `PCT_STOPS/BAR_STOPS` |
| Zone colours | `.moe-zone-*` | white `#ede6d9` / gold `#edcb9e` / teal `#00eaff` / purple `#9160d0` (**all authentic WG**) |
| Zone thresholds | JS `zoneOf()` | <65 / <85 / <95 / ≥95 |
| Split (50%) | `.moe-split` + `-passed` | line at `left 20%` (barX(50)); brightens when `fill>=50` |
| Marks 65/85/95 | ticks via `barX` | at `40/60/80%`; numbers CENTRED on tick |
| 100% end line | `.moe-end` | `left 100%` |
| 100% top label | *(removed)* | old static "100%" `.moe-end-top` deleted — the slot now holds the current-% label above |
| 100% dmg number | `.moe-end-label` | right-aligned `translateX(-100%)` `margin-left 2rem` |
| SIM harness | JS bottom `const SIM` | **`true` — REMOVE before commit** |
| Plain-number shadow | `.moe-tick-req` etc. | `0 1rem 0 rgba(13,14,16,.4), 0 0 3rem rgba(0,0,0,.55)` |

## State / next steps
**Working tree UNCOMMITTED** (11 tracked files + untracked `card_border.png`, `TASKS/`).
See the ⭐⭐ SESSION UPDATE at the top for exactly what this session changed.
- **Eyeball the SIM** (still cycling, `SIM=true`): current-% label vs 95% mark overlap; `#00eaff`
  neon check. Adjust label size/nudge or the cyan if the user wants.
- **Still open from round 4 item 2:** verify the whole-box hover (`#moe-root` is
  `pointer-events:auto`) doesn't steal drag-to-rotate / clicks near the box.
- **Before commit: set `SIM=false` (or delete the SIM HARNESS block) in `MoECalculator.js`.**
- **Commit** when the user asks — suggested scope: the whole widget-polish + refine-round-4 +
  round-5 + this session (JS/CSS/`card_border.png`/`sync_gameface.py` + the Python 100%-goalpost
  plumbing from r4 + the two updated tests). Tests: **17 passing** (no Python touched this session).
</content>
</invoke>
