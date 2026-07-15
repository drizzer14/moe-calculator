# HANDOFF — in-battle overlay row backdrop misalignment

**Status:** ROUND 2 fix applied + deployed + overlay-synced. **PENDING in-client re-verification
by the user (relaunch required — no hot-reload for the battle window).** UNCOMMITTED.
**Base commit:** `a3d194b`. Only `MoEBattle.css` is dirty (tuner was reverted to clean state).

## ROUND 2 (current) — residual progressive drift

Round-1 fix (below) reduced the drift but did NOT eliminate it. User re-verified in-client:
**still progressive (grows down the stack), backdrop still too HIGH** relative to text.

**Refined root cause:** the numerals stack at the true 21rem pitch (in-flow) while each lower
row's abspos backdrop pseudo origin creeps UP — a Gameface **flex-COLUMN** quirk. The abspos
containing-block origin the engine hands each stacked flex ITEM is under-counted per item, so the
correct `top/bottom: -6rem` resolve against a drifting origin. (Same buggy flex subsystem as the
unsupported `gap` and the round-1 negative-margin drift.)

**Fix:** `#moe-battle-root` changed `display: flex; flex-direction: column` → **`display: block`**.
Rows tile with deterministic block flow; each `.mb-row` is still a flex ROW internally. Nothing
else touched (padding-pitch + ±6rem pseudo overflow from round 1 all kept).

**⚠ SHADOW CORRECTION (round-1 note was WRONG):** `res_mods/<ver>/gui/gameface/mods/14th_ua/`
DOES contain a full `MoECalculator/` copy incl. `MoEBattle.css`, and it **shadows the packaged
`.wotmod`** — that overlay is what the client actually loads. `deploy_wotmod.py` alone does NOT
update it. After editing battle CSS/JS you MUST also run
`python tools/dev/sync_gameface.py "D:/Games/World_of_Tanks_EU" 2.3.1.0` (note: client version
folder is now **2.3.1.0**, not 2.3.0.1). Round 2 has been synced — overlay verified `display:
block`. On `lgtm` → commit; suggested `fix(battle): stop flex-column backdrop drift (display:block)`.

---

## ROUND 1 (superseded but kept for context)

## The bug (user's words)

> "In-battle row shadow and dots do not respect corrected row gaps."
> Clarified: "make them aligned with the text on Y axis to the center, like the first row.
> Currently, the lower the row, the more they shift to top." Later: "Leave their appearance
> as is, just make them aligned."

The per-row backdrop (`.mb-row::before` = checker dots, `.mb-row::after` = dark radial shadow)
drifts UP relative to its text, cumulatively — row 1 is correct, each lower row worse. This
shows on the 3-row overlay (damage / percent / optional Counted-Assistance row).

## Root cause (proven, not guessed)

A **Gameface/Coherent-specific** bug, NOT a CSS error. Reproduced the exact 3-row DOM + CSS in
headless Edge and MEASURED backdrop-box-center minus text-center: **`0.0` for every row** in a
standards browser (perfect alignment, no drift, at any inset). So the spec-correct CSS is fine;
the engine is the culprit.

The drift is *cumulative down the stack*. The only per-row-accumulating quantity was
`.mb-row { margin-bottom: -12rem }` — the negative margin that overlapped the airy 8rem-padded
rows to reach WG's ~44px (21rem) native pitch. **Gameface does not apply that negative-margin
overlap identically to the in-flow numerals and to the absolutely-positioned backdrop pseudos**,
so the pseudos creep up one notch per row. (This is the same Coherent build where flex `gap` is
unsupported — negative-margin flex quirks are consistent with that.)

### Dead end (first attempt, do not repeat)
Hypothesized "overlap doubles the shadow/dots in the gap" and inset the pseudos `top/bottom: 0
→ 6rem`. WRONG: it never touched the margin (the actual cause) so drift remained, and it
*shrank* the blobs (radial radii are box-%). User rejected it. That commit-worthy insight:
**the fix must remove the negative margin, not adjust the pseudos within it.**

## The fix (applied to `src/.../MoECalculator/MoEBattle.css`)

Remove the negative margin; get the identical 21rem pitch from padding; restore the original
33rem blob via a symmetric NEGATIVE pseudo inset (overflow, not shrink); nudge root +6rem to
put every baseline back exactly where it was.

| rule | before | after |
|------|--------|-------|
| `#moe-battle-root` | `top: 27.5rem` | `top: 33.5rem` (+6rem; compensates the 8→2rem top-padding lift) |
| `.mb-row` | `padding: 8rem 32rem; margin-bottom: -12rem` | `padding: 2rem 32rem` (box height = 21rem pitch; **no margin-bottom**) |
| `.mb-row::before` | `top: 6rem; bottom: 6rem` | `top: -6rem; bottom: -6rem` (overflow → 33rem blob, centred) |
| `.mb-row::after` | `top: 6rem; bottom: 6rem` | `top: -6rem; bottom: -6rem` (same) |

**Why it's equivalent to the ORIGINAL visually** (browser-measured on the new construct):
blob-center = text-center = `0.0` all rows; blob height = 33rem (original, not shrunk); text
pitch = 21rem; row-1 baseline = 44rem — all identical to pre-bug. It IS the original overlay,
minus the construct that triggers the engine bug.

Math for the +6rem root nudge: text-center = `padding-top + content/2`; top padding dropped
8→2rem, lifting every baseline exactly 6rem regardless of content height → +6rem restores it,
and since pitch is unchanged all lower rows follow.

## State of the tree

- `MoEBattle.css` — fix applied (uncommitted).
- `tools/dev/gen_overlay_tuner.ps1` — **reverted to committed state** (an abandoned `--rowinset`
  edit from the dead-end attempt was `git checkout`'d out). NOT yet updated for the new construct.
- Built + deployed to `D:/Games/World_of_Tanks_EU/mods/2.3.0.1/` via
  `C:\Python27\python.exe build/deploy_wotmod.py` (MUST be Py2.7). Packaged `.wotmod` verified
  to contain `top: 33.5rem`, `padding: 2rem 32rem`, two `top: -6rem`, and NONE of the old values.
- Deploy warns of a res_mods gameface overlay shadow — it only holds `WGModResearch` files, does
  NOT shadow `MoEBattle.css`, so the packaged fix loads. (False alarm here.)

## Remaining work (in order)

1. **User verifies in-client** (relaunch WoT → battle → enable Counted Assistance so all 3 rows
   show): each row's shadow+dots centred on its text like row 1; blobs same size as original;
   readout still on WG's native baselines.
2. **On `lgtm` → commit** (per the commit-after-lgtm rule; never before sign-off). Suggested:
   `fix(battle): center row backdrops by dropping Gameface-buggy negative margin`.
3. **Redo overlay-tuner lockstep** for the new padding-pitch construct (user explicitly wanted
   the tuner kept in lockstep). The tuner currently models pitch as `margin-bottom` (rowGap) and
   emits pseudos at `top:0;bottom:0`. Needs: pitch via padding (no negative margin) + emit
   pseudos at a negative overflow inset. `tools/dev/gen_overlay_tuner.ps1` emit block ≈ lines
   316–337; live-preview CSS ≈ lines 42–52; state/apply ≈ lines 274–290.

## Repro tool (for re-verifying geometry without the client)

Headless browser measurement — proved the bug is engine-side and validated the fix:
- Edge: `C:\Program Files (x86)\Microsoft\EdgeCore\150.0.4078.65\msedge.exe --headless=new
  --disable-gpu --dump-dom file:///<path>/repro2.html`
- The two repro HTMLs (`repro.html` = original construct, `repro2.html` = fix) were in the
  session scratchpad (temp). Re-create if needed: mirror the DOM from `MoEBattle.js` `ensureRoot`
  + the `.mb-row`/pseudo rules; make the pseudos visibly coloured; print
  `getComputedStyle(row,'::before')` top/bottom vs the `.mb-value` rect center per row. In a
  standards browser box-center == text-center (=0) always — that's the whole point; the value is
  confirming the new construct keeps blob height 33rem + pitch 21rem + baseline 44rem.

## Key files
- `src/res/gui/gameface/mods/14th_ua/MoECalculator/MoEBattle.css` — the overlay CSS (the fix).
- `src/res/gui/gameface/mods/14th_ua/MoECalculator/MoEBattle.js` — DOM (`ensureRoot`, 3 rows).
- `tools/dev/gen_overlay_tuner.ps1` — the tuner to bring back into lockstep.
- Skill: `moe-battle` (hosting/lifecycle/DOM); `moe-build-release` (build/deploy, no battle
  hot-reload).
