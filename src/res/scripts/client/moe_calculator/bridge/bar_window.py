# -*- coding: utf-8 -*-
"""Host a centre-screen transient bar as its OWN OpenWG-registered Gameface WINDOW over the
battle HUD. ONE implementation, instantiated once per bar (bridge/progress_view.py,
bridge/efficiency_view.py).

The two bars -- Moving Average and Damage Efficiency -- are radio ALTERNATIVES: battle_bridge opens
exactly one of them, which is the only reason both stylesheets can own #moe-bar-root and the .mp-*
prefix. They differ in FOUR things and nothing else: the layout view name, the ViewModel, the anchor
constants and the log tag. So each is a BarHost(...) rather than a hand-clone; what is emphatically
NOT shared is the per-bar state, because two hosts must be able to be open at once (a live radio
switch mid-battle opens one before the other closes):

  * ONE ``_active`` PER HOST, not per module. A module-level singleton is exactly what forced the
    clone this replaces -- apply_position / _place / active_view all hard-referenced it, so one
    module could not host two windows. Here it is instance state.
  * ONE LAYOUT PER HOST. Reusing another view's resId resolves the WRONG layout and opens a second
    copy of THAT view. Each layout is declared once in res/gui/gen_resources/
    com.14th_ua.moe_calculator.json as R.mods.moe_calculator.views.<name> (WG-native resources,
    client 2.4.1+) and resolved per open by layout_id() below.

Everything WHY-shaped about the hosting model lives in battle_view.py's docstrings (why a
registered window and not a garage-style inject; why WindowLayer.WINDOW and not OVERLAY; why NOT
WINDOW_FULLSCREEN -- a full-screen Coherent surface steals the whole-screen mouse hit-test whenever
the cursor is raised, and pointer-events:none does NOT make the window rectangle click-through).
Read that first. The difference here is placement: a bar is placed off whichever ANCHOR the
Alignment setting resolves to -- Fixed (the shipped default) picks one of the two INTERNALLY, by
Orientation: centred horizontally and proportionally down the screen when Horizontal (the old
"Damage Log" anchor), to the left of the minimap when Vertical (the old "Minimap" anchor) -- with
the stored X/Y stepper pair composed on top of either as an anchor-relative offset
(domain.anchor_offset) -- or, under Free,
AT the stored pair itself, read as an ANCHOR POINT (bottom-centre horizontal / bottom-right
vertical, domain.free_top_left) rather than a top-left, so a Default<->Large size flip re-anchors
the bar instead of growing it off to one side (TASKS/in-battle-bar-layout-auto-set-redesign.md
Trap 3 Fix B). A Ctrl+DRAG writes that same pair (converted into the anchor-point frame -- see
BarHost.drag); the gesture no longer FLIPS Alignment to Free -- it now only ever RUNS while
Alignment is ALREADY Free, since MSA has no way to assign a peer control's value, so the lock is
the gesture refusing to start at all under Fixed (see BarHost.drag's own docstring). The exact
pair (0, 0) under Free is its own AUTO sentinel meaning "not yet materialised"
(BarHost._materialise), not the screen origin -- see _resolve.

THE DRAG IS ENTIRELY PYTHON'S NOW, AND ABSOLUTE. adapter/battle_input samples Ctrl + the left mouse
button off WG's own input dispatchers plus its g_mouseEventHandlers registry, and reports the gesture
here as drag("start"/"move"/"end", cursor); each movement re-places the window from the LIVE CURSOR
POSITION (domain.cursor_top_left), ONE handler and ONE stored pair for both bars. It replaces a JS
delta protocol that failed structurally three times over: the reported delta was device px while
window.move takes logical px (a gain factor we kept getting wrong), and -- because each bar is its OWN
window whose surface rect IS the mouse hit rect -- any gain error or round-trip lag let the cursor
leave that bar-sized rect, at which point the events stopped, resumed, and the bar lurched. An
absolute mapping has no factor and needs no mouse input in the document at all, so the hit rect now
stays permanently collapsed (see MoEBarTransient.js) and the HUD-input-stealing hazard is retired
with it. Its GAIN IS EXACTLY 1, which takes one more term than a far-sentinel clamp can see -- the
window's own size; see _space, and do NOT scale a cursor fraction onto _extent's result.

THE SURFACE IS SIZED FROM THE JS, NOT FROM HERE. There is no Python-side size setter anywhere
(native PyObjectWindow has no resize / no autoSize; ``windowSize`` writes land silently in
``__dict__`` and do nothing), and no gen_resources field for size -- a Layout's parameters accept
only entrance / impl. What actually sizes a Gameface view is the view PUSHING its own size
to C++ via the ``viewEnv`` global: ``viewEnv.resizeViewRem(w, h)`` (rem == logical px). A view that
never calls it gets the engine's "default view size" fallback after a ``Size calculation timeout``
-- a flat 256x256 logical px, which is what clipped these bars.
PUSHING THE SIZE IS NOT SUFFICIENT ON ITS OWN, because the timeout's fallback runs LAST and WINS:
live-measured, the resize landed at 04.8s and the deadline's "Set the default view size" action at
06.2s put the surface back to 256x256. Static in-flow content does NOT satisfy the engine's
measurement either -- that premise was tested and disproven -- so the JS re-asserts the size once
after the deadline (SURFACE_REASSERT_MS in MoEBarTransient.js). Each resize round-trips back here as
Window._cResized -> onSizeChanged, which is exactly why _onReady SUBSCRIBES to it rather than
placing once: the placement has to be re-read against the REAL extent.

PC-only (needs the live client); not imported under pytest without stubs. Python 2.7 runtime.
"""
from moe_calculator._compat import LOG_CURRENT_EXCEPTION, LOG_DEBUG, LOG_PROD

from frameworks.wulf import ViewSettings, ViewFlags, WindowFlags, WindowLayer, PositionAnchor
from gui.impl.pub import ViewImpl, WindowImpl

from moe_calculator.bridge import mod_settings
from moe_calculator.domain.constants import (MINIMAP_SIZES, MM_GAP,
                                             MM_TICK_OVERHANG, MM_TICK_OVERHANG_LARGE,
                                             MM_TRACK_Y, MM_TRACK_Y_LARGE)
from moe_calculator.domain.positioning import (anchor_centred_reduced, anchor_minimap,
                                               anchor_offset, cursor_in_rect, cursor_logical,
                                               cursor_top_left, free_anchor_point, free_top_left)

# Our R.mods subtree -- keep in lockstep with res/gui/gen_resources/com.14th_ua.moe_calculator.json.
_RES_NODE = "moe_calculator"
_unresolved_logged = set()


def layout_id(view_name):
    """The layoutID of R.mods.moe_calculator.views.<view_name>, or -1 when it does not resolve
    (gen_resources JSON missing/invalid, pre-2.4.1 client). Fail-soft: the caller skips the window,
    and the miss is logged ONCE per view -- open_window is re-driven every battle tick."""
    try:
        from gui.impl.gen import R
        res_id = R.mods.dyn(_RES_NODE).dyn("views").dyn(view_name)()
    except Exception:
        res_id = -1
    if res_id is None or res_id < 0:
        if view_name not in _unresolved_logged:
            _unresolved_logged.add(view_name)
            LOG_PROD("[moe] layout R.mods.%s.views.%s unresolved -- window disabled"
                     % (_RES_NODE, view_name))
        return -1
    return res_id


# A large sentinel offset used to clamp the window to the far corner (LEFT/TOP anchor) so we can
# read back the movable extent (= logical space - windowSize) and place proportionally.
_FAR = 1 << 20

# _place()'s readback tolerance, in logical px -- how close window.position must land to the
# intended (x, y), AFTER EVERY move(), to count as "actually applied". A no-op move on an
# unrealized surface leaves the window sitting at _extent's far-sentinel corner (the minimap's own
# bottom-right corner), hundreds of px away, so a few px of slack cannot mask that; a realized
# in-bounds move lands dead-on (the engine only clamps an out-of-bounds one). This readback is now
# the UNIVERSAL realization test (see _place's own docstring) -- it no longer runs "only while
# unrealized" against a guessed fallback surface size, because that guess was itself the bug (an
# ultrawide client's engine-forced default view size is NOT the same (256, 256) this was measured
# against on the dev machine, which let an unrealized window slip through as "realized").
# ponytail: a fixed px count, not a fraction of screen/anchor geometry -- anchor_minimap's points
# sit well inside the screen, so a legitimate unrealized-window placement this close to the far
# corner is not a real case; if one ever is, it does NOT self-heal on the very next refresh()
# tick -- it stays pending until the surface actually REALIZES (onSizeChanged / ensure_placed's
# retry), same as the no-op bug this guards against.
_PLACE_TOLERANCE_PX = 3

# Engine's un-resized default view size; used only by tests to model an unrealized surface.
_FALLBACK_SURFACE_SIZE = (256, 256)

# The engine can NATIVELY destroy one of our windows out from under us. A WindowFlags.TOOLTIP
# window (see _BarWindow) is disposable to Wulf: clicking an alternative-equipment slot on the
# battle countdown makes the engine destroy the bar's window AND its view -- windowStatus and
# viewStatus go DESTROYING/DESTROYED and View._cFini nulls the viewModel -- with NO Python call to
# destroy(). Nothing re-opened it before this, because open_window's `_active is not None` guard has
# no liveness check: the dead (window, view) tuple stays non-None, active_view() keeps handing it
# back, and every push then no-ops on its None viewModel, so the bar silently stops updating for the
# rest of the battle. These are the frameworks/wulf DESTROYING(4)/DESTROYED(5) status values
# (gui_constants.WindowStatus, view.View); read numerically so this stays engine-free / unit-testable.
_DEAD_STATUS = (4, 5)   # WindowStatus/View DESTROYING, DESTROYED


def _clamp_to_extent(x, y, max_x, max_y):
    """Clamp a resolved top-left into the window's movable extent [0, max] per axis so EVERY target
    is reachable, then the readback in _place is a pure realization test.

    Without this, a pin stored off-screen (e.g. a Free/legacy y below the screen bottom) resolves to
    a target the engine silently clamps back on-screen, so ``applied != target`` and _place's
    realization gate (b24e0b4) REJECTS it forever -- has_placed() never flips and the bar hides for
    the whole battle, retrying the same unreachable target every tick. Clamping first makes an
    off-screen pin land on-screen and its readback match.

    NEVER emits the exact pair (0, 0): that is Free's AUTO sentinel (see
    unclamping-drag-is-constrained-by-the-auto-placement-sentinel), and the clamped value flows on
    into _materialise's write-back -- a negative / off-top-left pin clamping to (0, 0) is floored one
    px on x so it can never be misread as 'not yet materialised'. Pure (no engine call): unit-tested."""
    cx = max(0, min(int(x), int(max_x)))
    cy = max(0, min(int(y), int(max_y)))
    if (cx, cy) == (0, 0):
        cx = 1
    return cx, cy


def _cursor_position():
    """The mouse cursor's live position as the engine reports it, or None.

    THE FALLBACK, not the primary read: a mouse move reported through gui.g_mouseEventHandlers
    carries its own ``event.cursorPosition``, which drag() prefers. This is what the key /
    AvatarInputHandler sampling points -- which have no event to read -- fall back to.

    ``GUI.mcursor().position`` is battle-usable (precedent: gui/Scaleform/daapi/view/battle/shared/
    radial_menu.py's _showInternal) and is a Vector2. ITS UNITS ARE NOT SETTLED in the decompiled
    client -- one call site feeds it to a clip-space ray cast, another pairs a cursor pair with
    GUI.screenResolution() -- which is why the mapping that consumes it (domain.cursor_top_left)
    decides the convention at runtime instead of assuming one.

    Lazily imported and fail-soft to None ("leave the bar where it is"), so this module still
    imports under pytest with the game closed."""
    try:
        import GUI
        return GUI.mcursor().position
    except Exception:
        return None


def _minimap_size_index():
    """The player's minimap size as an index into constants.MINIMAP_SIZES, already clamped.

    Lazily imported and fail-soft for the same reason _cursor_position is: adapter/battle_adapter
    imports BigWorld at module scope, and this module has to stay importable with the game closed.
    The engine read, its clamp and its own fail-soft default all live in the adapter (that is the
    layer allowed to touch settingsCore) -- this wrapper only keeps the import off the module top,
    and falls back to the SAME largest-index default when even the import fails (see the adapter
    for why the largest, not the middle)."""
    try:
        from moe_calculator.adapter import battle_adapter
        return battle_adapter.read_minimap_size_index()
    except Exception:
        return len(MINIMAP_SIZES) - 1


def _effective_variant():
    """The variant actually gating the currently-open bar host: the played vehicle's stored
    override if it has one, else the global default -- mirrors battle_bridge._window_gates so
    _materialise's own-variant check (below) doesn't skip the host an override actually opened.

    Returns None when the played vehicle's descr can't be read THIS frame (unreadable descr ->
    int_cd 0, or a read exception). None means "can't resolve" -- NOT the global default: an
    unreadable frame must never flip _materialise's own-variant gate against a host that a
    per-vehicle OVERRIDE legitimately opened (that would skip a fresh Free AUTO write for a frame,
    leaving the steppers reading 0/0 longer). _materialise treats None as "proceed" (below).

    Lazily imported for the same reason _minimap_size_index is (battle_adapter touches BigWorld
    at module scope)."""
    default = mod_settings.progress_bar_variant()
    try:
        from moe_calculator.adapter import battle_adapter, variant_overrides
        int_cd = battle_adapter._player_vehicle_int_cd(battle_adapter._player_vehicle_descr())
        if not int_cd:
            return None
        return variant_overrides.effective(int_cd, default)
    except Exception:
        return None


def _screen_resolution():
    """(width, height) in device px, or None. Only needed for the PIXEL-space cursor convention --
    a clip-space read normalises itself."""
    try:
        import GUI
        return GUI.screenResolution()
    except Exception:
        return None


class _BarView(ViewImpl):
    """The registered Gameface view; its root ViewModel IS the bar's own model (the JS reads it
    with a bare ModelObserver(), no nested submodel and no unwrap).

    layoutID and the model arrive per INSTANCE, so one class serves every bar -- see the module
    docstring on why each host needs its own layout."""

    def __init__(self, layout_id, view_model):
        super(_BarView, self).__init__(ViewSettings(layout_id, ViewFlags.VIEW, view_model))

    @property
    def viewModel(self):
        return super(_BarView, self).getViewModel()

    def _onLoading(self, *args, **kwargs):
        super(_BarView, self)._onLoading(*args, **kwargs)
        # Push once the view (and its bound VM) is live so the bar has real values in hand for its
        # first transient. Lazy import avoids a bar_window <-> battle_bridge cycle.
        try:
            from moe_calculator.bridge import battle_bridge
            battle_bridge.refresh()
        except Exception:
            LOG_CURRENT_EXCEPTION()


class _BarWindow(WindowImpl):
    """Content-sized window hosting a _BarView over the HUD. Same layer as MoEBattleWindow, for
    the same reasons (read its docstring): NOT full-screen (a full-screen Coherent surface steals
    the whole-screen mouse hit-test whenever the cursor is raised), layer WINDOW (7) so the modal
    in-battle menu at TOP_WINDOW (10) keeps its input, shown without focus.

    EXPERIMENTAL, needs live confirmation: typeFlag is WindowFlags.TOOLTIP (48 | WINDOW), not
    WindowFlags.WINDOW, to fix a pre-existing bug where Ctrl-clicking the bar (a gesture that
    already needs zero hit-testing -- see the module docstring) steals autofocus from the
    Scaleform battle chat input even though pushHitArea collapses the JS hit rect to nothing; the
    native Wulf window rect still captures the click regardless. WG's own non-interactive
    overlays (gui/impl/pub/tooltip_window.py's ToolTipWindow, gui/impl/backport/backport_tooltip.py's
    BackportTooltipWindow) use WindowFlags.TOOLTIP for exactly "never grabs input". WindowFlags has
    no click-through/non-focusable bit of its own (frameworks/wulf/gui_constants.py's WindowFlags
    is exhaustive), so TOOLTIP -- documented as never grabbing input -- is the closest lever.
    Checked before shipping this: `layer` is a separate WindowSettings field (independent of
    wndFlags at the Python API level), so it is UNCHANGED here; WG's own
    gui/Scaleform/daapi/view/lobby/hangar/hangar.py explicitly special-cases a TOOLTIP-typeFlag
    window AT WindowLayer.WINDOW (excluding it from `_HELP_LAYOUT_RESTRICTED_LAYERS` gating),
    which is direct precedent that this exact (layer=WINDOW, typeFlag=TOOLTIP) combination is one
    the engine already expects and handles. No Python-visible auto-dismiss/timeout/focus-manager
    logic keys off typeFlag anywhere in the decompiled client; that arbitration is native C++ and
    has no Python-visible seam, so this cannot be proven headless -- it needs an in-client Ctrl+
    click + Enter-to-chat check under both alignments before being treated as done. If it
    regresses (bar disappears, renders under the HUD, or the reposition gesture misbehaves),
    revert to WindowFlags.WINDOW here first.

    THE SAME FACT -- pushHitArea's JS-side collapse does NOT stop the native Wulf window rect from
    capturing a click -- is also why a vertical bar's SURFACE (not just its drawn backdrop) blocked
    clicks on the minimap's first column: the surface is sized in MoEBarTransient.js (viewW), and
    the JS hit-area collapse never shrinks that rect, only pads it to (near-)zero AROUND its own
    size -- a bigger surface just gets a bigger, still-fully-collapsed pad. So the surface itself
    has to clear the minimap on its own; shrinking only the drawn backdrop (.mpv-backdrop /
    .mev-backdrop, V_BOX_W_REM) leaves the invisible surface exactly where it was. See
    domain.positioning.anchor_minimap and each bar's own V_PAD_XR_REM note (MoEProgress.js /
    MoEEfficiency.js) for the fix."""

    def __init__(self, content, place, host):
        super(_BarWindow, self).__init__(
            WindowFlags.TOOLTIP, content=content, layer=WindowLayer.WINDOW)
        self._place = place
        self._host = host

    def _onReady(self):
        self.show(focus=False)
        # RE-ARM EVERY MOUNT (dropped again in close_window -> detach): _place reads the movable
        # extent by far-sentinel clamp, and at _onReady the surface is still the engine's 256x256
        # default-size fallback -- the JS pushes the real size a moment later. Wulf fires
        # onSizeChanged per resize, so re-place off that rather than trusting this one shot. Plain
        # `+=` is the WG idiom for a Wulf window Event (see Window.__attachToDecorator).
        self.onSizeChanged += self._on_size_changed
        self._place(self)

    def _on_size_changed(self, _unique_id, _width, _height):
        """The JS resized our surface -> the movable extent changed -> re-place.

        ALSO flips the host's `_sized` latch: THIS is the first point a real (post-256x256
        fallback) surface size exists, which is exactly what BarHost._materialise gates on --
        materialising against the fallback size would bake a wrong Free anchor point FOREVER (see
        TASKS/in-battle-bar-layout-auto-set-redesign.md Trap 2).

        ALSO pushes on a has_placed() False->True TRANSITION (cold-start fix): the only VM
        `visible` writer is battle_bridge.refresh()/push_progress/push_efficiency, and NOTHING
        else on this path calls it -- a late-but-successful _place() here used to flip
        has_placed() True with no push to follow, so the bar stayed invisible until an unrelated
        refresh (e.g. Ctrl) happened to fire. Captured BEFORE _place() (which is what can flip it)
        and compared AFTER, so a routine Default<->Large / minimap resize that leaves an
        already-True has_placed() alone does NOT push every time -- only the one-time cold
        transition does. Lazy import avoids a bar_window <-> battle_bridge cycle (same pattern as
        _BarView._onLoading above).

        CANNOT RE-ENTER: window.move() (inside _place) is a position change, not a resize, so it
        never re-fires onSizeChanged; battle_bridge.refresh() -> ensure_placed() finds
        has_placed() already True (we just set it) and takes its no-op branch, so no new _place()
        -- let alone a new resize -- is generated from inside this handler."""
        self._host._sized = True
        was_placed = self._host.has_placed()
        self._place(self)
        if not was_placed and self._host.has_placed():
            try:
                from moe_calculator.bridge import battle_bridge
                battle_bridge.refresh()
            except Exception:
                LOG_CURRENT_EXCEPTION()

    def detach(self):
        """Drop the onSizeChanged subscription. Called from close_window BEFORE destroy so the
        listener never outlives a battle. Fail-soft -- teardown must not raise."""
        try:
            self.onSizeChanged -= self._on_size_changed
        except Exception:
            LOG_CURRENT_EXCEPTION()


class BarHost(object):
    """One centre-screen bar window: its layout, its ViewModel and its own open/closed singleton.

    ``item_id`` is the view name declared as R.mods.moe_calculator.views.<item_id> in
    res/gui/gen_resources/com.14th_ua.moe_calculator.json -- keep in lockstep, and DISTINCT per host.
    ``vm_factory`` is called per open to build a fresh root ViewModel. ``y_frac`` / ``x_off`` /
    ``y_shift`` are the bar's HORIZONTAL-orientation anchor constants (domain/constants), and
    ``tag`` prefixes its log lines. ``y_shift_large`` is the same intra-surface compensation for the
    LARGE size mode -- a bigger surface shifts its composition further down inside itself (see the
    constants' derivations) -- and BOTH shifts are only ONE of the values _resolve picks LATE rather
    than freezing here: the size, orientation and alignment settings are all read per placement,
    because these arguments are bound at MODULE IMPORT and a setting changed after that (or between
    battles) would otherwise keep using whichever value was current at first load, forever.
    ``mm_track_x`` / ``mm_track_x_large`` are the MINIMAP alignment's own per-bar term -- where this
    bar's VERTICAL track sits inside its own surface on the cross axis (constants
    .*_MM_TRACK_X(_LARGE)) -- per bar for the same reason the two shifts are, and read just as late.
    Its Y counterpart is SHARED by both bars (MM_TRACK_Y) and so needs no argument.
    ``mm_gap_bottom`` is that alignment's OTHER per-bar term: the clearance this bar's VERTICAL track
    keeps off the screen's bottom edge (constants.*_MM_GAP_BOTTOM, 30 vs 28 -- each tuner's own tuned
    value). It was a single shared constant while both bars' surfaces buried the tuned gaps under 90
    logical px of unreachable slack; the front-end change that shortened both vertical surfaces to
    their own tuned gap is what made the two numbers differ ON SCREEN and so worth threading. It has
    no Large twin, on purpose -- see the constants' note.
    ``mm_gap`` / ``mm_gap_large`` are the MINIMAP alignment's per-bar, per-size X clearance to
    spend (constants.PROGRESS_/EFFICIENCY_MM_GAP(_LARGE), replacing the shared constants.MM_GAP
    for actual placement -- see that constant's own derivation for why a single shared knob
    cannot serve both bars, and why even a per-bar knob still has to split by size: the two sizes'
    margins are different affine functions of the gap, so one shared value is capped by whichever
    size is tighter). Both default to constants.MM_GAP, so a caller that never passes either
    (every non-production BarHost in the test suite) keeps the ORIGINAL shared behaviour unchanged
    at both sizes.
    ``variant`` is this bar's own mod_settings.PROGRESS_VARIANT_* index (progress_view passes
    MOVING_AVERAGE, efficiency_view EFFICIENCY) -- BarHost._materialise's own-variant gate against
    it, since both hosts share ONE stored Free pair and a live variant flip mid-battle can briefly
    have both open (see the module docstring). Defaults to None, which never equals a real variant
    index, so a host built without one (e.g. a test fixture) simply never materialises.

    DELETED (v23, the Fixed-alignment redesign): ``x_shift_large`` and its rule-5 right-pin math
    (constants.PROGRESS_/EFFICIENCY_ANCHOR_X_SHIFT_LARGE, anchor_centred_reduced's ``x_shift``
    argument). It existed solely for a VERTICAL bar resolving to the Damage Log anchor under
    Large, and that combination is not merely rare now, it is UNREACHABLE: Alignment only ever
    stores Fixed or Free (clamp_variant's ceiling is PROGRESS_ALIGN_FREE == 1), and Fixed always
    picks Minimap when vertical (see _resolve) -- there is no stored value or UI path left that
    can select Damage Log while vertical.
    """

    def __init__(self, item_id, vm_factory, y_frac, x_off, y_shift, y_shift_large,
                 mm_track_x, mm_track_x_large, mm_gap_bottom, tag,
                 mm_gap=MM_GAP, mm_gap_large=MM_GAP, variant=None):
        self.item_id = item_id
        self._vm_factory = vm_factory
        self._y_frac = y_frac
        self._x_off = x_off
        self._y_shift = y_shift
        self._y_shift_large = y_shift_large
        self._mm_track_x = mm_track_x
        self._mm_track_x_large = mm_track_x_large
        self._mm_gap_bottom = mm_gap_bottom
        self._mm_gap = mm_gap
        self._mm_gap_large = mm_gap_large
        self._tag = tag
        self._variant = variant
        self._layout_id = lambda: layout_id(item_id)   # -1 when unresolved; see layout_id
        self._active = None                         # (window, view) while open
        self._extent_cache = None                   # memoized movable extent; see _extent
        # The last position a real window.move() applied WITHOUT raising -- ONE per host, same as
        # `_active`, because a host only ever drives one open window at a time (see the class
        # docstring). _place's fail-safe restores here instead of a guessed corner; see _place.
        # It ALSO IS "has this host ever placed successfully" -- see has_placed(): set only on
        # success, never cleared, so its mere presence is the whole signal.
        self._last_good = None
        # True once THIS window's surface has been resized past the engine's 256x256 size-timeout
        # fallback at least once (see _BarWindow._on_size_changed) -- the materialise-on-mount
        # gate _materialise needs, reset back to False by open_window on every fresh window.
        self._sized = False
        # Anti-spam latch for _place()'s LOG_PROD rejection line: ensure_placed() retries _place()
        # every battle_bridge.refresh() tick while unrealized (bounded by the ~2s realization
        # race, not per-frame, but still repeats), so this fires the diagnostic once per mount
        # rather than once per retry. Reset alongside `_sized` on every fresh open_window() mount.
        self._reject_logged = False
        # Sibling anti-spam latch for _place()'s LOG_PROD SUCCESS line -- the placement-confirmed
        # counterpart to `_reject_logged` above, so a remote python.log can tell "never placed"
        # apart from "placed at X" (see that line's own comment). Also once per mount, reset
        # alongside `_sized`/`_reject_logged` in open_window().
        self._place_logged = False
        # THE LIVE GESTURE's only two pieces of state (both None while none is in flight):
        # `_grab` is the offset between the window's top-left and the cursor's mapped position at
        # gesture start, carried for the whole gesture so the bar keeps the point it was grabbed by;
        # `_drag_pos` is the Free ANCHOR POINT (not a top-left, see free_anchor_point) equivalent
        # to the last position actually applied, i.e. what the mouse-up persists -- and None means
        # the gesture NEVER MOVED, which must persist nothing (see drag).
        # `_declined` latches a gesture this host does NOT own (it began outside our window rect),
        # so a foreign drag that later sweeps the cursor across us cannot be claimed mid-flight.
        self._grab = None
        self._drag_pos = None
        self._declined = False

    def _resolve(self, max_x, max_y, space_x, space_y):
        """This bar's top-left in logical GUI space: the base anchor the ALIGNMENT setting selects,
        with the stored X/Y stepper pair composed on top (domain.anchor_offset -- positive =
        right/down, uniformly, whichever alignment produced the base).

        `max_x, max_y` is the movable extent (space - surface) and `space_x, space_y` the FULL
        logical space; the surface size is their per-axis difference, which is why placing a bar
        needs no engine call the caller has not already made (see _space, and the drag's ownership
        gate, which recovers the surface the same way).

        THREE BRANCHES, same shape as before v23's Fixed-alignment redesign -- only WHERE the
        dispatch comes from changed. Alignment only ever STORES Fixed or Free now (clamp_variant's
        ceiling is PROGRESS_ALIGN_FREE == 1); Fixed resolves to one of the two INTERNAL anchor
        selectors (mod_settings.PROGRESS_ALIGN_DAMAGE_LOG / PROGRESS_ALIGN_MINIMAP -- see that
        module for why they survive) PURELY by Orientation -- Horizontal -> Damage Log,
        Vertical -> Minimap. Dispatch below branches on `vertical` DIRECTLY rather than on a
        locally-assigned "resolved anchor" value: PROGRESS_ALIGN_MINIMAP and PROGRESS_ALIGN_FREE
        are BOTH 1 (two different, never-crossed vocabularies -- stored alignment vs. internal
        anchor selector), so re-testing a variable that was just SET to PROGRESS_ALIGN_MINIMAP
        against `== PROGRESS_ALIGN_FREE` would wrongly match. Neither Damage Log nor Minimap is a
        separately stored choice any more, but the placement math for each is otherwise UNCHANGED:
          * Damage Log -- centred horizontally, PROPORTIONALLY down the viewport
            (anchor_centred_reduced). Its `y_shift` cancels the composition's intra-surface top
            offset (the JS shifts the whole bar into positive document coordinates); the fraction's
            extent-to-viewport conversion is computed by passing `space_y`, not baked into the
            constant -- see the constants' derivations and anchor_centred_reduced's docstring.
            Reachable only when Horizontal now (Fixed+Vertical always resolves to Minimap instead
            -- see mod_settings' SETTINGS_VERSION 22->23 comment for the `x_shift_large` rule-5
            right-pin machinery this retired: it existed ONLY for a vertical bar resolving to this
            anchor, which is no longer possible through the UI or a stored value at all).
          * Minimap -- to the LEFT of the minimap, whose measured logical width comes from the live
            settingsCore size INDEX (_minimap_size_index). The tick overhang term applies only to a
            VERTICAL bar: it is a CROSS-axis length, and only a vertical bar's cross axis is the x
            axis the minimap gap is measured on (a horizontal bar's ticks overhang in y instead) --
            reachable only when Vertical now, for the same reason as above. Both tuners measure the
            gaps to the visible TRACK box, so a VERTICAL bar passes where its track sits inside its
            surface (*_MM_TRACK_X / MM_TRACK_Y) as anchor_minimap's `edge_x` / `edge_y`.
          * Free -- the stored pair as an ANCHOR POINT (bottom-centre horizontal / bottom-right
            vertical -- domain.positioning.free_top_left, Trap 3 Fix B), converted into a top-left
            using THIS placement's own live surface size, which is what makes a Default<->Large
            size flip re-anchor the bar instead of growing it off to one side or the other --
            EXCEPT at the pair (0, 0), which under Free means AUTO and defers to whichever anchor
            this ORIENTATION defaults to (Horizontal -> Damage Log, Vertical -> Minimap, the SAME
            mapping computed below). This is Free's "not yet materialised" marker
            (BarHost._materialise): picking Alignment = Free leaves the pair at (0, 0) until the
            bar's next battle mount computes the real on-screen point (no surface exists in the
            settings panel to compute it from -- the bar must not jump), and a user who types 0 / 0
            into the steppers gets AUTO rather than the screen origin, a deliberately accepted lost
            capability. A NON-zero pair still carrying the PRE-v22 frame (mod_settings.
            progress_bar_pos_frame() == POS_FRAME_LEGACY -- see the SETTINGS_VERSION 21->22
            comment) is honoured as the literal top-left it always was instead, until
            _materialise converts it the first time this bar mounts with a real surface.

        EVERY SETTING IS READ HERE, PER PLACEMENT, none in __init__ (which binds at module import):
        size, orientation and alignment can all change after load. Size in particular has to be
        read here because the JS pushes the LARGE surface on its post-deadline re-assert, which
        round-trips back as onSizeChanged -> _place -- this read is what makes the two agree."""
        large = mod_settings.progress_bar_size() == mod_settings.PROGRESS_SIZE_LARGE
        vertical = (mod_settings.progress_bar_orientation()
                    == mod_settings.PROGRESS_ORIENT_VERTICAL)
        alignment = mod_settings.progress_bar_alignment()
        off_x, off_y = mod_settings.bar_pos_x(), mod_settings.bar_pos_y()
        # Free is real (not the (0, 0) AUTO marker, which falls through to Fixed's own mapping
        # below) only when BOTH the stored value is Free AND the pair is non-zero. Decided here,
        # against the ORIGINAL stored value, and never re-tested against a locally-computed
        # internal anchor selector below: PROGRESS_ALIGN_MINIMAP and PROGRESS_ALIGN_FREE are BOTH
        # 1 (two different, never-confused vocabularies -- see mod_settings), so comparing a
        # freshly-assigned "internal anchor" variable back against PROGRESS_ALIGN_FREE would
        # wrongly match Minimap.
        is_free = (alignment == mod_settings.PROGRESS_ALIGN_FREE and (off_x, off_y) != (0, 0))
        if is_free:
            if mod_settings.progress_bar_pos_frame() == mod_settings.POS_FRAME_LEGACY:
                # A pre-v22 pair is still a literal top-left (Fix B has not converted it yet, see
                # BarHost._materialise) -- honour it verbatim, exactly as pre-v22 did.
                return anchor_offset((0, 0), off_x + self._x_off, off_y)
            surface = (space_x - max_x, space_y - max_y)
            return free_top_left((off_x, off_y), surface, vertical)
        # Fixed, or Free still at its own (0, 0) AUTO marker: resolve to the internal anchor
        # Fixed's own mapping selects -- Vertical -> Minimap, Horizontal -> Damage Log.
        if vertical:
            overhang = MM_TICK_OVERHANG_LARGE if large else MM_TICK_OVERHANG
            edge_x = self._mm_track_x_large if large else self._mm_track_x
            edge_y = MM_TRACK_Y_LARGE if large else MM_TRACK_Y
            gap = self._mm_gap_large if large else self._mm_gap
            base = anchor_minimap(space_x, space_y, edge_x, edge_y,
                                  MINIMAP_SIZES[_minimap_size_index()], gap,
                                  self._mm_gap_bottom, overhang)
        else:
            base = anchor_centred_reduced(max_x, max_y, space_y, self._y_frac,
                                          self._y_shift_large if large else self._y_shift)
        return anchor_offset(base, off_x + self._x_off, off_y)

    def _extent(self, window):
        """The window's movable extent (= logical space - surface), read by clamping it to the far
        corner with a LEFT/TOP anchor -- the self-calibration battle_view._place uses, and the whole
        reason neither this module nor the domain has to know the surface size.

        MEMOIZED, because the measurement is a WINDOW MOVE: a Ctrl+drag calls drag() per mouse
        movement and an un-cached read cost a second native move() -- to (1<<20, 1<<20) -- per
        pointer event, which is what made the bar visibly jump around the cursor. The extent is a pure function of
        the surface size and the logical space, so it cannot change mid-gesture; _place invalidates
        it for the three things that DO change it (first placement, onSizeChanged, interface
        scale)."""
        if self._extent_cache is None:
            window.move(_FAR, _FAR, xAnchor=PositionAnchor.LEFT, yAnchor=PositionAnchor.TOP)
            self._extent_cache = window.position
        return self._extent_cache

    def _space(self, window):
        """The FULL logical GUI space (width, height) the window is moved in = extent + surface size.

        THE DRAG'S GAIN IS EXACTLY 1 BECAUSE OF THIS, and only because of this. _extent recovers
        space - surface (all a far-sentinel clamp can see), so mapping the cursor's screen fraction
        onto it scales every movement by (space - surface) / space -- measured ~0.74 on x, i.e. "the
        bar moves slower than the cursor". The missing term is the window's OWN size, and Wulf hands
        it over directly: ``Window.size`` is ``self.proxy.windowSize``, the sibling of the
        ``windowPosition`` that ``.position`` reads, so it is in the SAME logical units as
        ``.position`` and ``move()`` by construction -- WG's own tooltip_positioner.py subtracts a
        ``window.size`` width straight from a coordinate it then feeds to ``window.move()``. No rem
        conversion, no interface-scale factor, nothing guessed.

        Read live rather than memoized: unlike _extent this is a plain property read, not a window
        move, so it costs nothing per pointer event. Fail-soft to the extent alone (Wulf itself
        returns (0.0, 0.0) for a window with no proxy, which cannot be moved either)."""
        max_x, max_y = self._extent(window)
        try:
            width, height = window.size
            return max_x + int(width), max_y + int(height)
        except Exception:
            return max_x, max_y

    def _place(self, window):
        """Place the window off whichever anchor the Alignment setting selects (see _resolve).
        Fail-soft: a positioning error must never blank the bar.

        THE CACHE INVALIDATION POINT for _extent, and the only one needed: every reason the extent
        can move -- the first placement, the JS's resize (onSizeChanged, i.e. a Default<->Large
        flip), an interface-scale change and a minimap resize (both apply_position) -- already
        routes through here. _space's own extent read is free, having been warmed one line above.

        A FAILURE HERE MUST NOT STRAND THE WINDOW ON THE FAR SENTINEL, NOR AT THE SCREEN ORIGIN.
        _extent() already moved the window to (_FAR, _FAR) before _space/_resolve ever run, and
        that sentinel corner IS the minimap's own corner (both anchor bottom-right) -- so any
        exception between that measuring move and the real window.move() below would otherwise
        leave the bar sitting on top of the minimap, looking exactly like a placement bug and
        logged only once, silently. (0, 0) is no better: the bar must appear ONLY near the
        minimap, never top-left. So the fallback is LAST-GOOD-POSITION restore instead: on
        failure, move back to the last position a `window.move()` here actually applied without
        raising (`_last_good`, updated below on every success) -- that needs no recompute, so it
        cannot re-raise the same fault, and it is by definition a real anchor this bar has already
        stood at (possibly one layout stale -- orientation/size/minimap-size may have changed
        since, but it is still near the minimap, and the next successful _place corrects it). Only
        when NO last-good position exists yet (the very first placement this host has ever
        attempted) is there nothing to restore to -- do nothing further: the VM `visible` flag
        defaults False and battle_bridge's push gates it on has_placed() (below), which stays
        False until a LATER _place succeeds, so nothing shows the corner meanwhile. The JS's
        post-deadline SURFACE_REASSERT_MS re-assert (see the module docstring) fires
        onSizeChanged again shortly after mount regardless of this failure, re-running _place.

        THE REAL MOVE BELOW CAN SILENTLY NO-OP: on a not-yet-realized window (still the engine's
        post-timeout default view size -- e.g. the very first _place, called from _onReady before
        the JS has ever pushed a real size) `window.move` raises nothing, it just does not apply,
        leaving the window parked wherever _extent()'s own far-sentinel move put it moments earlier
        -- the minimap's bottom-right corner, a whole screen away from any real anchor. A REALIZED
        in-bounds anchor lands dead-on instead (the engine only clamps an out-of-bounds move), so
        the position readback within `_PLACE_TOLERANCE_PX` is the realization proof: accepted only
        when the applied position matches the target. Rejected, `_last_good` is left exactly as it
        was (None on a first attempt), so has_placed() stays False and the bar stays hidden rather
        than parked on the minimap; it does not clear on the very next refresh() tick either -- it
        stays pending until the surface actually realizes (onSizeChanged flips `_sized`, and
        ensure_placed() -- driven from battle_bridge.refresh(), since no call site is guaranteed to
        run against a realized surface -- retries then). Trade-off: a legitimately off-screen
        Free/legacy pin that the engine clamps to the same corner is now rejected too, exactly like
        an unrealized no-op -- accepted, since neither this readback nor any other cheap signal can
        tell the two apart."""
        try:
            self._extent_cache = None
            max_x, max_y = self._extent(window)
            space_x, space_y = self._space(window)
            x, y = self._resolve(max_x, max_y, space_x, space_y)
            # Clamp into the movable extent BEFORE the move so an off-screen/edge pin lands on-screen
            # and its readback confirms placement, instead of the engine clamping it and _place
            # rejecting the mismatch forever (see _clamp_to_extent). A cold-start no-op still fails
            # the readback: the clamped on-screen target is far from an unrealized (0, 0) position.
            x, y = _clamp_to_extent(x, y, max_x, max_y)
            window.move(x, y, xAnchor=PositionAnchor.LEFT, yAnchor=PositionAnchor.TOP)
            applied_x, applied_y = window.position
            surface = (space_x - max_x, space_y - max_y)
            # Read for the diagnostics below only -- _resolve already read these itself; re-reading
            # here costs two cheap getter calls and lets both LOG_PROD lines echo the exact stored
            # alignment/offset a remote python.log needs to confirm the Fixed/Free shared-pair fix.
            alignment = mod_settings.progress_bar_alignment()
            off_x, off_y = mod_settings.bar_pos_x(), mod_settings.bar_pos_y()
            # Plain realization test: did the move actually apply? A realized in-bounds move lands
            # dead-on; an unrealized surface's move NO-OPS and the readback stays at the pre-move
            # position -- which the reported client reports as (0, 0) (python.log: applied=(0, 0)
            # surface=(0, 0)), NOT necessarily the far-sentinel corner (see memory
            # bar-host-place-must-gate-on-surface-realization). Because the target is now CLAMPED
            # into [0, max] it can never be (0, 0) for a real pin (the AUTO sentinel is floored to
            # (1, 0) in _clamp_to_extent) and is well inside the screen for any anchor, so a no-op
            # readback -- whether (0, 0) or the far corner -- is always further than
            # _PLACE_TOLERANCE_PX from it and this check rejects it, keeping the cold-start bar
            # hidden (no flash) until the surface realizes. Do NOT re-add a guard that assumes the
            # no-op value is always the far sentinel: it catches nothing here (the tolerance check
            # already rejects the real (0,0) no-op) and would permanently hide a legitimate realized
            # bottom-right pin, which clamps to (max_x, max_y) and lands there dead-on.
            if (abs(applied_x - x) <= _PLACE_TOLERANCE_PX
                    and abs(applied_y - y) <= _PLACE_TOLERANCE_PX):
                self._last_good = (x, y)
                if not self._place_logged:
                    # Once per mount (mirrors `_reject_logged`) -- lets the next remote python.log
                    # distinguish "never placed" from "placed at X", and confirms which alignment
                    # branch + stored offset actually produced it.
                    self._place_logged = True
                    LOG_PROD("%s placement confirmed: applied=(%d, %d) alignment=%d"
                              % (self._tag, x, y, alignment))
            elif not self._reject_logged:
                # Once per mount (see `_reject_logged`'s own comment) -- the SUCCESS path logs
                # nothing (every normal battle would spam), but a rejected placement leaves NO
                # trace at all today, which is exactly what makes this unconfirmable on a remote
                # client whose engine-forced fallback surface differs from anything reproduced here.
                self._reject_logged = True
                LOG_PROD("%s placement rejected: target=(%d, %d) applied=(%d, %d) surface=%s "
                          "alignment=%d off=(%d, %d)"
                          % (self._tag, x, y, applied_x, applied_y, surface,
                             alignment, off_x, off_y))
            self._materialise(x, y, surface[0], surface[1])
        except Exception:
            LOG_CURRENT_EXCEPTION()
            try:
                if self._last_good is not None:
                    lx, ly = self._last_good
                    window.move(lx, ly, xAnchor=PositionAnchor.LEFT, yAnchor=PositionAnchor.TOP)
            except Exception:
                LOG_CURRENT_EXCEPTION()

    def has_placed(self):
        """True once this host has completed at least one successful `_place` -- confirmed only
        when the position readback landed within `_PLACE_TOLERANCE_PX` of the target, not merely a
        `window.move()` that did not raise -- exactly `_last_good is not None` (see its own
        comment in __init__). battle_bridge's push_progress/push_efficiency AND this into the
        pushed `visible` so the FIRST-ever placement failure -- window still sitting at the
        far-sentinel/minimap corner, no `_last_good` yet -- can never flash on screen before the
        retry re-places it (the VM `visible` also defaults False, belt-and-braces). Transparent
        forever after the first success: `_last_good` is never cleared."""
        return self._last_good is not None

    def _materialise(self, x, y, surface_w, surface_h):
        """Write the just-resolved on-screen point back as Free's stored ANCHOR POINT, ONCE --
        the deferred half of two DIFFERENT stories that happen to end in the exact same action
        (see TASKS/in-battle-bar-layout-auto-set-redesign.md Trap 2 / Trap 3 Fix B / DECISION 1 /
        DECISION 2):

          * Free freshly picked, pair still (0, 0) -- `x, y` is this orientation's default anchor
            (_resolve's AUTO branch); convert it into the anchor-point frame and persist it, so the
            panel's steppers stop reading 0/0 the next time the user looks.
          * a pre-v22 store's Free pin is still a literal top-left (mod_settings.
            progress_bar_pos_frame() == POS_FRAME_LEGACY) -- `x, y` IS that pair, verbatim
            (_resolve's legacy branch); convert it into the SAME anchor-point frame and persist it,
            which is also what flips the marker to POS_FRAME_ANCHOR (see set_bar_position).

        Both cases reduce to "re-express the resolved top-left as an anchor point, using THIS
        placement's surface size, and persist it" -- domain.positioning.free_anchor_point is the
        exact inverse of the free_top_left conversion _resolve just applied (or would have, absent
        the legacy branch), so the bar's on-screen position never moves.

        THREE GATES, all load-bearing:
          * `_sized` -- the FIRST _place runs at _onReady against the engine's 256x256 size-timeout
            fallback; materialising against that bakes a wrong anchor point FOREVER (once the pair
            != (0, 0) and the frame is "anchor", neither branch above fires again).
          * the alignment/pair/frame are re-read FRESH here rather than reusing _resolve's locals,
            which were overwritten in place by the AUTO rewrite.
          * own-VARIANT only -- both hosts share ONE stored pair, and a live variant flip mid-battle
            can briefly have both open (see the class docstring)."""
        if not self._sized:
            return
        # Own-variant gate: skip only when the effective variant is KNOWN to be a different host
        # (the load-bearing case -- a stale host still open mid-flip must not materialise against
        # the shared pair). None means the descr was unreadable this frame -> proceed rather than
        # spuriously skip, or a per-vehicle-override host would miss a fresh Free AUTO write until
        # the next readable frame (see _effective_variant).
        effective = _effective_variant()
        if effective is not None and effective != self._variant:
            return
        if mod_settings.progress_bar_alignment() != mod_settings.PROGRESS_ALIGN_FREE:
            return
        pos = (mod_settings.bar_pos_x(), mod_settings.bar_pos_y())
        legacy = mod_settings.progress_bar_pos_frame() == mod_settings.POS_FRAME_LEGACY
        if pos != (0, 0) and not legacy:
            return   # already materialised, in the current frame -- nothing to do
        vertical = (mod_settings.progress_bar_orientation()
                    == mod_settings.PROGRESS_ORIENT_VERTICAL)
        ax, ay = free_anchor_point((x, y), (surface_w, surface_h), vertical)
        mod_settings.set_bar_position(ax, ay, persist=True)

    def drag(self, phase, cursor=None):
        """The Ctrl+left-button reposition gesture. `phase` is "start", "move" or "end", reported by
        adapter/battle_input off WG's own input dispatchers -- no JS, no delta, no wire protocol.
        `cursor` is the position the reporting mouse EVENT carried (gui.g_mouseEventHandlers hands us
        ``event.cursorPosition``), or None from the key/AvatarInputHandler paths that have no event --
        in which case we read GUI.mcursor() ourselves. Both go through the same unit-agnostic mapping.

        EVERY MOVE IS AN ABSOLUTE PLACEMENT. The live cursor is mapped into this window's logical GUI
        space (domain.cursor_top_left, which is UNCLAMPED -- a bar may be parked past any screen
        edge -- and owns the unit-agnostic
        read), then offset by the grab recorded at "start" so the bar keeps the point it was grabbed
        by instead of teleporting its corner under the cursor. Nothing accumulates, so nothing can
        drift, no gain factor exists to get wrong, and the gain is exactly 1 (see _space).

        A "move" ARRIVING FIRST IS TREATED AS THE START. battle_input's mouse wrap can latch the
        gesture on the first movement (with the cursor raised, the button press may never reach the
        key dispatcher), so the grab is recorded by whichever event gets here first.

        THE GESTURE IS OWNED PER HOST, decided ONCE. Ctrl+left-button is sampled globally off WG's
        input dispatchers and battle_bridge hands the event to BOTH bars unconditionally, so without
        a spatial gate a Ctrl+drag anywhere on screen dragged whichever bar was open -- including
        while the user was dragging another mod's UI. This host claims the gesture only if it BEGAN
        inside its own window rect (domain.cursor_in_rect against window.position + the surface size,
        which _space already recovers as space - extent -- no extra engine call). The decision is
        latched: a claimed gesture is never re-tested (that would drop the bar the moment the cursor
        left the rect) and a DECLINED one is never reconsidered (`_declined`, cleared on the next
        "start"/"end"), so a foreign drag sweeping the cursor over us cannot hijack the bar halfway.

        ONLY THE END PERSISTS, and only if the gesture actually MOVED. A live move writes the
        in-memory value alone -- that is all _resolve reads -- because a settings write per movement
        would mean an MSA updateModSettings + saveState at pointer rate. And a gesture that never
        moved writes nothing at all: `_drag_pos` stays None, so no set_bar_position runs, sparing a
        stray Ctrl+click on the bar a needless MSA write. (set_bar_position no longer touches
        Alignment at all -- see its own docstring -- so a no-move gesture has nothing further to
        protect against there; the gesture could not have started here in the first place unless
        Alignment was already Free.)

        EVERY MOVE ALSO CONVERTS INTO THE STORED FRAME (Trap 3 Fix B): `window.move()` still takes
        the TOP-LEFT `pos` computed above, but what gets handed to set_bar_position (both the live,
        unpersisted update and the eventual gesture-end persist) is that top-left re-expressed as
        the Free ANCHOR POINT (domain.positioning.free_anchor_point, the exact inverse of the
        free_top_left conversion _resolve applies on read) -- so a dragged bar keeps rule 5's
        size-invariance the same way a materialised or panel-set Free pin does. The GRAB offset
        above stays in top-left space throughout; only the value actually persisted is converted.

        BLOCKED OUTRIGHT UNDER FIXED (v23 follow-on): dragging only ever makes sense once the bar
        HAS a free-floating position to write, so the Free gate sits before any cursor read or
        window move -- the bar must never visibly follow the cursor and then snap back once the
        gesture ends, which is what letting the gesture run and discarding the result at "end"
        would look like. The gate guards the START / MOVE application ONLY: "end" runs its
        state-clearing cleanup UNCONDITIONALLY (so an alignment flip or Reset mid-gesture can never
        strand `_grab`/`_drag_pos`), and merely SKIPS the persist when Alignment is no longer Free.

        Fail-soft throughout: an unreadable cursor leaves the window exactly where it is, and nothing
        raises into the engine's input path."""
        if self._active is None:
            return
        try:
            if phase == "end":
                # ALWAYS clear the gesture state, even if Alignment left Free mid-gesture (a radio
                # flip or Reset): otherwise _grab/_drag_pos leak into the next gesture. Persist the
                # final position ONLY when the gesture still completed as a Free drag -- one whose
                # Alignment changed underneath it must not write a stale Free pin, but it must still
                # leave clean state behind (and a gesture that never moved has _drag_pos None).
                pos = self._drag_pos
                self._grab = None
                self._drag_pos = None
                self._declined = False
                if pos is not None and (mod_settings.progress_bar_alignment()
                                        == mod_settings.PROGRESS_ALIGN_FREE):
                    mod_settings.set_bar_position(pos[0], pos[1], persist=True)
                return
            # start / move only run under Free (dragging needs a free-floating pin to write) -- the
            # gate sits HERE, AFTER the end-cleanup above, so an alignment flip can never strand
            # _grab/_drag_pos in a state a later phase acts on.
            if mod_settings.progress_bar_alignment() != mod_settings.PROGRESS_ALIGN_FREE:
                return
            if phase == "start":
                self._declined = False
            elif self._declined:
                return                          # not our gesture; decided at its start
            window = self._active[0]
            # READ BEFORE _extent: a cold extent cache measures by MOVING the window to the far
            # sentinel, which would make this read the sentinel corner instead of where the bar is.
            origin = window.position
            # ONE extent measurement PER GESTURE: _extent's read is a real window MOVE (the far
            # sentinel), so an un-memoized read here would teleport the window per pointer event --
            # which is what made the bar visibly jump around the cursor. Only _place invalidates it.
            max_x, max_y = self._extent(window)
            space_x, space_y = self._space(window)
            if cursor is None:
                cursor = _cursor_position()
            screen = _screen_resolution()
            if phase == "start" or self._grab is None:
                # The grab is measured off the UNCLAMPED mapping: the cursor can legitimately sit
                # beyond the movable extent (the screen's bottom-right corner always does, by the
                # surface size), and clamping the measurement would bake that error into the offset
                # for the whole gesture.
                spot = cursor_logical(cursor, screen, space_x, space_y)
                if spot is None:
                    return                      # unreadable cursor -> no grab, no move
                # OWNERSHIP GATE (start only -- see the docstring): the surface size is
                # space - extent, so the rect needs nothing this handler has not already read.
                if not cursor_in_rect(spot, origin, (space_x - max_x, space_y - max_y)):
                    self._declined = True
                    return                      # the gesture began on somebody else's box
                # Grab from the window's ACTUAL position (`origin`, read above BEFORE _extent -- see
                # memory bar-host-drag-must-read-position-before-extent), NOT from _resolve(): the
                # window may sit elsewhere than _resolve() computes -- an engine-clamped Free pin, or
                # a minimap-size / interface-scale change since the last _place -- and grabbing off
                # the resolved point would teleport the bar by that divergence on the first move.
                self._grab = (origin[0] - spot[0], origin[1] - spot[1])
                self._drag_pos = None
                return                          # the bar is already where it was grabbed
            pos = cursor_top_left(cursor, screen, space_x, space_y,
                                  self._grab[0], self._grab[1])
            if pos is None:
                return
            window.move(pos[0], pos[1], xAnchor=PositionAnchor.LEFT, yAnchor=PositionAnchor.TOP)
            # Convert the just-applied TOP-LEFT into the stored ANCHOR POINT frame (Trap 3 Fix
            # B) -- window.move() above already ran in top-left space; only what gets persisted
            # changes frame. `self._drag_pos` carries the ANCHOR POINT from here on, so "end"
            # (above) needs no conversion of its own.
            vertical = (mod_settings.progress_bar_orientation()
                        == mod_settings.PROGRESS_ORIENT_VERTICAL)
            apos = free_anchor_point(pos, (space_x - max_x, space_y - max_y), vertical)
            self._drag_pos = apos
            mod_settings.set_bar_position(apos[0], apos[1], persist=False)
        except Exception:
            LOG_CURRENT_EXCEPTION()

    def apply_position(self):
        """Re-place this bar's window if open. Called from battle_bridge on an interface-scale
        change (the proportional anchor must follow the resized logical space) and on a MINIMAP
        RESIZE (the minimap alignment's base anchor moves with the minimap's width -- the size
        index is re-read here, per placement, so no state has to be invalidated). No-op when
        closed."""
        if self._active is None:
            return
        self._place(self._active[0])

    def ensure_placed(self):
        """Retry _place() while this host is open but has never landed (_place's readback
        rejected every attempt so far -- see its own docstring). No call site of _place is
        guaranteed to run against a realized (post-256x256-fallback) surface, so this is the
        reliable retry: called once per battle_bridge.refresh() tick for each active host,
        after open_window(), it costs nothing once has_placed() is True (the common case,
        checked first) and otherwise re-runs the exact same _place() the surface's own resize
        event would have re-triggered anyway, just without waiting on that event. No-op with no
        active window. _place() is already fail-soft, so nothing further to guard here."""
        if self._active is None or self.has_placed():
            return
        self._place(self._active[0])

    def _is_dead(self):
        """True if the engine destroyed our cached (window, view) out from under us -- the native
        WindowFlags.TOOLTIP teardown described at module top (_DEAD_STATUS). The cached handle is
        DEAD if the window's windowStatus or the view's viewStatus is DESTROYING/DESTROYED, or the
        view's viewModel has been nulled (native View._cFini). Checked on the per-tick open path so
        a dead handle is dropped and re-mounted instead of trusted forever.

        Fail-soft to ALIVE: an unreadable status must NOT thrash a window we cannot prove is dead --
        a false 'dead' would tear down and re-mount a healthy bar every tick."""
        if self._active is None:
            return False
        window, view = self._active
        try:
            if getattr(window, "windowStatus", None) in _DEAD_STATUS:
                return True
            if getattr(view, "viewStatus", None) in _DEAD_STATUS:
                return True
            return view.viewModel is None
        except Exception:
            return False

    def open_window(self):
        """Idempotently open this bar's window. Returns its _BarView (read ``.viewModel`` to push
        into), or None on failure / layout unresolved.

        ALSO SELF-HEALS a handle the engine destroyed out from under us (see _is_dead / the module
        docstring): a dead cached handle is DROPPED and re-mounted through the normal path below,
        rather than trusted forever -- which is what silently killed the bar for the rest of a
        battle after an alternative-equipment-slot click on the countdown. The re-mount re-runs the
        SAME code the first mount does (fresh view + window, re-armed onSizeChanged, all cold-start
        latches reset -- see below), so it re-places from the stored pin against the new window's own
        realized surface, exactly like the first mount. battle_bridge.refresh() re-drives this every
        tick for each gated-on window, which is what actually TRIGGERS the re-mount (open_window is
        not otherwise called mid-battle) -- once re-created it is alive again and this returns early,
        so there is no busy re-create loop."""
        if self._active is not None:
            if not self._is_dead():
                return self._active[1]
            LOG_DEBUG("%s handle destroyed by the engine -- re-mounting" % self._tag)
            self._active = None   # drop the dead handle; the fresh mount below resets _sized too
        try:
            layout = self._layout_id()
            if layout < 0:
                return None   # layout_id already logged it once
            # A FRESH window starts at the engine's 256x256 fallback again, same as the very
            # first one -- so the materialise-on-mount latch must reset here too, not just at
            # __init__, or a stale True from a PREVIOUS battle would let _materialise fire
            # against this window's own first (fallback-sized) _place call. The reject-log and
            # place-log latches reset alongside it so each gets ONE fresh LOG_PROD line per
            # battle, not just per process.
            # _last_good MUST reset too: it is what has_placed() reads, and a fresh unrealized
            # window has placed NOTHING yet. A stale True carried over from the previous mount would
            # make ensure_placed() early-return (skipping the cold-start retry) and open the
            # push_progress/push_efficiency visibility gate immediately -- flashing the bar
            # mis-placed at the far-sentinel corner before this window's own _place ever confirms.
            # Safe to null: _place re-resolves its target from the stored pin (_resolve), never from
            # _last_good; the only other reader is the exception fallback, which is None-guarded.
            self._sized = False
            self._reject_logged = False
            self._place_logged = False
            self._last_good = None
            view = _BarView(layout, self._vm_factory())
            window = _BarWindow(view, self._place, self)
            # Publish the singleton BEFORE load() so the view's _onLoading initial push (which calls
            # back through battle_bridge.refresh() -> active_view()) sees us.
            self._active = (window, view)
            window.load()
            LOG_DEBUG("%s window opened (layoutID=%s, layer=WINDOW, content-sized)"
                      % (self._tag, layout))
            return view
        except Exception:
            LOG_CURRENT_EXCEPTION()
            self._active = None
            return None

    def close_window(self):
        """Destroy this bar's window if open. MUST be called on battle teardown alongside the other
        windows' close_window()s or the window leaks across battles."""
        if self._active is None:
            return
        window = self._active[0]
        self._active = None
        try:
            window.detach()          # unhook onSizeChanged before the window goes away
            window.destroy()
            LOG_DEBUG("%s window destroyed" % self._tag)
        except Exception:
            LOG_CURRENT_EXCEPTION()

    def active_view(self):
        """The currently-open _BarView, or None."""
        return None if self._active is None else self._active[1]
