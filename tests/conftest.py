import os
import sys
import types

# Make the in-game package importable in tests without the game engine.
_CLIENT = os.path.join(os.path.dirname(__file__), "..", "src", "res", "scripts", "client")
sys.path.insert(0, os.path.abspath(_CLIENT))


def _stub_module(name, **attrs):
    """Install a bare stub module into sys.modules (once) so an adapter that imports a game
    symbol AT MODULE TOP can be imported under pytest. These only satisfy the import; every
    test drives real behavior by monkeypatching the adapter's own functions, never these.
    Mirrors the fake-game-symbol technique in test_i18n.py, hoisted here so the adapter
    modules import regardless of test collection order."""
    mod = sys.modules.get(name)
    if mod is None:
        mod = types.ModuleType(name)
        sys.modules[name] = mod
    for key, value in attrs.items():
        if not hasattr(mod, key):
            setattr(mod, key, value)
    return mod


# engine_adapter: `from CurrentVehicle import g_currentVehicle`
_stub_module("CurrentVehicle", g_currentVehicle=object())
# battle_adapter: `import BigWorld` (callback/player are only touched via monkeypatched paths)
_stub_module("BigWorld", callback=lambda *a, **k: None, player=lambda: None)
