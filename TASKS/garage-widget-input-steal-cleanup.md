# Research: Garage widget input-steal + bridge lifecycle cleanups

_Submitted: repo-wide bug hunt (2026-07-11) · Status: open_

## Summary

A cluster of garage-side bridge/front-end issues. The one worth treating as a real defect is
the garage widget still capturing the pointer for a feature that's now disabled (a latent
input-steal). The rest are dead marshaling, a stale-doc trap, and lifecycle edge cases that are
fail-soft today but waste work / risk drift.

## Findings

### 1. `#moe-root` keeps `pointer-events: auto` although its only consumer (the tooltip) is disabled — HEADLINE
> **WRONG / WON'T-FIX (2026-07-11):** this finding is incorrect. `pointer-events: auto` is NOT
> tooltip-only — it also powers the box's own `:hover` polish (`#moe-root:hover` brightens the
> fill + fades the border into one flat panel, with a transition). `:hover` only fires on an
> element that RECEIVES pointer events, and CSS has no "hover-for-styling-but-click-through"
> mode, so setting `pointer-events: none` silently kills the hover visual (attempted + reverted,
> user-confirmed regression). The box sits over largely-dead hangar space and its children stay
> `pointer-events:none`, so the residual capture is acceptable. LEAVE `#moe-root` at `auto`.
> Findings #2 (drop dead `setIcon`/`mark_icon_url`) and #3 (stale battle full-screen docs) DID
> ship. See memory [[garage-box-pointer-events]].

`MoECalculator.css:45-50`. The root is `pointer-events: auto` *solely* so it can react to
`:hover` for the hover tooltip (the comment says exactly this). But the tooltip is disabled:
`MoECalculator.js:142` `TOOLTIP_ENABLED = false`, so `ensureTooltip()` is never reached and no
hover listener is ever bound. `auto` now captures the pointer over the box footprint
(a wide panel floating above the carousel) for **zero benefit** — every other overlay child is
correctly `pointer-events: none`; only the root captures. A click / drag-to-rotate that begins
inside the box footprint is swallowed instead of reaching the hangar.
**Severity:** input-steal (latent). **Confidence:** medium (that `auto` is now purposeless is
high; that it overlaps an interactive region is medium — depends on exact box placement).
**Fix:** set the root to `pointer-events: none` while `TOOLTIP_ENABLED` is false (or gate the
CSS/JS together so the two never drift).

### 2. Per-tick `setIcon` marshaling is dead work — JS ignores the pushed `icon`
`gameface_bridge.py:485` marshals `tv.setIcon(fmt.mark_icon_url(model.nation, tk.mark_count))`
into `MarkTickVM.icon` (index 4) every push, but the widget renders the hardcoded `FLAT_MARK`
glyph and never reads `tk.icon` (`MoECalculator.js:103-106,120` — `markIcon(count)` →
`FLAT_MARK`). `MoEVM.nation` (index 1) is likewise never read by the JS; it exists only to feed
this dead icon URL. Wasted per-push adapter call + marshaling; a misleading contract.
**Severity:** cosmetic/latent. **Confidence:** high. **Fix:** drop the `setIcon` call +
`mark_icon_url` (and `nation`) if the flat glyph is the intended final look, OR wire the JS to
consume `tk.icon` if nation art was the intent. Decide which; don't ship both.

### 3. Stale "full-screen" docs in the battle front-end (latent trap)
`MoEBattleView.html:12-13` and `MoEBattle.js:4-7` still describe the overlay as a "full-screen,
input-transparent top-layer window." `battle_view.py:95-113` documents at length that
`WINDOW_FULLSCREEN` was **dropped** (window is content-sized now) specifically to fix the
Ctrl+click/hover input-steal. A future editor trusting the header could re-add full-screen
sizing / `width:100%` and reintroduce the cross-surface hit-test steal the content-sizing
avoids. Same class as the already-noted `MoEBattle.css` position comment, in two more files.
**Severity:** cosmetic (latent trap). **Confidence:** high. **Fix:** correct both headers to
"content-sized." (Ties to #1 — both are about not re-introducing input steal.)

### 4. Garage `_active` only torn down on battle-entry, not on ordinary sub-view unmount
`gameface_bridge.py:436-449` (`refresh`) + `:322-336` (`_host_alive`). `_host_alive()` returns
False only when the lobby state machine is gone (battle). If the injected `params`/`stats`
sub-view unmounts during ordinary in-lobby navigation (a full-screen lobby view that tears the
presenter down) while the lobby machine still exists, `_active` still references the torn-down
host VM and `_host_alive()` is True, so `refresh()` (fired by a stats sync / settings change /
moe-data-ready) calls `push()` into a dead VM. Fail-soft (push is `try/except`ed) and
self-heals on re-mount (`note_mount` re-attaches), but wastes work + log-spams until then.
**Severity:** latent. **Confidence:** medium.

### 5. Sub-view re-mount re-runs `gf_mod_inject` on the shared hangar document
`gameface_bridge.py:392-405` (re-attach) → `attach:340-358` → `openwg_gameface.gf_mod_inject`.
On re-mount with a fresh VM (post-battle rebuild, any presenter re-mount) `attach()` re-invokes
`gf_mod_inject`, re-listing `MoECalculator.css`/`.js` for the hangar doc and building a fresh
`MoEVM`. If OpenWG's injector doesn't dedupe asset URLs per document, the JS module could be
imported twice → a second `ModelObserver`/render subscription against the same `#moe-root`
(the DOM is id-deduped by `ensureRoot`, so at worst double renders, not double DOM).
**Severity:** latent. **Confidence:** low (depends on OpenWG dedup behavior — verify in-client).

### 6. `_on_vehicle_changed` refreshes synchronously instead of coalescing
`gameface_bridge.py:93-103`. Unlike `_on_sync_completed` (which routes through
`_schedule_refresh` because `CurrentVehicle` only rebuilds its item on the next tick),
`_on_vehicle_changed` calls `refresh()` directly. A vehicle change that also triggers an
items-cache sync yields one direct push (possibly reading a not-yet-rebuilt `CurrentVehicle`)
plus one coalesced push → a brief stale readout on tank switch + a redundant double push.
**Severity:** latent (transient wrong-answer). **Confidence:** low-medium. **Fix:** route
`_on_vehicle_changed` through `_schedule_refresh` too, or confirm the direct read is always
current.

### Related (already tracked elsewhere, not re-filed)
- `wulf_args.py` is dead code but deliberately **kept** for the Phase-3 Ctrl+drag feature — see
  `TASKS/code-cleanups-2026-07.md` and `TASKS/mod-positioning.md`. Do not delete.

## Suggested approach

#1 and #3 are the input-steal-safety pair — fix together and verify no cross-surface capture.
#2 is a decision (flat glyph vs nation art) then a deletion or a wiring. #4/#5/#6 are lifecycle
hardening — land opportunistically when a feature next touches `gameface_bridge.py` (the same
"wait for an adjacent change + bridge tests" caveat as the bridge-scaffolding extraction in
`TASKS/code-cleanups-2026-07.md`).

## Touch points

- `MoECalculator.css:45-50` · `MoECalculator.js:142,103-106,120`
- `gameface_bridge.py:93-103,322-336,340-358,392-405,436-449,485`
- `MoEBattleView.html:12-13` · `MoEBattle.js:4-7` · `bridge/battle_view.py:95-113`

## Verification

- #1/#3: in-client — start a drag-to-rotate and clicks over the garage box footprint; confirm
  the hangar still receives them (no steal). No hot-reload for battle → relaunch for #3.
- #2: confirm the tick still renders after dropping `setIcon` (flat glyph is client-side).
- #4/#5/#6: in-client navigation stress (enter/leave sub-views, tank-switch, post-battle
  return) watching the log for pushes into dead VMs / double subscriptions.

## Open questions

- #2: is the flat glyph the intended final look, or was nation mark-art the goal? (Decides
  delete-vs-wire.)
- #5: does OpenWG `gf_mod_inject` dedupe asset URLs per document? Needs a live probe.
