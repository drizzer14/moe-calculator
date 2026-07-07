# Research: Widget visual refinement — round 4

_Submitted: "make current damage and % numbers thinner; copy hover effect for the whole
widget from crew/equipment/ammo/consumables; add final tick with 100% moe; mark 50% tick
line as passed when it's passed; don't round the % — it must be precise." · Status: shipped_

Fifth batch of visual polish on the MoE Calculator Gameface widget. Continues the effort
tracked in `TASKS/widget-polish-handoff.md` (rounds 1–3, uncommitted working tree) — read
that first for the dev loop (`tools/dev/sync_gameface.py`), the tunable-knobs table, the
reference screenshots in `TASKS/refs/`, and the Gameface/Coherent CSS gotchas. All five
items below are front-end only **except** item 5, which also has a Python-side thread.

---

## 1. Current damage & % numbers — thinner

### Summary
The top-left readout (current avg combined damage · current mark %) renders bold; the user
wants a lighter weight.

### Findings
- The readout markup is built in `ensureRoot()` — `.moe-cur` wrapping `.moe-cur-dmg`,
  `.moe-cur-sep`, `.moe-cur-pct` (`MoECalculator.js:68-74`).
- Styling: `#moe-root .moe-cur { font-size: 16rem; font-weight: 700; ... }`
  (`MoECalculator.css:87-91`). This 700 is the only thing making it heavy — the per-mark
  requirement labels below the bar already use `font-weight: 400` (`MoECalculator.css:270`)
  and read noticeably thinner, so 400 is the proven "thin" weight for this face.
- Font family is `PFDINMax, "PF DIN Max Compressed", "Warhelios", sans-serif`
  (`MoECalculator.css:28`). `Warhelios` only ships Regular/Bold; PF DIN Max Compressed is
  the condensed numeric face. Whether a weight *below* 400 (e.g. 300) actually renders
  depends on the registered font faces — 300 may silently fall back to 400.

### Suggested approach
Change `.moe-cur` `font-weight: 700` → `400` (matches the requirement labels; safe). If the
user wants it thinner still, try `300`, but verify in-game that it doesn't fall back to 400
(Gameface renders whatever face is registered; there may be no Light weight). The damage,
separator, and % children inherit weight from `.moe-cur`, so one change covers all three.

### Touch points
- `MoECalculator.css` — `.moe-cur` (`:89`).

### Open questions
- Target weight: 400 (safe, matches labels) or lighter 300 (may not have a face)? Recommend
  starting at 400 and letting the user eyeball it.

---

## 2. Whole-widget hover effect (copy crew/equipment/ammo/consumables)

### Summary
The garage's bottom-bar setup boxes (crew / equipment / ammunition / consumables) brighten /
gain a frame glow on mouse-over. The user wants the whole MoE box to react the same way when
hovered.

### The blocker to solve first — `pointer-events`
`#moe-root` is deliberately `pointer-events: none` (`MoECalculator.css:31`) so the widget
**never steals the hangar's drag-to-rotate**. A CSS `:hover` cannot fire on an element that
ignores the pointer. So this feature *requires* re-enabling pointer capture on the box —
which reintroduces exactly the input-stealing risk that line was added to avoid.

Mitigation: enable pointer events on the **root box only** (it's a small panel floating over
empty hangar space above the carousel), while keeping the child overlays that extend beyond
the visible box (`.moe-ticks`, `.moe-cur-marker`, `.moe-split*`) at `pointer-events: none`.
The box sits over dead space, so capturing hover there shouldn't block rotate/click — but
this **must be verified live** (drag-to-rotate starting on the box; clicks near it). If it
does interfere, an alternative is a transparent hover-catcher sized exactly to the box, or
accept that only the box footprint is interactive.

### Findings (WG's own hover styling — extracted from the client)
The garage bottom-bar boxes (crew / equipment / ammunition / consumables) are the
`__hangar` variants of `Container` / `ShellsSection` (bundled in the client's
`AmmunitionPanel.css`, mirrored in `HangarAmmunitionSetup.css`). All of them share **one
identical, minimal hover idiom** — verified against `gui-part{1..4}.pkg`:

```css
/* default: dark-tinted box */
background-image: linear-gradient(rgba(0,0,0,.45), rgba(0,0,0,.45));
cursor: pointer;

/* hover: keep the dark layer, STACK a 15% white overlay on top */
background-image:
  linear-gradient(rgba(0,0,0,.45), rgba(0,0,0,.45)),
  linear-gradient(rgba(255,255,255,.15), rgba(255,255,255,.15));
```

That white-15% overlay is the **entire** hover treatment. Notably WG does **NOT** on hover:
change the border / border-image, add any box-shadow/glow, apply `filter`/`opacity`, or use a
CSS `transition` — the highlight is **instantaneous**. (The `box-shadow` glow lives only on
the *selected/active* box, not on hover; a soft `inset` white shadow is the *full tank-setup
screen* `__setup` variant, not the bottom bar.) So a faithful copy is a subtle uniform
brightening of the whole panel, nothing more.

Our widget already has a panel fill `background: rgba(10,10,10,0.28)`
(`MoECalculator.css:36`) and a frame `#moe-root::before` (`:47-61`). Since our `background`
is a solid colour (not a gradient), the cleanest port is to add a white-overlay
`background-image` on hover while leaving `background-color` and the frame untouched — exactly
mirroring WG (frame unchanged on hover).

### Suggested approach
1. On `#moe-root`: `pointer-events: auto` (box footprint only); keep the overlay children
   that extend past the box (`.moe-ticks`, `.moe-cur-marker`, `.moe-split*`, `.moe-tick*`) at
   `pointer-events: none` so only the panel captures hover.
2. Add the hover rule, values straight from WG (instant — **no** transition, to match):
   ```css
   #moe-root:hover {
       background-image: linear-gradient(rgba(255,255,255,.15), rgba(255,255,255,.15));
   }
   ```
   (Our `background-color: rgba(10,10,10,0.28)` stays; the overlay rides on top. Leave
   `#moe-root::before` alone — WG doesn't touch the frame on hover.)
   - **Explicit user constraint (round 5): hover brightens the BACKGROUND only, NOT the
     border** — add no `#moe-root:hover::before` rule and don't animate the frame. This
     matches WG exactly. See `TASKS/widget-refine-round5.md §3`.
   - If a subtle animated fade reads better than WG's instant snap, a short
     `transition: background-image` is a deviation-from-WG the user can opt into.
   - The extracted/pretty-printed WG sources are in the scratchpad `wgcss/` dir
     (`Container__Container.pretty.css`, `AmmunitionPanel__AmmunitionPanel.pretty.css`) —
     session-scoped, re-extract via the handoff's pkg technique if gone.

### Touch points
- `MoECalculator.css` — `#moe-root` (`:13`, flip `pointer-events`), the overlay children
  (add explicit `pointer-events: none`), new `#moe-root:hover` rule.
- Possibly `MoECalculator.js` only if a dedicated hover-catcher node is chosen over
  box-level pointer capture (see the blocker above).

### Verification
- Live in-client: hover the box → effect matches the bottom-bar boxes; **drag-to-rotate and
  clicks are unaffected** whether the cursor starts on/near the box. This is the whole risk.

### Open questions
- Is capturing hover on the box footprint acceptable, or must rotate/click be provably
  untouched (→ needs the catcher-node approach / live test)?
- Copy WG's hover *exactly* (its frame+fill+glow), or just brighten our existing frame?

---

## 3. Final tick at 100% MoE

### Summary
Add a tick / end-cap at the far right of the bar representing 100% (the top of the percentile
axis), beyond the existing 65/85/95 milestone marks.

### Findings
- Milestone ticks come from the data model: exactly three, at `MARK_PERCENTS = (65, 85, 95)`
  (`domain/constants.py:14`), built in `builder.py:27-36`, marshalled in
  `gameface_bridge.py:317-328`, rendered by `renderTicks()` (`MoECalculator.js:94-122`).
  There is **no** 100% entry anywhere — and there is no "4 marks", so a 100% tick carries no
  mark art and no threshold from the external table (`thresholds` is keyed `{1,2,3}`).
- The axis already runs to 100: `barX(100)` returns `100` (`MoECalculator.js:44-48`), i.e.
  the bar's right edge. `AXIS_MAX = 100` (`domain/constants.py:21`).
- The closest existing pattern is the `.moe-split` divider + `.moe-split-label` "50%"
  (`MoECalculator.js:78-79` markup; `MoECalculator.css:159-184` style) — a fixed DOM node
  positioned by `left` %, not a data-driven tick.

### Suggested approach
Treat it as an **axis end-cap**, mirroring the split, not as a 4th mark:
- Add fixed `.moe-end` (divider) + `.moe-end-label` ("100%") nodes in `ensureRoot()`
  alongside the split nodes; position at `left: 100%` (the bar's right edge) with a
  `translateX` pull-back so the label doesn't overflow the panel.
- Style them like `.moe-split*` for family consistency (faint upright line + small caption).
- No Python / model change needed — it's a static axis label. (Only touch the model if the
  user wants a real *data* tick, e.g. showing the 3-mark art again or a 100%-damage figure.)

### Touch points
- `MoECalculator.js` — `ensureRoot()` markup (`:67-83`).
- `MoECalculator.css` — new `.moe-end` / `.moe-end-label` rules (clone of `:159-184`).

### Open questions
- Is the 100% tick just an **end label/line** (recommended — matches the "50%" caption), or
  should it show something else (mark art, a damage number)? The bar's right edge is already
  the visual "100%", so the value-add is the label.
- Does the fill ever reach it? `fill = cur_percentile` clamped 0..100 (`builder.py:44`);
  100% only at a perfect damage rating, so in practice the end-cap reads as an unreached
  goalpost — confirm that's the intent.

---

## 4. Mark the 50% line as "passed" once passed

### Summary
The "50%" split divider is drawn static/faint. When the current percentile is past 50, it
should read as passed (brighter), the way reached milestone ticks do.

### Findings
- Split divider `.moe-split` (`MoECalculator.css:159-169`) and caption `.moe-split-label`
  (`:173-184`) are painted at a fixed faint tone (`rgba(236,230,218,0.45)` /
  `rgba(216,207,191,0.45)`) regardless of progress — there is no "passed" state.
- The precedent exists for ticks: `renderTicks()` adds `moe-tick-reached` per tick
  (`MoECalculator.js:99`), and CSS brightens the reached notch/label
  (`.moe-tick-reached .moe-tick-notch → 0.8`, `.moe-tick-reached .moe-tick-req → #ede6d9`;
  `MoECalculator.css:259-277`). Mirror that for the split.
- The split sits at `SPLIT_PCT = 50` (`MoECalculator.js:42`). "Passed" ⇔ `fill >= 50`
  (fill is the clamped current percentile — `data.fill`, set at `MoECalculator.js:162`).
  Note: when `fill >= 50` the bright fill already visually covers the divider (fill width =
  `barX(fill)`, split at `barX(50) = 25%`), so brightening the divider/label reinforces what
  the fill already shows.

### Suggested approach
- In `render()`, toggle a root class when past the split, next to the existing `moe-zone-*`
  toggles (`MoECalculator.js:154-157`): `root.classList.toggle("moe-split-passed", fill >= SPLIT_PCT)`.
- In CSS, add `#moe-root.moe-split-passed .moe-split { background: rgba(236,230,218,0.8); }`
  and `#moe-root.moe-split-passed .moe-split-label { color: #ede6d9; }` — same brightened
  tones the reached ticks use, for a consistent "passed" language.

### Touch points
- `MoECalculator.js` — `render()` class toggle (`~:154`).
- `MoECalculator.css` — new `.moe-split-passed` rules (near `:159-184`).

### Open questions
- Threshold is `>= 50` on the current percentile — confirm (vs. strictly `> 50`). Recommend
  `>= 50`.

---

## 5. Don't round the % — show it precisely

### Summary
The current-mark percentage is displayed rounded to one decimal, which also rounds **up**
(84.96 → "85.0"). The user wants it precise.

### Findings — where the rounding is (and isn't)
The percentile flows through the pipeline **unrounded** until the very last step:
1. `engine_adapter._read_moe()` reads `mog.getDamageRating()` — the dossier method that
   already divides the stored `damageRating` by 100, giving e.g. `84.73`
   (`engine_adapter.py:62`). So **hundredths (0.01) precision is available** from the game.
2. `build_model()` only clamps it to a float, no rounding (`builder.py:22`).
3. `push()` writes the raw float via `setCurPercent(model.cur_percentile)`
   (`gameface_bridge.py:311`); the VM stores it as a number (`view_models.py:71`).
   (The `LOG_NOTE` `%.1f` at `gameface_bridge.py:305` is log-only — not the displayed value.)
4. **The only rounding is in the widget JS:** `pctText(p)` → `p.toFixed(1) + "%"`
   (`MoECalculator.js:31-35`). `toFixed` rounds half-up, so 84.96 shows as "85.0" —
   misleading for a MoE tool where 85 is the 2-mark threshold.

Note: `adapter/format.py:percent()` supports a `decimals` arg but is **not** on this display
path (the JS formats the %). Leave it or align it, but it isn't the fix.

Reassurance: this is display-only. Whether a milestone tick lights (`reached`) comes from
`marks >= count` in Python (`builder.py:35`), i.e. actual marks held — **not** from the
displayed %, so a rounded "85.0%" never falsely lights the 2-mark tick. The issue is purely
that the shown number is imprecise/inflated.

### Suggested approach
Edit `pctText()` (`MoECalculator.js:31-35`) to show more precision. Two decisions for the user:
- **How many decimals** — the game's granularity is 0.01, so **2 decimals** (e.g. "84.73%")
  is the natural, non-spurious maximum. More than 2 is fake precision.
- **Round vs. truncate** — `toFixed(2)` still rounds up (84.999 → 85.00). To *never* show a
  threshold as reached before it is, truncate instead:
  `(Math.floor(p * 100) / 100).toFixed(2) + "%"`. Recommended for a MoE calculator.

Keep the `p <= 0 → "0%"` special case.

### Touch points
- `MoECalculator.js` — `pctText()` (`:31`).
- (Optional) `adapter/format.py:percent()` if any other surface should match; not required.

### Verification
- Unit: `format.py:percent` has coverage in `tests/` — if the JS logic is mirrored anywhere,
  keep them consistent (JS has no test harness).
- Live: pick a vehicle whose rating is e.g. `xx.9x`; confirm the readout shows 2 decimals and
  does not round up to the next whole/threshold value.

### Open questions
- Decimals: 2 (recommended) or something else?
- Round or **truncate** (recommended: truncate, so it never overstates progress toward a mark)?

---

## 6. Border 1rem thicker (to match the bottom-bar boxes)

### Summary
The widget's frame reads thinner than the garage's crew / equipment / ammo / consumables
boxes. Make our frame **1rem thicker** (4rem → 5rem) to match their heavier edge.

### The change
- Current frame: `#moe-root::before { border: 4rem solid transparent;
  border-image: url(card_border.png) 16 / 4rem repeat; opacity: 0.5; }`
  (`MoECalculator.css:56-57`). Logged as "Frame thickness = 4rem" in the handoff knobs table.
- +1rem → `border: 5rem solid transparent; border-image: url(card_border.png) 16 / 5rem repeat;`
- **Gotcha (from the handoff / memory):** widening the `border-image` *width* stretches the
  fixed 64px texture's 16px slice, which **washes out the edge line**. If the thicker frame
  looks blurry/faded, raise the slice number (`16 → ~20`) rather than only the width, so the
  crisp corner/edge is preserved.

### Note on what those boxes' frame actually is (reference, not required)
Confirmed from a live screenshot: those boxes **do** carry a visible frame — a dark outer
edge with a light inner bevel — so a heavier frame on our widget is the right direction. (An
earlier read of `Container_base` alone was misleading: that inner slot is frameless
—`scratchpad/wgcss/Container__Container.pretty.css:18-22`— but the box's frame is drawn by a
surrounding wrapper.) WG's recurring box-edge idiom is a 1rem `box-shadow` double ring —
`box-shadow: 0 0 0 1rem rgba(0,0,0,.3), 0 0 0 1rem rgba(255,255,255,.15) inset`
(e.g. the CButton "ghost" variant, `AmmunitionPanel__AmmunitionPanel.pretty.css:2538`) — dark
outer ring + light inner bevel, which is the bevel visible in the screenshot. Our frame uses
a different mechanism (the `card_border.png` border-image texture); thickening it is the
simplest match. Only if the texture frame can't be made to read like that bevel would
switching to the box-shadow double-ring be worth considering.

### Touch points
- `MoECalculator.css` — `#moe-root::before` (`:56-57`); update the "Frame thickness" row in
  the handoff knobs table when it lands.

### Verification
- Live in-client vs. a real bottom-bar box (screenshot compare, as in `TASKS/refs/`): the
  thicker frame should read closer to those boxes; check the edge line stays crisp (see the
  slice gotcha).

---

## 7. Gold "below 85%" zone colour = mission-timer gold

### Summary
The current-percentile "gold" band (65 ≤ pct < 85) should use the **same gold as the garage
mission cards' countdown timer**, instead of the current `#ffd977`.

### Findings
- Our gold zone is `#ffd977`, used in two rules: the readout
  `#moe-root.moe-zone-gold .moe-cur-pct { color: #ffd977 }` (`MoECalculator.css:100`) and the
  fill `#moe-root.moe-zone-gold .moe-fill { background-color: #ffd977 }` (`:104`). The band is
  assigned by JS `zoneOf()` returning `"gold"` for `65 ≤ p < 85` (`MoECalculator.js:53-59`).
- **WG's mission-timer gold (extracted from the client):** `#edcb9e` — a warm gold/amber.
  Selector `.Timer_label__accent` in
  `gui/gameface/_dist/production/mono/user_missions/lib/lib.css` (from `gui-part4.pkg`). The
  garage daily-missions card (`DailyBonusMissionCard`) wraps this shared `Timer` component;
  the card's own `_timer` rule only positions it, the colour comes from `Timer_label__accent`.
  Its full declaration also carries an amber/orange glow:
  ```css
  color: #edcb9e;
  font-weight: 500;
  text-shadow: 0 0 6rem rgba(255,228,159,0.16), 0 0 10rem rgba(255,177,86,0.24),
               0 0 12rem rgba(255,61,0,0.32), 0 1rem 0 rgba(0,0,0,0.3);
  ```
  (The timer's only other state is `cooldown` = muted off-white — not a red "expiring" gold —
  so `#edcb9e` is the unambiguous normal gold.)

### Suggested approach
- Replace `#ffd977` → `#edcb9e` at `MoECalculator.css:100` and `:104`.
- **Note the value is noticeably paler/warmer than the current `#ffd977`.** On the *readout
  text* it should read fine (that's exactly where WG uses it). On the *bar fill* the paler
  tone may look washed over the bright hangar — check live; the glow `text-shadow` above is
  what gives WG's timer its punch, so if the flat `#edcb9e` looks weak on the readout, port
  that `text-shadow` onto `.moe-zone-gold .moe-cur-pct` too (text-shadow doesn't apply to the
  fill's `background-color`).
- Update the "gold" colour note in comments (`:97`) if the hex changes.

### Touch points
- `MoECalculator.css` — `.moe-zone-gold .moe-cur-pct` (`:100`), `.moe-zone-gold .moe-fill`
  (`:104`), optional glow on the readout.

### Open questions
- Apply `#edcb9e` to **both** the readout text and the bar fill, or only the readout (where
  WG actually uses it), keeping a punchier gold for the fill? Recommend: try both, eyeball the
  fill over a bright hangar.
- Port WG's amber glow `text-shadow` onto the gold readout, or keep it flat?

---

## Cross-cutting notes
- Dev loop, image-cache caveat, live-screenshot (STA clipboard) method, and the pkg-CSS
  extraction technique are all in `TASKS/widget-polish-handoff.md` — not repeated here.
- Items 1, 3, 4 are low-risk CSS/JS. Item 5 is a one-line JS change + a user decision.
  **Item 2 is the only one with a real risk** (pointer-events vs. drag-to-rotate) and needs
  a live input test before it's called done.
- When this round + the uncommitted rounds 1–3 are locked, the working tree
  (JS/CSS/`card_border.png`/`sync_gameface.py`) still needs a **commit** (see the handoff).
