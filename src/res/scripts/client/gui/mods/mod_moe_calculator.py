# -*- coding: utf-8 -*-
"""14th_ua's MoE Calculator — entry point.

Mount path: WoT 2.x loads only packaged .wotmod. OpenWG's JS injector only acts on
hangar SUB-views, so we patch hangar sub-view presenters to inject our widget assets
and expose our data model; the widget JS renders from that model. Placement is
COLLISION-AWARE: we patch a PRIORITY list of candidate sub-views (params, then stats)
and the bridge injects onto the first FREE one, yielding a sub-view another OpenWG mod
already claimed instead of clobbering it (see TASKS/collision-aware-injection.md). The
list is deliberately disjoint from the sibling Garage Progress Bar's so the two 14th_ua
mods never contend. We recompute on vehicle change.

OpenWG Gameface is a hard dependency. Python 2.7 (BigWorld) runtime.

See the wotmod-architecture harness skill for the layered domain/adapter/bridge
design this scaffold demonstrates, and wotmod-build-deploy for packaging.
"""
from debug_utils import LOG_CURRENT_EXCEPTION
from moe_calculator._compat import LOG_DEBUG

MOD_NAME = "14th_ua's MoE Calculator"
MOD_VERSION = "1.2.0"


# Candidate hangar sub-views in PRIORITY order: (name, module path, class). `params` is
# MoE's natural home; `stats` is the collision-avoidance fallback. Deliberately DISJOINT
# from the sibling Garage Progress Bar's [crew, loadout] so the two 14th_ua mods never
# contend for a sub-view (that disjointness is the coordination contract -- see
# TASKS/collision-aware-injection.md; do not overlap the two lists).
_CANDIDATES = (
    ("params",
     "gui.impl.lobby.hangar.presenters.hangar_vehicle_params_presenter",
     "HangarVehicleParamsPresenter"),
    ("stats",
     "gui.impl.lobby.hangar.presenters.vehicle_statistics_presenter",
     "VehiclesStatisticsPresenter"),
)


def _install():
    import openwg_gameface  # noqa: F401  (hard dependency; raises if absent)
    from moe_calculator.bridge import gameface_bridge as bridge

    # Import + patch each candidate INDEPENDENTLY so a missing/renamed fallback presenter
    # (e.g. across a client patch) can't stop the primary from mounting.
    patched = []
    for name, module_path, class_name in _CANDIDATES:
        P = _resolve_presenter(module_path, class_name)
        if P is None:
            continue
        _patch_presenter(bridge, P, name)
        patched.append(name)

    bridge.set_candidate_order(patched)

    # Arm once now (for an install that happens while already in the hangar); each patched
    # _onLoading re-arms on every subsequent mount.
    bridge.install_all_listeners()
    LOG_DEBUG("[%s] v%s installed (collision-aware sub-view inject: %s)"
              % (MOD_NAME, MOD_VERSION, ", ".join(patched) or "none"))


def _resolve_presenter(module_path, class_name):
    """Import module_path and return its class_name attribute, or None (logged) if the
    presenter is missing/renamed -- so the other candidates still patch."""
    try:
        module = __import__(module_path, fromlist=[class_name])
        return getattr(module, class_name)
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return None


def _patch_presenter(bridge, P, name):
    """Monkey-patch a hangar sub-view presenter's _onLoading to note its mount and push the
    model when the bridge places our widget there. Idempotent per class via the
    _moe_calculator_patched flag."""
    if getattr(P, "_moe_calculator_patched", False):
        return

    _orig_onLoading = P._onLoading

    def _onLoading(self, *args, **kwargs):
        _orig_onLoading(self, *args, **kwargs)
        try:
            # Re-arm on every mount: the battle-exit hangar teardown rebuilds the WG
            # delegate lists but drops ours, so a once-only subscription stops firing after
            # the first battle. install_all_listeners is idempotent (membership-checked), so
            # re-arming every mount is safe and also survives hot reloads.
            bridge.install_all_listeners()
            # note_mount decides placement (collision-aware) and returns (host_vm, rvm) to
            # push into when it placed our widget on THIS sub-view, else None (waiting on a
            # higher-priority sub-view, blocked, or this sub-view is not ours).
            target = bridge.note_mount(name, self.getViewModel())
            if target is not None:
                host_vm, rvm = target
                bridge.push(rvm, host_vm=host_vm)
        except Exception:
            LOG_CURRENT_EXCEPTION()

    P._onLoading = _onLoading
    P._moe_calculator_patched = True


def _install_battle():
    # In-battle overlay: a standalone OpenWG-registered Gameface WINDOW opened OVER the
    # battle HUD (see moe_calculator.bridge.battle_view). The battle HUD has NO shared
    # full-screen Gameface document to inject a position:fixed overlay into (each WG battle
    # Gameface view is composited by Flash at its own placeId), so the garage-style
    # gf_mod_inject sub-view trick cannot work here -- we host our own window instead
    # (the exact pattern WG's gui.impl.battle.prebattle.PrebattleHintsWindow uses).
    #
    # Lifecycle is driven off the GLOBAL PlayerEvents arena hooks (which persist across
    # battles, unlike the per-battle controllers): onAvatarReady opens the window +
    # (re)arms the efficiency listener, onAvatarBecomeNonPlayer destroys it. Arming once
    # here is enough; install_all_listeners is idempotent (membership-checked).
    import openwg_gameface  # noqa: F401  (hard dependency; raises if absent)
    from moe_calculator.bridge import battle_bridge as bbridge

    bbridge.install_all_listeners()
    LOG_DEBUG("[%s] battle overlay armed (registered Gameface window on arena lifecycle)"
              % MOD_NAME)


def _install_settings():
    # Register the two "…Widget Enabled" toggles (ModsSettingsAPI is a SOFT dependency: if it
    # is absent register() logs-and-returns and both widgets stay enabled). Subscribe each
    # feature bridge's apply_settings so a checkbox change takes effect live. Runs BEFORE the
    # two installers so the flags are already seeded when the first mount reads them.
    from moe_calculator.bridge import mod_settings
    from moe_calculator.bridge import gameface_bridge, battle_bridge

    mod_settings.register()
    mod_settings.add_change_listener(gameface_bridge.apply_settings)
    mod_settings.add_change_listener(battle_bridge.apply_settings)
    LOG_DEBUG("[%s] settings registered (garage=%s, battle=%s, battle_alt=%s)"
              % (MOD_NAME, mod_settings.garage_enabled(), mod_settings.battle_enabled(),
                 mod_settings.battle_alt_key_enabled()))


try:
    _install_settings()
except Exception:
    LOG_CURRENT_EXCEPTION()

try:
    _install()
except Exception:
    LOG_CURRENT_EXCEPTION()

try:
    _install_battle()
except Exception:
    LOG_CURRENT_EXCEPTION()
