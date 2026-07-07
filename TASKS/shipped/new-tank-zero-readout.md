# Research: Show 0 / 0% on a brand-new tank

_Submitted: "When a tank is new, show 0 as current damage and 0% as current percent" · Status: **SHIPPED 2026-07-06** (front-end only, uncommitted)_

## Resolution (what shipped)
Applied exactly as suggested — dropped the `dmg > 0 ? … : "—"` guards in `render()`
(`MoECalculator.js`), now always `thousands(dmg)` / `pctText(pct)` (0 → "0" / "0%"). User
confirmed "LGTM". No Python/CSS change.

---


## Summary
A never-played tank currently renders the readout as `—` (damage) and blank (percent). Show
explicit `0` and `0%` instead.

## Findings
- The readout is set in `render()` (`MoECalculator.js:152-155`):
  ```js
  const dmg = data.curAvgDamage || 0;
  const pct = data.curPercent || 0;
  root.querySelector(".moe-cur-dmg").textContent = dmg > 0 ? thousands(dmg) : "—";
  root.querySelector(".moe-cur-pct").textContent = dmg > 0 ? pctText(pct) : "";
  ```
  So on a new tank (`dmg === 0`) it shows `"—"` and `""`.
- A new tank genuinely reads 0: `engine_adapter._read_moe()` returns `(0, 0.0, 0)` for a
  vehicle with no dossier records (`engine_adapter.py:56-57,66-68`), so `curAvgDamage=0` /
  `curPercent=0` are pushed. These come from the **synchronous dossier read**, NOT the async
  thresholds table — so `dmg === 0` reliably means "new/unplayed tank", never "still loading".
  Showing `0`/`0%` is therefore honest, not a placeholder-for-unknown.
- The formatters already produce the wanted output: `thousands(0)` → `"0"` and `pctText(0)` →
  `"0%"` (`MoECalculator.js:34-36`, the `p <= 0` case). So the fix is just to drop the guards.

## Suggested approach
Always format both values:
```js
root.querySelector(".moe-cur-dmg").textContent = thousands(dmg);   // 0 -> "0"
root.querySelector(".moe-cur-pct").textContent = pctText(pct);      // 0 -> "0%"
```
(The static damage icon `.moe-cur-icon` still shows — icon + `0` reads fine.) The bar fill
(`barX(0)=0`) and ticks already render correctly at 0%; only the readout text changes.

## Touch points
- `MoECalculator.js` — the two lines at `:154-155` (and the `dmg`/`pct` locals at `:152-153`
  stay). No Python / CSS change.

## Verification
- Live in-garage on a freshly-bought, never-played tank: readout shows `0` and `0%` (not `—`);
  bar is empty. A played tank still shows its real values.

## Open questions
- Confirm `0`/`0%` is wanted for *every* zero-damage case (also e.g. a tank played 0 damage in
  its only battle) — assumed yes; the point is to never show `—`.
