# -*- coding: utf-8 -*-
"""Engine-free data types for the in-battle MoE path. 2/3 compatible.

Mirrors domain/types.py for the garage path: the battle adapter reads the live client
into a BattleSnapshot, the battle builder turns that into a BattleMoEModel, and the
battle bridge marshals the model to the Gameface overlay. NOTHING here may import a game
symbol -- that is what lets the in-battle math unit-test on plain Python 3 (see tests/).
"""


class BattleSnapshot(object):
    """Engine-free description of the live combat state needed to project MoE standing.

    Live-combat components (this battle so far, from the personal-efficiency controller):
    - `damage`       : direct damage dealt.
    - `assist`       : assisted damage -- spot + track MERGED live (only post-battle splits
                       them), so the combined-damage figure derived from it is approximate.
    - `stun`         : stun-assisted damage (tracked separately live).
    - `team_damage`  : friendly-fire dealt (subtracted from combined damage); 0 when the
                       live controller exposes no team-damage bucket.

    Pre-battle dossier baseline (career standing to project against; readable in battle):
    - `pre_avg_damage` : current moving-average combined damage (dossier movingAvgDamage).
    - `pre_percentile` : current damage rating 0.0..100.0 (dossier damageRating).

    Reference data + gating:
    - `thresholds`   : {1: dmg, 2: dmg, 3: dmg, 100: dmg} per-tank combined-damage
                       distribution stops; {} when unknown / not loaded yet.
    - `nation`       : nation id string (optional; for any art).
    - `has_vehicle`  : whether a player vehicle was readable (False -> overlay hidden).
    - `in_battle`    : whether combat is active (arena BATTLE period; gates the overlay).
    - `is_spectating`: whether a DIFFERENT vehicle than the player's own is being observed
                       (postmortem free-look). True -> overlay hidden: the identity follows
                       the observed tank while the stats stay ours, so the readout is bogus.
    """
    def __init__(self, vehicle_int_cd=0, nation="", damage=0, assist=0, stun=0,
                 team_damage=0, pre_avg_damage=0, pre_percentile=0.0, thresholds=None,
                 has_vehicle=True, in_battle=True, is_spectating=False):
        self.vehicle_int_cd = vehicle_int_cd
        self.nation = nation
        self.damage = damage
        self.assist = assist
        self.stun = stun
        self.team_damage = team_damage
        self.pre_avg_damage = pre_avg_damage
        self.pre_percentile = pre_percentile
        self.thresholds = thresholds or {}
        self.has_vehicle = has_vehicle
        self.in_battle = in_battle
        self.is_spectating = is_spectating


class BattleMoEModel(object):
    """Output of build_battle_model(): the four in-battle readout values.

    - `combined_damage` : live combined damage this battle (CD).
    - `proj_avg_damage` : projected moving-average combined damage folding in this CD (EWMA).
    - `cur_percent`     : "where you'd stand if the battle ended now" (0.0..100.0), ANCHORED
                          to WG's real career standing: pre_percentile + this battle's interp
                          increment (interp(proj) - interp(pre_avg)), clamped 0..100. Opens at
                          exactly pre_percentile before any damage. 0.0 when thresholds unknown.
    - `pct_delta`       : the signed battle increment interp(proj) - interp(pre_avg) -- how far
                          this battle moves your standing, on a self-consistent interp scale
                          (NOT mixed against WG's rating). 0.0 when thresholds are unknown.
    - `has_data`        : True when the per-tank threshold table was usable (percent/delta real).
    """
    def __init__(self, combined_damage, proj_avg_damage, cur_percent, pct_delta,
                 has_data=False):
        self.combined_damage = combined_damage
        self.proj_avg_damage = proj_avg_damage
        self.cur_percent = cur_percent
        self.pct_delta = pct_delta
        self.has_data = has_data
