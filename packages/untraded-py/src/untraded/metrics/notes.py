# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Limits and version history of the metrics, for the generated pages (`docs/metrics/`).

Kept apart from the metric code so they can be reviewed in one place. Tests check that every key
is a registered metric, and that every version above 1.0.0 says what changed.
"""

from __future__ import annotations

ALL_LIMITS = (
    "Per-round values divide by the rounds the player **played** (connected and on a team at "
    "freeze-time end), not by the rounds of the match (metrics-v1 § 0).",
    "A dead player who takes over a bot of their team gets the bot's kills and damage, as on the "
    "in-game scoreboard; the bot's death is not theirs.",
)
"""Limits shared by every metric."""

FAMILY_LIMITS: dict[str, tuple[str, ...]] = {
    "duel": (
        "Distances are straight lines between positions, through walls: neither line of sight "
        "nor the navmesh path is taken into account (both come later).",
    ),
    "trade": (
        "A death is traded only when the killer is then killed **by the victim's team**, within "
        "`trade.window_s`, both ends included. CS Demo Manager differs in four ways: a killer "
        "killed by their own teammate trades the death, a player controlling a bot can trade, the "
        "kill of an enemy who had just killed a teammate is a trade kill, and a trade at exactly "
        "5.00 s does not count (validation-csdm § 5).",
        "Distances are straight lines between positions, through walls.",
    ),
    "clutch": (
        "Kills after the round end (exit frags) are ignored, so no clutch starts after it.",
        "The enemies are those present in the round: a missing player is not counted.",
        "When the last two players of a team die on the same tick, nobody clutched.",
        "A win is a round the clutcher's team wins, whether or not the clutcher survives.",
    ),
    "pos": (
        "Zones are the engine's navmesh place names (`last_place_name`, e.g. `BombsiteA`), not "
        "community callouts, and some places are large.",
        "These are distributions per map and side: they become meaningful over many rounds on "
        "the same map, not on a single match.",
    ),
    "util": (
        "Blinds of players already dead are ignored. Blind durations are the engine's, which "
        "already depend on the distance and the angle to the flash.",
    ),
    "eco": (
        "Buy types use thresholds aligned with CS Demo Manager (`buy.eco_max`, "
        "`buy.full_min_ct`, `buy.full_min_t`): a spending convention, checked on the corpus "
        "and kept (docs/calibration.md).",
    ),
    "rating": (
        "Ratings summarize; they hide what the other metrics explain. Read them with KAST, ADR "
        "and the duels.",
    ),
}

LIMITS: dict[str, tuple[str, ...]] = {
    "base.assists": (
        "An assist on the death of an uncontrolled bot is not counted, unlike CS Demo Manager.",
    ),
    "base.hs_pct": ("Undefined (empty) for a player without kills.",),
    "base.kast": (
        "Differs from CS Demo Manager by design. CS Demo Manager counts a round the player "
        "missed as survived, a player killed by a teammate as surviving, a flash-only assist, and "
        "a trade by the killer's own teammate; Untraded counts none of them (validation-csdm "
        "§ 1, § 4 and § 5).",
        "Flash assists do not count by default (`kast.count_flash_assist`).",
    ),
    "base.survival_pct": (
        "A player alive at the round end who dies after it (an exit frag) did not survive: the "
        "weapons are lost.",
    ),
    "duel.opening_kills": (
        "A death by a fall or the world (no killer) is not an opening; the opening is the first "
        "kill by a player.",
    ),
    "duel.opening_deaths": (
        "A death by a fall or the world (no killer) is not an opening; the opening is the first "
        "kill by a player.",
    ),
    "duel.isolated_deaths": (
        "The radius (🎯) was checked on the corpus and kept at 1000 units: the traded share "
        "halves by 750 units and drops to almost nothing beyond 1250 (docs/calibration.md).",
        "The last player alive is never isolated: there is no teammate to be far from.",
    ),
    "duel.nearest_teammate_at_death": (
        "A median over the player's deaths with a living teammate: undefined without any.",
    ),
    "trade.kill_opportunities": (
        "The sighting is the engine's spotting (the radar's), sampled at 16 Hz: not a true line "
        "of sight, and it can lag behind a quick trade, which is why a trade counts as seen. "
        "The distance (🎯) was calibrated on the corpus: 1300 units (docs/calibration.md).",
    ),
    "trade.death_opportunities": (
        "The sighting is the engine's spotting, sampled at 16 Hz. The distance (🎯) was "
        "calibrated on the corpus: 1300 units (docs/calibration.md).",
    ),
    "trade.untraded_deaths": (
        "Leaves out the deaths with no teammate left to trade them (the last player alive), so "
        "deaths = traded + untraded + those.",
    ),
    "duel.duels_lost": (
        "The sighting is the engine's spotting, sampled at 16 Hz: a duel the spotting missed "
        "is not counted, a death in the back never is. A death to a bot is never a duel: a bot "
        "has no steamid to spot.",
    ),
    "duel.lost_without_damage_pct": (
        "Damage to the killer earlier in the round counts, even in an earlier duel. About half "
        "of the duels lost on the corpus: compare it with the player's own reference.",
    ),
    "clutch.win_pct": ("Undefined (empty) for a player without clutch attempts.",),
    "pos.setup_zone_t20": (
        "Only rounds where the player is alive 20 s after freeze-time end (`setup.offset_s`).",
    ),
    "pos.recurring_death_spot": (
        "The share and the minimum rounds (🎯) were calibrated on the corpus "
        "(docs/calibration.md); the table is empty until the player has played enough rounds "
        "on a map and side.",
    ),
    "pos.heatmap_points": ("Raw points only: rendering comes in phase 2.",),
    "util.fire_damage": (
        "Fire damage is credited only when it is linked to one of the player's own molotovs or "
        "incendiaries (the game does not say whose fire it is, demoparser2 #317).",
    ),
    "util.he_damage": (
        "Only HE grenades. The 1 to 2 points of a smoke, flash or decoy hitting a player are "
        "not utility damage here, unlike CS Demo Manager.",
    ),
    "util.flash_to_kill": (
        "One count per kill for each player whose flash was still active, so two flashers can "
        "both be credited.",
    ),
    "util.unused_value_at_death": (
        "Fixed buy prices; grenades picked up from the ground count at the same price.",
    ),
    "eco.equipment_lost_at_death": (
        "The equipment value at the tick of death includes weapons picked up during the round.",
    ),
    "eco.kills_vs_buy": (
        "The class is the best weapon held, not the weapon used: a rifle holder killing with a "
        "pistol is a `rifle` kill.",
    ),
    "rating.hltv1": (
        "HLTV's reference averages date from the CS:GO 1.0 era and were not recomputed for CS2. "
        "The formula is public and exact; it is checked against independent calculations.",
    ),
    "rating.hltv2_approx": (
        "A community approximation of a formula HLTV does not publish: no error margin against "
        "HLTV's own values is known. Always label it approx.",
        "Can be negative; CS Demo Manager floors it at 0.",
    ),
    "rating.swing": (
        "The model is trained on a small corpus of high-level matches (docs/winprob.md): its "
        "numbers move with each new model version, which bumps this metric's version.",
        "The death of a bot is not credited.",
    ),
    "rating.untraded": (
        "Beta: the scale is measured on a small corpus of high-level matches (docs/winprob.md). "
        "A new model or a larger corpus gives a new scale, which bumps this metric's version.",
        "Read it with its margin (`rating.untraded_margin`): over one match, it is wide.",
        "What the player's actions were worth in the match, noisy over one match: for what the "
        "player is worth, read `rating.untraded_level`.",
    ),
    "rating.untraded_level": (
        "Beta: fitted on 54 high-level matches (docs/winprob.md). Over one match it is the box "
        "score's prediction; how fast the ledger should take over across matches is not measured "
        "yet.",
        "Closer to 1.00 than the match rating by design: it is the match rating to expect.",
    ),
    "rating.untraded_margin": (
        "It only counts the spread of the player's own rounds, not the model's uncertainty.",
    ),
}

FIRST_PR: dict[str, int] = {
    "base": 32,
    "duel": 33,
    "trade": 33,
    "clutch": 33,
    "pos": 34,
    "util": 35,
    "eco": 36,
    "rating": 37,
}
"""Pull request that added each family at 1.0.0."""

_TRADES = (
    "Trades now count a kill on the same tick (delay 0) (#41) and the victim's own grenade or "
    "fire killing the killer later (#42); two players killing each other on the same tick "
    "trade nothing."
)
_CLUTCHES = "A player who leaves the server mid-round leaves the team's lineup (#44)."
_OPPORTUNITY = (
    "`trade.opportunity_distance` 1000 -> 1300 units: 26 % of the real trades of the calibration "
    "corpus came from beyond 1000 units, 90 % from within 1300 (docs/calibration.md)."
)
_RECURRING = (
    "`pos.recurring_min_rounds` 8 -> 32 rounds: at 8, only 8 % of the spots found in half of a "
    "player's rounds came back in the other half (docs/calibration.md)."
)

CHANGES: dict[str, dict[str, str]] = {
    "base.assist_score": {"1.0.0": "First version (#43)."},
    "rating.untraded": {
        "1.0.0": "First version, the beta of the open rating (#137).",
        "2.0.0": "The Untraded Rating 2.0: the ledger's credit per round (every change of the "
        "round's win probability credited, the hold left out), on a scale fitted on 54 matches "
        "(s = 15.31); the average player of a match is 1.00 by construction (#153 to #157).",
    },
    "rating.untraded_level": {"1.0.0": "First version, with the Untraded Rating 2.0 (#157)."},
    "rating.untraded_margin": {
        "1.0.0": "First version, the beta of the open rating (#137).",
        "2.0.0": "The margin of the rating 2.0: the spread of the ledger's credit per round.",
    },
    "rating.untraded_parts": {
        "1.0.0": "First version, the beta of the open rating (#137).",
        "2.0.0": "The parts of the rating 2.0: shooting, utility, trade, objective, taken, team, "
        "balance and baseline.",
    },
    "rating.swing": {
        "1.0.0": "First version, with the win-probability model 1.0 (#125).",
        "1.1.0": "Nothing is credited once the round is decided: a death to the bomb's explosion "
        "debited its victim (#126).",
    },
    "base.kast": {
        "1.1.0": "A death after the round end is not a survival (#43), as in CS Demo Manager. "
        + _TRADES,
    },
    "base.survival_pct": {
        "1.1.0": "A death after the round end is not a survival: the weapons are lost (#43).",
    },
    "rating.hltv2_approx": {"1.1.0": "Follows `base.kast` 1.1.0 (#41, #42, #43)."},
    **{
        metric_id: {"1.1.0": _TRADES}
        for metric_id in (
            *(
                f"trade.{name}{suffix}"
                for name in ("trade_kills", "traded_deaths", "traded_death_pct", "untraded_deaths")
                for suffix in ("", "_w3")
            ),
            "trade.kill_conversion_pct",
            "duel.isolated_deaths",
            "duel.isolated_death_pct",
            "pos.death_zones",
            "pos.recurring_death_spot",
        )
    },
    "trade.death_opportunities": {"1.1.0": _OPPORTUNITY},
    "trade.kill_opportunities": {"1.1.0": _OPPORTUNITY},
    **{
        metric_id: {"1.1.0": _CLUTCHES}
        for metric_id in (
            *(f"clutch.{kind}_1v{n}" for kind in ("attempts", "wins") for n in range(1, 6)),
            "clutch.win_pct",
        )
    },
}
"""What changed in each version above 1.0.0, or a first version outside its family's PR."""
CHANGES["trade.kill_conversion_pct"]["1.2.0"] = _OPPORTUNITY
CHANGES["pos.recurring_death_spot"]["1.2.0"] = _RECURRING
_SIGHT = (
    "An opportunity needs the teammate to have seen the killer within `trade.window_s` (the "
    "engine's spotting), or to have traded it: distance alone counted teammates behind walls, "
    "and only 14 % of the opportunities were converted (#167)."
)
_ALONE = "The last player alive has nobody to trade them: such a death is left out (#167)."
for _metric in ("trade.kill_opportunities", "trade.death_opportunities"):
    CHANGES[_metric]["1.2.0"] = _SIGHT
CHANGES["trade.kill_conversion_pct"]["1.3.0"] = _SIGHT
for _metric in ("trade.untraded_deaths", "trade.untraded_deaths_w3"):
    CHANGES[_metric]["1.2.0"] = _ALONE
CHANGES["pos.recurring_death_spot"]["1.3.0"] = _ALONE
CHANGES["duel.duels_lost"] = {"1.0.0": "First version (#167)."}
CHANGES["duel.lost_without_damage_pct"] = {"1.0.0": "First version (#167)."}


def history(metric_id: str, version: str) -> list[tuple[str, str]]:
    """`(version, change)` pairs, oldest first, up to `version`."""
    family = metric_id.split(".")[0]
    entries = {"1.0.0": f"First version (#{FIRST_PR[family]})."} | CHANGES.get(metric_id, {})
    return sorted(entries.items(), key=lambda e: tuple(int(p) for p in e[0].split(".")))
