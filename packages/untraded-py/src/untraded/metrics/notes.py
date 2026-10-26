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
        "Buy types use v0 thresholds aligned with CS Demo Manager (`buy.eco_max`, "
        "`buy.full_min_ct`, `buy.full_min_t`), still to calibrate on our target level.",
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
        "The radius is a v0 threshold (🎯), not yet calibrated.",
        "The last player alive is never isolated: there is no teammate to be far from.",
    ),
    "duel.nearest_teammate_at_death": (
        "A median over the player's deaths with a living teammate: undefined without any.",
    ),
    "trade.kill_opportunities": (
        "An opportunity is a distance, not a sight line: a teammate behind a wall within the "
        "distance had one. The distance is a v0 threshold (🎯).",
    ),
    "trade.death_opportunities": (
        "An opportunity is a distance, not a sight line. The distance is a v0 threshold (🎯).",
    ),
    "trade.untraded_deaths": (
        "Includes deaths with no teammate left to trade them (the last player alive).",
    ),
    "clutch.win_pct": ("Undefined (empty) for a player without clutch attempts.",),
    "pos.setup_zone_t20": (
        "Only rounds where the player is alive 20 s after freeze-time end (`setup.offset_s`).",
    ),
    "pos.recurring_death_spot": (
        "The share and the minimum rounds are v0 thresholds (🎯); the table is empty until the "
        "player has played enough rounds on a map and side.",
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
    "rating.swing": {"1.0.0": "First version, with the win-probability model 1.0 (#125)."},
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


def history(metric_id: str, version: str) -> list[tuple[str, str]]:
    """`(version, change)` pairs, oldest first, up to `version`."""
    family = metric_id.split(".")[0]
    entries = {"1.0.0": f"First version (#{FIRST_PR[family]})."} | CHANGES.get(metric_id, {})
    return sorted(entries.items(), key=lambda e: tuple(int(p) for p in e[0].split(".")))
