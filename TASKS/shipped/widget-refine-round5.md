# Research: Widget visual refinement — round 5

_Submitted: (1) "match numbers' shadow/border to that of the top-right corner garage widgets";
(2) "make the bar span full width like it was before, but split into 5 regions: below 50%,
50–65%, 65–85%, 85–95%, 95–100%"; (3) "hover should only brighten the background, not the
border." · Status: shipped (2026-07-06)_

> Shipped: all three items applied & synced (5-region equal-fifths `barX`, WG-matched layered
> text-shadows, hover brightens background only). NB the per-zone band colours added alongside
> round 5 were later REMOVED per user — the bar is now white-only (see the widget-polish handoff
> / memory).

Round 5 of MoE widget polish — three items. Front-end only. Continues
`TASKS/widget-polish-handoff.md`. **Round 4 shipped** (archived at
`TASKS/shipped/widget-refine-round4.md`); items 1 and 3 build on shipped round-4 items 7 and 2
(cross-refs below).

---

## 1. Match number shadow/border to the top-right garage widgets

### Summary
The widget's numbers carry a heavy dark blur; the user wants their shadow / "border" to match
WG's top-right corner widgets (Battle Pass chapter-progress + missions/event cards). Up-front
fact from the extraction: **WG uses NO text stroke** (`-webkit-text-stroke`/`text-stroke`
appear nowhere in the Battle Pass / user-missions CSS) — every outline/glow on those numbers
is layered `text-shadow`. So "match the border" = adopt the layered shadow, not a CSS outline.

### Findings — our numbers today
- `.moe-cur` (current damage + %, children inherit) — `text-shadow: 0 1rem 4rem rgba(0,0,0,0.9),
  0 0 2rem rgba(0,0,0,0.6)` (`MoECalculator.css:90`).
- `.moe-tick-req` (per-mark requirement) — `text-shadow: 0 1rem 3rem rgba(0,0,0,0.9)` (`:273`).
- `.moe-split-label` ("50%" / round-4 "100%") — `text-shadow: 0 1rem 3rem rgba(0,0,0,0.9)` (`:181`).
No text-stroke anywhere (already matches WG's approach).

### Findings — WG's idioms (extracted; sources in `scratchpad/wgcss/`, session-scoped)
1. **BP progress numbers ("Stage N", "18 / 100") — FLAT: no shadow, no stroke** (cream bold
   text on the widget's own dark surface).
2. **Warm-gold accent glow — the shared "important number" style** (`.Timer_label__accent`,
   `.ShortCounter_text`; identical in `battle_pass/lib` + `user_missions/lib`), with
   `color:#edcb9e; font-weight:500`:
   ```css
   text-shadow: 0 0 6rem  rgba(255,228,159,0.16),
                0 0 10rem rgba(255,177,86,0.24),
                0 0 12rem rgba(255,61,0,0.32),
                0 1rem 0  rgba(0,0,0,0.3);
   ```
   **Same four-layer glow as round-4 item 7's mission-timer gold, which SHIPPED** — the gold
   readout is already `#edcb9e`; round 5 adds the matching glow shadow on top.
3. **Plain card label drop-shadows:** dark surface / light text →
   `text-shadow: 0 1rem 0 rgba(13,14,16,0.4)`; light surface / dark text →
   `0 1rem 0 rgba(255,255,255,0.7)`.

### The tension (not a straight copy)
WG's numbers sit on **solid dark surfaces**; ours **float over the live hangar** (semi-
transparent panel) — which is why the current shadow is a heavy `4rem/0.9` blur for
legibility. Porting WG's subtle `0 1rem 0 rgba(13,14,16,0.4)` verbatim may read too faint over
a bright hangar. Judgement call: pixel-match WG vs. stay legible while floating.

### Suggested approach
- **`.moe-cur-pct`** (the "important number") → idiom **2** glow, bundled with item 7's
  `#edcb9e`. Caveat: the glow is warm-gold but the readout recolours per zone
  (`moe-zone-*`, `:99-102`); a warm glow under teal/purple reads oddly. First cut: idiom-2
  glow in the **gold zone**, neutral drop elsewhere.
- **`.moe-cur-dmg`, `.moe-tick-req`, `.moe-split-label`** (plain numbers) → idiom **3-dark**
  `0 1rem 0 rgba(13,14,16,0.4)`; **if too faint over a bright hangar, keep a stronger dark
  layer** (e.g. add `0 0 3rem rgba(0,0,0,0.7)`) — a deliberate float-context deviation.
- Stay stroke-free (matches WG).

### Touch points
- `MoECalculator.css` — `.moe-cur` (`:90`; split per-child if the readout gets the glow),
  `.moe-cur-pct` gold-zone (`:100`, with item 7), `.moe-tick-req` (`:273`), `.moe-split-label`
  (`:181`).

### Open questions
- Mapping confirm (accent glow gold-zone-only or per-zone-tinted?).
- WG's subtle `0 1rem 0` drop vs. a heavier dark layer for float-legibility?
- Round-4 item 7 already applied `#edcb9e` to the gold readout — confirm the glow shadow
  should now be layered on top (they're the same WG idiom).

---

## 2. Full-width bar, split into 5 regions

### Summary
Revert the bar to spanning the **full width linearly** (undo the round-3 25%/75% two-section
compression), but divide it into **5 regions** at the milestone boundaries:
below 50% · 50–65% · 65–85% · 85–95% · 95–100%.

### Findings — the current axis (what to replace)
Round 3 introduced a **piecewise two-section axis** `barX()` (`MoECalculator.js:42-48`):
```js
const SPLIT_BAR = 25;   // first 25% of bar width = 0..50 percentile
const SPLIT_PCT = 50;
function barX(percentile){
  const p = Math.max(0, Math.min(100, Number(percentile)||0));
  if (p <= SPLIT_PCT) return p * (SPLIT_BAR / SPLIT_PCT);
  return SPLIT_BAR + (p - SPLIT_PCT) * ((100 - SPLIT_BAR) / (100 - SPLIT_PCT));
}
```
`barX()` maps a percentile → position % and is applied to BOTH the fill width and every tick's
`left` (`js:100,163,164`). Marks 65/85/95 currently land at bar-x 47.5/77.5/92.5. There is one
visible divider `.moe-split` at `left:25%` with a `.moe-split-label` "50%"
(`css:159-184`; markup `js:78-79`). Milestone ticks already draw a `.moe-tick-notch` upright
line at each mark position (`css:249-258`).

### The design decision — region widths
The 5 regions have percentile boundaries **0 · 50 · 65 · 85 · 95 · 100**. How wide is each on
the bar?
- **(a) Equal width — 20% each** (recommended; my read of "5 regions" + "full width"): bar-x
  boundaries **0/20/40/60/80/100**. Marks 65/85/95 → 40/60/80; the 50 split → 20; 100 → right
  edge. This spreads the crowded high-percentile marks even more than today's 25/75 split
  (each region an even fifth), and reads as a clean 5-segment bar.
- **(b) Proportional width** = linear axis (region widths = their percentile span: 50/15/20/
  10/5% of the bar). This is literally "full width like before" but the top marks re-crowd —
  which is the very problem round 3 solved. Likely NOT what's wanted, but it's the honest
  reading of "like it was before."

The phrase pulls both ways ("full width like before" ⇒ linear; "5 regions" ⇒ deliberate
segments). **Recommend (a) equal-width fifths** and confirm with the user.

### Suggested approach
- Replace `barX()` with a general piecewise map over boundary arrays, e.g.:
  ```js
  const PCT_STOPS = [0, 50, 65, 85, 95, 100];   // percentile boundaries
  const BAR_STOPS = [0, 20, 40, 60, 80, 100];   // bar-x boundaries (equal fifths = option a)
  function barX(p){
    p = Math.max(0, Math.min(100, Number(p)||0));
    for (let i=1;i<PCT_STOPS.length;i++){
      if (p <= PCT_STOPS[i]){
        const t = (p-PCT_STOPS[i-1])/(PCT_STOPS[i]-PCT_STOPS[i-1]);
        return BAR_STOPS[i-1] + t*(BAR_STOPS[i]-BAR_STOPS[i-1]);
      }
    }
    return 100;
  }
  ```
  (Keeps `barX` applied to fill + ticks as-is, so those stay consistent for free. Retire the
  `SPLIT_BAR`/`SPLIT_PCT` constants.)
- **Region boundaries visually:** 65/85/95 are already drawn by the tick notches; the 50
  boundary is the existing `.moe-split` — just reposition it to the new 50→20% spot (or make
  the divider position data-driven off `barX(50)`). 0 and 100 are the bar ends (100 dovetails
  with round-4 item 3's end tick). So minimal new DOM if "regions" = boundary lines.
- **If "regions" means shaded bands** (not just boundary lines), add 5 background segments
  tinted per region — bigger change; see open question. Note the 5 regions do NOT map 1:1 to
  the 4 `zoneOf()` colour bands (zones split at 65/85/95; regions add a 50 boundary inside the
  white zone), so region tinting ≠ zone tinting.

### Touch points
- `MoECalculator.js` — `barX()` + constants (`:42-48`); it already feeds fill + ticks.
- `MoECalculator.css` — `.moe-split` / `.moe-split-label` position (`:159-184`); optional
  region-band backgrounds on `.moe-track`.
- Interacts with round-4 items 3 (100% end tick = the 95–100 region's right edge) and 4 (50%
  passed = region 1|2 boundary). Best sequenced with those.

### Verification
- Live: bar fills the panel width; the 5 regions read clearly; marks sit on their boundaries;
  fill edge + ticks still agree (both go through `barX`).

### Open questions
- **Region widths: equal fifths (a, recommended) or proportional/linear (b)?**
- Do "regions" mean **boundary lines** (cheap; mostly already present) or **shaded/tinted
  bands**? If tinted, what colours (they don't match the zone bands)?

---

## 3. Hover brightens the background only, not the border

### Summary
Constraint on the (shipped) round-4 hover: hovering the widget should brighten only the
background, leaving the frame/border unchanged. **Verify the shipped hover already does this;
fix it if the frame reacts on hover.**

### Findings
This **matches what the extraction found** for round-4 item 2: WG's bottom-bar box hover is a
single 15% white background overlay and touches **nothing else** — no border / border-image
change, no box-shadow, no filter (`Container__Container.pretty.css:25-29`). So the intended
approach was already frame-agnostic; this item locks it in explicitly (don't animate
`#moe-root::before` / the `card_border.png` frame on hover).

### Suggested approach
Ensure the hover rule is exactly `#moe-root:hover { background-image:
linear-gradient(rgba(255,255,255,.15), rgba(255,255,255,.15)); }` with **no `:hover::before`
rule** and no frame animation. If round 4 shipped a frame change on hover, remove it.

### Touch points
- The shipped hover CSS on `#moe-root` / `#moe-root:hover`. Reference:
  `TASKS/shipped/widget-refine-round4.md §2`. This note adds only the "frame stays put"
  constraint.

### Open questions
- None — merges into round-4 item 2.

---

## Cross-cutting
- Dev loop, live-screenshot (STA clipboard), and pkg-CSS extraction technique are in
  `TASKS/widget-polish-handoff.md`. Extracted WG CSS in `scratchpad/wgcss/` is session-scoped.
- Item 2 (5-region bar) is best sequenced with round-4 items 3 (100% end tick) and 4 (50%
  passed), since all three touch the bar's boundaries.
