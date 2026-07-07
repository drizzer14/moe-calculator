# -*- coding: utf-8 -*-
"""Pre-battle career baseline cache (engine-free, unit-testable).

The in-battle overlay needs the vehicle's CAREER standing to project from: its MoE
percentile and its moving-average combined damage. Those come from the lobby items-cache
vehicle dossier -- which is NOT available in battle: `IItemsCache.items.getVehicleDossier`
returns None there, so `engine_adapter._read_moe` fails soft to (0, 0.0, 0) and the overlay
would read 0% / 0 avg at the start of every battle (verified: python.log push shows
pct=0.0 delta=0.00 for a 73.7% tank).

So we snapshot the baseline from the GARAGE read (where the dossier IS readable), keyed by
vehicle intCD, and the battle adapter falls back to it when the in-battle read comes back
empty. The battle intCD (`arena.vehicles[vid]['vehicleType'].type.compactDescr`) equals the
garage intCD (`g_currentVehicle.item.intCD`) -- both are the vehicle type compactDescr --
so the key matches across the garage->battle hop.

Module-level state lives for the client session: a tank selected in the garage this session
(the normal "pick tank -> battle" flow) has a usable baseline in battle. A tank never opened
in the garage has no entry and simply degrades to the old 0 baseline.
"""

_baseline = {}  # int_cd -> (percentile_float, avg_damage_int)


def remember(int_cd, percentile, avg_damage):
    """Record a vehicle's career baseline from a garage read. No-op for a falsy key or an
    empty (all-zero) read, so a never-played tank or a transient blank never overwrites a
    good baseline."""
    if not int_cd:
        return
    p = float(percentile or 0.0)
    a = int(avg_damage or 0)
    if p <= 0.0 and a <= 0:
        return
    _baseline[int(int_cd)] = (p, a)


def get(int_cd):
    """The remembered (percentile, avg_damage) for a vehicle, or None if never seen."""
    if not int_cd:
        return None
    return _baseline.get(int(int_cd))


def clear():
    """Test helper: drop all remembered baselines."""
    _baseline.clear()
