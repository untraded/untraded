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
        "`trade.window_s` and the same tick included. A killer killed by their own teammate does "
        "not trade it, unlike CS Demo Manager.",
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
        "Differs from CS Demo Manager by design: it counts rounds the player missed as survived, "
        "a player killed by a teammate as surviving, flash-only assists, and trades by the "
        "killer's own teammate (validation-csdm § 4 and § 5).",
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

CHANGES: dict[str, dict[str, str]] = {
    "base.assist_score": {"1.0.0": "First version (#43)."},
    "base.kast": {
        "1.1.0": "A death after the round end is not a survival (#43), as in CS Demo Manager.",
    },
    "base.survival_pct": {
        "1.1.0": "A death after the round end is not a survival: the weapons are lost (#43).",
    },
    "rating.hltv2_approx": {"1.1.0": "Follows `base.kast` 1.1.0 (#43)."},
}
"""What changed in each version above 1.0.0, or a first version outside its family's PR."""


def history(metric_id: str, version: str) -> list[tuple[str, str]]:
    """`(version, change)` pairs, oldest first, up to `version`."""
    family = metric_id.split(".")[0]
    entries = {"1.0.0": f"First version (#{FIRST_PR[family]})."} | CHANGES.get(metric_id, {})
    return sorted(entries.items(), key=lambda e: tuple(int(p) for p in e[0].split(".")))
