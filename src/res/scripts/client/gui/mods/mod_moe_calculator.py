# -*- coding: utf-8 -*-
"""14th_ua's MoE Calculator — entry point.

Mount path: WoT 2.x loads only packaged .wotmod. OpenWG's JS injector only acts on
hangar SUB-views, so we patch a hangar sub-view presenter
(HangarVehicleParamsPresenter) to inject our widget assets and expose our data
model; the widget JS renders from that model. We recompute on vehicle change.

OpenWG Gameface is a hard dependency. Python 2.7 (BigWorld) runtime.

See the wotmod-architecture harness skill for the layered domain/adapter/bridge
design this scaffold demonstrates, and wotmod-build-deploy for packaging.
"""
from debug_utils import LOG_NOTE, LOG_CURRENT_EXCEPTION

MOD_NAME = "14th_ua's MoE Calculator"
MOD_VERSION = "0.1.0"


def _install():
    import openwg_gameface  # noqa: F401  (hard dependency; raises if absent)
    from gui.impl.lobby.hangar.presenters.hangar_vehicle_params_presenter import (
        HangarVehicleParamsPresenter as P)
    from moe_calculator.bridge import gameface_bridge as bridge

    if getattr(P, "_moe_calculator_patched", False):
        return

    _orig_onLoading = P._onLoading

    def _onLoading(self, *args, **kwargs):
        _orig_onLoading(self, *args, **kwargs)
        try:
            # Re-arm on every mount: the battle-exit hangar teardown rebuilds the
            # onChanged delegate list with WG's own presenters but drops ours, so a
            # once-only subscription stops firing after the first battle. The installer
            # is idempotent (membership-checked), so re-arming every mount is safe and
            # also keeps things working across hot reloads.
            bridge.install_all_listeners()
            rvm = bridge.attach(self.getViewModel())
            bridge.push(rvm, host_vm=self.getViewModel())
        except Exception:
            LOG_CURRENT_EXCEPTION()

    P._onLoading = _onLoading
    P._moe_calculator_patched = True

    # Arm once now (for the install that happens while already in the hangar);
    # _onLoading re-arms on every subsequent mount.
    bridge.install_all_listeners()
    LOG_NOTE("[%s] v%s installed (sub-view inject + data)" % (MOD_NAME, MOD_VERSION))


try:
    _install()
except Exception:
    LOG_CURRENT_EXCEPTION()
