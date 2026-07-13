# -*- coding: utf-8 -*-
"""In-battle Alt-key detection for the "Battle Widget on Alt Key" peek mode.

Event-driven ON PURPOSE. A self-rescheduling ``BigWorld.callback`` poll STALLS ~2s into a
battle (see ``TASKS/shipped/mod-positioning-handoff.md``), so we do NOT poll. Instead we wrap
``AvatarInputHandler.handleKeyEvent`` -- WG's central battle key dispatcher, which fires on
every key down/up transition -- and, at each event, sample whether either Alt key is currently
held via ``BigWorld.isKeyDown``. ``isKeyDown`` read AT an input event (not on a timer) avoids
the stall entirely.

The wrapper ALWAYS runs WG's original handler first and returns its result -- it only OBSERVES
input, never consumes or alters it. Ownership: the original is stashed on the wrapper.

Game symbols (``BigWorld``, ``Keys``, ``AvatarInputHandler``) are lazy-imported inside the
functions so this module still imports under the Python 3 test interpreter with the game closed.
"""
from moe_calculator._compat import LOG_CURRENT_EXCEPTION, LOG_DEBUG

# One-time patch guard, last-seen combined Alt state, and the transition callback.
_installed = False
_alt_held = False
_on_change = None


def _alt_down_now():
    """True iff either the left or right Alt key is currently down (engine read)."""
    import BigWorld
    from Keys import KEY_LALT, KEY_RALT
    return bool(BigWorld.isKeyDown(KEY_LALT) or BigWorld.isKeyDown(KEY_RALT))


def _update_alt_state():
    """Sample Alt and fire the callback only when the combined state flips."""
    global _alt_held
    held = _alt_down_now()
    if held != _alt_held:
        _alt_held = held
        LOG_DEBUG("[moe-battle] Alt %s" % ("down" if held else "up"))
        if _on_change is not None:
            _on_change(held)


def install_alt_key_listener(on_change):
    """Monkey-patch ``AvatarInputHandler.handleKeyEvent`` (once) to report Alt transitions.

    ``on_change(held)`` is invoked (guarded) only when the combined Alt-held state changes.
    Idempotent and self-healing: a repeat call just refreshes the callback; the patch itself is
    applied a single time. Returns True once the hook is in place, False if the class isn't
    importable yet (a later call retries)."""
    global _installed, _on_change
    _on_change = on_change
    if _installed:
        return True
    try:
        from AvatarInputHandler import AvatarInputHandler
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return False

    original = AvatarInputHandler.handleKeyEvent
    # Never double-wrap (e.g. across a dev reload): a prior wrapper carries the real original.
    original = getattr(original, "_moe_alt_original", original)

    def _patched(self, *args, **kwargs):
        # Run WG's handler first and preserve its return (was-the-event-consumed?) value.
        result = original(self, *args, **kwargs)
        try:
            _update_alt_state()
        except Exception:
            LOG_CURRENT_EXCEPTION()
        return result

    _patched._moe_alt_original = original  # ownership marker
    AvatarInputHandler.handleKeyEvent = _patched
    _installed = True
    LOG_DEBUG("[moe-battle] Alt-key listener installed on AvatarInputHandler.handleKeyEvent")
    return True


def alt_held():
    """The combined Alt-held state as last observed by the hook (False before the first event)."""
    return _alt_held
