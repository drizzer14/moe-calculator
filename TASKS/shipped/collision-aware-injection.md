# Research: Collision-aware sub-view injection (coexist with any mod)

_Submitted: port from the Garage Progress Bar (2026-07-09) · Status: IMPLEMENTED IN WORKING TREE (2026-07-09, UNCOMMITTED) — pending in-client verify + 0.2.0 release_

> **Landed (uncommitted working tree — NOT yet committed/verified, so not truly "shipped"):**
> pure `domain/placement.py` (`choose_placement` → WAIT/INJECT/BLOCKED) + `tests/test_placement.py`
> (11 cases, green); bridge `INJECT_FIELD`, placement globals, `set_candidate_order`,
> `has_inject_model`, `note_mount`, and a real `detach()` teardown wired into `refresh()`'s
> host-gone branch — this **also closes the `_active` teardown** from [[garage-bridge-lifecycle]].
> Entry point `_CANDIDATES` = `[params, stats]`, each presenter imported + patched independently
> via `_resolve_presenter` / `_patch_presenter`. 95 tests pass; all edited client modules
> byte-compile under Python 2.7.
> **Still open:** the `VehiclesStatisticsPresenter` GATING PROBE (is `stats` always-mounted +
> does its `_onLoading` fire?), the full in-client verification checklist below (running client,
> REPL port 2224), and the 0.2.0 version bump + release (do NOT bump until verified). Rider 2
> (front-end JS observer stacking) is tracked in [[garage-bridge-lifecycle]].

## Summary

MoE's garage widget shares the last-writer-wins `ModInjectModel` problem with every
OpenWG mod: OpenWG stores exactly ONE `ModInjectModel` per hangar sub-view and its JS
injector (`gui/gameface/js/index.js`) processes each sub-view **once** (`injectedResIds`
Set keyed by sub-view, no re-inject hook), so two mods that inject onto the same sub-view
silently blank each other. Today `mod_moe_calculator.py` injects onto
`HangarVehicleParamsPresenter` unconditionally — it clobbers, or is clobbered by, anyone
else there. The sibling Garage Progress Bar was just made collision-aware (its commit
`6a6a631`); this is the symmetric port so MoE also **detects an occupied sub-view and
places on a free one instead of overwriting**.

Merging into a shared model is NOT possible (verified against OpenWG v1.1.6:
`gf_mod_inject` overwrites a fixed field; the JS one-shot ignores later edits). The
feasible robustness is collision-AVOIDANCE.

## Findings (mechanism — already proven live)

- OpenWG `gf_mod_inject(model, name, …)` builds one `ModInjectModel` and assigns it to
  the **fixed** VM field `"ModInjectModel"` (the `name` arg is only a JS-side
  discriminator). Second call on the same VM overwrites.
- Wulf `ViewModel` exposes **no name-based getter** for a child model (only index-based
  `_getViewModel(idx)`), BUT the native proxy's `toString()` serializes the model tree
  (field names included) to JSON. So `'"ModInjectModel"' in vm.proxy.toString()` reliably
  detects an existing injection. Confirmed live from the Garage-bar's REPL, including
  reading MoE's own `VehicleParamsViewModel` (`moe_hostvm_has_MIM = True`) — cross-mod
  detection works.
- MoE's structure mirrors the Garage bar's (entry point patches one presenter's
  `_onLoading`, bridge `attach()` = `gf_mod_inject` + `_addViewModelProperty(DATA_PROP)`
  + caches `_active`), so the port is nearly mechanical.

## Plan (port of Garage-bar commit 6a6a631)

### 1. New `moe_calculator/domain/placement.py` (pure, engine-free)
Verbatim copy of the Garage bar's module. Exposes `WAIT/INJECT/BLOCKED` and:
`choose_placement(order, vms, has_inject) -> (action, name)` — walk priority order;
skip a foreign-occupied candidate; the first not-yet-mounted candidate forces `WAIT`
(so we never commit to a fallback while the preferred sub-view is still pending);
`BLOCKED` only when every candidate is mounted and occupied.

### 2. `bridge/gameface_bridge.py`
- Add `INJECT_FIELD = "ModInjectModel"` near the `WIDGET_NAME`/`DATA_PROP` constants.
- Add placement globals: `_candidate_order = []`, `_candidate_vms = {}`,
  `_placed_name = None`, `_placed_vm = None`.
- `set_candidate_order(names)` — set the priority list.
- `has_inject_model(vm)` — `try: return ('"%s"' % INJECT_FIELD) in vm.proxy.toString()
  except: return False` (fail-soft to False).
- `note_mount(name, vm)` — record the candidate's VM; if already committed, act only
  when OUR sub-view re-mounts (never migrate → no duplicate widget; if a fresh VM is
  foreign-occupied, yield instead of clobber); else run `choose_placement` and `attach`
  the chosen VM, logging `LOG_NOTE` on fallback / on BLOCKED. **Keep `attach()` as-is**
  (it must still call `moe_data.start()` after a successful inject).
- Update the module docstring (drop "we inject onto HangarVehicleParamsPresenter" →
  "collision-aware placement across candidate sub-views").

### 3. `gui/mods/mod_moe_calculator.py`
- Extract the `_onLoading` monkey-patch into `_patch_presenter(bridge, P, name)`
  (idempotent per class via the existing `_moe_calculator_patched` flag), calling
  `bridge.note_mount(name, self.getViewModel())` then `bridge.push` on the returned
  `(host_vm, rvm)`.
- Candidate order — **MUST be disjoint from the Garage bar's `[crew, loadout]`** so the
  two 14th_ua mods never contend:
  `[("params", HangarVehicleParamsPresenter), ("stats", VehiclesStatisticsPresenter)]`
  — params is MoE's natural home (uncontested by the Garage bar, which now avoids it);
  `VehiclesStatisticsPresenter` (`…hangar/presenters/vehicle_statistics_presenter.py`,
  a `ViewComponent` with its own `_onLoading`) is the proposed fallback.
  **GATING PROBE (light):** confirm `VehiclesStatisticsPresenter` is always-mounted in the
  standard garage and its `_onLoading` fires (the detection primitive itself is already
  proven). If it is NOT always present, use another own-`_onLoading` `ViewComponent`
  from that dir (e.g. `VehicleMenuPresenter`) — just keep it out of `{crew, loadout}`.
- Leave `_install_battle()` untouched — the in-battle overlay is a registered Gameface
  **window**, not sub-view injection, so it has no collision problem.

### 4. Tests — `tests/test_placement.py`
Copy the Garage bar's suite (adjust the import to `moe_calculator.domain.placement`):
preferred-free→inject; preferred-unmounted→wait; fallback-free-but-preferred-pending→wait;
preferred-foreign+fallback-free→inject fallback; all-foreign→blocked; single-candidate
free/foreign; explicit `None` VM treated as unmounted. Run `python -m pytest -q`, expect green.

## Coordination / riders

- **Disjoint lists are the contract.** Document in BOTH mods that Garage=`[crew, loadout]`
  and MoE=`[params, stats]` are deliberately non-overlapping. A future edit that overlaps
  them re-introduces mutual displacement.
- **Folds into [[garage-bridge-lifecycle]].** That bug adds a teardown clearing `_active`;
  the same teardown MUST also reset `_placed_name`/`_placed_vm` (else after a hangar
  rebuild we think we're still committed to a torn-down sub-view). Do these together, or
  land placement first and note the new globals in the lifecycle fix.
- Rider 2 of the lifecycle note (does OpenWG re-execute injected JS modules per mount →
  stacked `observer.onUpdate`?) is orthogonal but worth resolving in the same REPL session.

## Touch points

- NEW `src/res/scripts/client/moe_calculator/domain/placement.py`
- `src/res/scripts/client/moe_calculator/bridge/gameface_bridge.py` — constants, globals,
  `set_candidate_order`, `has_inject_model`, `note_mount`, docstring
- `src/res/scripts/client/gui/mods/mod_moe_calculator.py` — `_patch_presenter` + candidate list
- NEW `tests/test_placement.py`

## Verification

- `python -m pytest -q` green (placement suite + existing 40+).
- Build+deploy (`build/deploy_wotmod.py`, client CLOSED) + relaunch; debug REPL on
  **2224** (MoE's port). With the Garage bar also installed, confirm: both bars render;
  `bridge._placed_name == "params"`; `bridge._candidate_vms` has both candidates; the
  chosen VM `has_inject_model` True and the fallback VM False (single injection); a
  non-destructive `choose_placement(order, vms, forced-params-occupied)` returns
  `(INJECT, "stats")`; `refresh()` still returns True.
- Residual limitation (document in code, same as Garage bar): yields to a mod that claimed
  a sub-view *first*, but cannot win a load-order race where a non-cooperating mod
  overwrites us *after* we inject and before the JS one-shot. Only a hard fix is upstream
  OpenWG (merge / mod-keyed injection).

## Release

Behavior change → version bump (0.1.0 → **0.2.0**) + rebuild installer/zip + tag/release
per the MoE release process. Coordinate with any other unshipped 0.1.0-era commits.

## Open questions

- Is `VehiclesStatisticsPresenter` always-mounted in the standard garage? (Gating probe.)
- Land placement before or after [[garage-bridge-lifecycle]]? (They share the bridge globals.)
