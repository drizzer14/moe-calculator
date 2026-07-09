# -*- coding: utf-8 -*-
"""Pure, engine-free collision-aware placement for the garage widget inject.

OpenWG stores exactly ONE `ModInjectModel` per hangar sub-view and its JS injector
processes each sub-view once, so two mods that inject onto the same sub-view silently
blank each other (last-writer-wins; merging is impossible -- see
TASKS/collision-aware-injection.md). The feasible robustness is collision-AVOIDANCE:
given a priority `order` of candidate sub-views, place on the first FREE one and yield a
sub-view a foreign mod already claimed.

`choose_placement` is the whole decision, kept pure so it is unit-testable with the
client closed. The bridge feeds it live ViewModels + a `has_inject` detector and acts on
the returned (action, name); this module imports zero game symbols.

Anchoring convention for callers: `order` is highest-priority-first. `vms` maps a
candidate name to its mounted ViewModel, or None (== absent) when that sub-view has not
mounted yet. `has_inject(vm)` is True when `vm` already carries a foreign inject model.
"""

# Decision outcomes.
WAIT = "wait"        # a higher-or-equal-priority candidate has not mounted yet -- defer.
INJECT = "inject"    # place on `name` (mounted + free).
BLOCKED = "blocked"  # every candidate is mounted AND occupied -- nowhere free to go.


def choose_placement(order, vms, has_inject):
    """Decide where (or whether) to inject. Returns (action, name):

      * (INJECT, name)  -- `name` is mounted and free; inject there.
      * (WAIT, name)    -- `name` is the first candidate not mounted yet; wait for it
                           (so we never commit to a fallback while a higher-priority
                           sub-view is still pending, and never BLOCK while one may yet
                           come up free).
      * (BLOCKED, None) -- every candidate is mounted and foreign-occupied (or `order`
                           is empty); there is no free sub-view to place on.

    Walks `order` in priority order: an unmounted candidate short-circuits to WAIT; a
    mounted+free one to INJECT; a mounted+occupied one is skipped. Falling off the end
    (all mounted+occupied) is BLOCKED.
    """
    for name in order:
        vm = vms.get(name)
        if vm is None:
            # First not-yet-mounted candidate wins the decision: wait for it.
            return WAIT, name
        if has_inject(vm):
            # A foreign mod already claimed this sub-view -- yield, try the next.
            continue
        return INJECT, name
    return BLOCKED, None
