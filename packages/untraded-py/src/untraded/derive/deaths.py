# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Deaths in context: openings, trades and spacing (metrics-v1 § 2).

A is killed by enemy B at tick t. If a teammate C of A kills B later in the same round (or on the
same tick), A's death is traded after `trade_delay_s`, by C (the trader); C's kill `avenges_delay_s`
after A's death. When A and B kill each other on the same tick, nobody is traded; A's own
grenade or fire killing B later does trade A's death.
The trade window W (5 s by default) is applied by the metrics: traded = delay <= W.
"""

from __future__ import annotations

import polars as pl

from untraded.parsing.schema import Team

_POSITION = ("x", "y", "z")


def build_deaths(
    kills: pl.DataFrame,
    teams: pl.DataFrame,
    rounds: pl.DataFrame,
    states: pl.DataFrame,
    tickrate: float,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Returns (`death`, `trade_opportunity`).

    `teams`: steamid -> team. `states`: `player_tick`, which holds an exact row at every kill tick.
    """
    deaths = (
        kills.with_row_index("order")
        .join(teams.rename({"steamid": "victim", "team": "victim_team"}), on="victim", how="left")
        .join(
            teams.rename({"steamid": "attacker", "team": "killer_team"}), on="attacker", how="left"
        )
        .with_columns(
            # A bot nobody controls has no steamid: its team is the killer's opposite (see
            # parsing.core.mark_bot_victims). A taken-over bot is on its controller's team.
            pl.when(pl.col("victim").is_null())
            .then(_opposite(pl.col("killer_team")))
            .otherwise(pl.col("victim_team"))
            .alias("victim_team"),
            # A bot's death is nobody's death.
            pl.when(pl.col("victim_bot")).then(None).otherwise(pl.col("victim")).alias("victim"),
        )
        .with_columns(
            (
                pl.col("attacker").is_not_null()
                & (pl.col("attacker") != pl.col("victim")).fill_null(True)
                & (pl.col("killer_team") != pl.col("victim_team"))
            )
            .fill_null(False)
            .alias("is_enemy_kill")
        )
    )
    deaths = _openings(deaths, rounds)
    deaths = _trades(deaths, tickrate)

    alive = (
        states.filter(pl.col("is_alive"))
        .join(teams, on="steamid")
        .select("tick", pl.col("steamid").alias("teammate"), "team", *_POSITION)
    )
    near = (
        deaths.select("order", "tick", "victim", "victim_team", "victim_x", "victim_y", "victim_z")
        .join(alive, left_on=["tick", "victim_team"], right_on=["tick", "team"])
        .filter(pl.col("teammate") != pl.col("victim"))
        .group_by("order")
        .agg(_distance("victim").min().alias("nearest_teammate_distance"))
    )
    sightings = _sightings(states, deaths)
    opportunities = (
        deaths.filter(pl.col("is_enemy_kill"))
        .select(
            "tick",
            "round",
            "victim",
            "victim_team",
            pl.col("attacker").alias("killer"),
            "attacker_x",
            "attacker_y",
            "attacker_z",
        )
        .join(alive, left_on=["tick", "victim_team"], right_on=["tick", "team"])
        .filter(pl.col("teammate") != pl.col("victim"))
        .select(
            "tick",
            "round",
            "victim",
            "killer",
            "teammate",
            _distance("attacker").alias("distance_to_killer"),
        )
    )
    # As-of joins keep one row per opportunity or death, however many samples there are.
    # The first sample, from the kill on, where the teammate sees the killer.
    first_sight = (
        opportunities.select("tick", "round", "victim", _id("killer"), _id("teammate"))
        .sort("tick")
        .join_asof(
            sightings.rename({"seen": "killer", "seer": "teammate"}),
            left_on="tick",
            right_on="seen_tick",
            by=["round", "killer", "teammate"],
            strategy="forward",
            check_sortedness=False,  # both sides are sorted on the tick just above
        )
        .select(
            "tick",
            "victim",
            "teammate",
            ((pl.col("seen_tick") - pl.col("tick")) / tickrate).alias("sight_delay_s"),
        )
    )
    opportunities = (
        opportunities.with_columns(_id("teammate"))
        .join(first_sight, on=["tick", "victim", "teammate"], how="left")
        .sort("tick", "victim", "teammate")
    )
    # The last sample, up to the death, where the victim saw the killer.
    last_sight = (
        deaths.filter(pl.col("is_enemy_kill") & pl.col("victim").is_not_null())
        .select("order", "tick", "round", _id("victim"), _id("attacker"))
        .sort("tick")
        .join_asof(
            sightings.rename({"seen": "attacker", "seer": "victim"}),
            left_on="tick",
            right_on="seen_tick",
            by=["round", "victim", "attacker"],
            strategy="backward",
            check_sortedness=False,
        )
        .select("order", ((pl.col("tick") - pl.col("seen_tick")) / tickrate).alias("last_sight_s"))
    )
    death = (
        deaths.join(near, on="order", how="left")
        .join(last_sight, on="order", how="left")
        .sort("order")
        .select(
            "tick",
            "round",
            "victim",
            "victim_team",
            "victim_bot",
            pl.col("attacker").alias("killer"),
            "killer_team",
            "is_enemy_kill",
            "is_opening",
            "trade_delay_s",
            "trader",
            "avenges_delay_s",
            "nearest_teammate_distance",
            "last_sight_s",
        )
    )
    return death, opportunities


def _sightings(states: pl.DataFrame, deaths: pl.DataFrame) -> pl.DataFrame:
    """(`round`, `seen`, `seer`, `seen_tick`): the samples where `seer` has spotted `seen`, the
    engine's `spotted_by` (radar visibility), both still alive (a dead player stays spotted).
    Sorted by `seen_tick`, one row per sample and pair."""
    # A player dies once a round: the first death counts, so that a crafted demo repeating
    # deaths cannot multiply the rows.
    died = (
        deaths.filter(pl.col("victim").is_not_null())
        .group_by("round", _id("victim").alias("steamid"))
        .agg(pl.col("tick").min().alias("died"))
    )
    living = pl.col("died").is_null() | (pl.col("seen_tick") <= pl.col("died"))
    spotted = (
        states.filter(pl.col("spotted_by").list.len() > 0)
        .select(
            pl.col("tick").alias("seen_tick"),
            "round",
            _id("steamid").alias("seen"),
            pl.col("spotted_by").alias("seer"),
        )
        .explode("seer")
        .with_columns(_id("seer"))
        .unique()
    )
    for column in ("seen", "seer"):
        spotted = (
            spotted.join(died, left_on=["round", column], right_on=["round", "steamid"], how="left")
            .filter(living)
            .drop("died")
        )
    return spotted.sort("seen_tick")


def _id(column: str) -> pl.Expr:
    """A steamid column, cast to one type so that joins on players match."""
    return pl.col(column).cast(pl.UInt64)


def _opposite(team: pl.Expr) -> pl.Expr:
    return team.cast(pl.String).replace_strict({"A": "B", "B": "A"}, default=None).cast(Team)


def _distance(prefix: str) -> pl.Expr:
    """3D distance between the `teammate` position (x, y, z) and `{prefix}_x/y/z`."""
    dx, dy, dz = (pl.col(axis) - pl.col(f"{prefix}_{axis}") for axis in _POSITION)
    return (dx * dx + dy * dy + dz * dz).sqrt()


def _openings(deaths: pl.DataFrame, rounds: pl.DataFrame) -> pl.DataFrame:
    """The opening is the first enemy kill of the round after freeze-time end."""
    first = (
        deaths.join(rounds.select("round", "freeze_end_tick"), on="round")
        .filter(pl.col("is_enemy_kill") & (pl.col("tick") >= pl.col("freeze_end_tick")))
        .group_by("round")
        .agg(pl.col("order").min().alias("opening_order"))
    )
    return (
        deaths.join(first, on="round", how="left")
        .with_columns(
            (pl.col("order") == pl.col("opening_order")).fill_null(False).alias("is_opening")
        )
        .drop("opening_order")
    )


def _trades(deaths: pl.DataFrame, tickrate: float) -> pl.DataFrame:
    """Adds `trade_delay_s` and `trader` (for the victim) and `avenges_delay_s` (for the killer)."""
    enemy = deaths.filter(pl.col("is_enemy_kill"))
    # The killer's own death by the victim's team, later in the round (a player dies once).
    revenge = enemy.select(
        "round",
        pl.col("victim").alias("attacker"),
        pl.col("tick").alias("revenge_tick"),
        pl.col("attacker").alias("trader"),
        pl.col("killer_team").alias("trader_team"),
    )
    # The same tick counts (a delay of 0), unless the victim and the killer killed each other.
    # Later, the victim's own grenade or fire can still kill the killer: that counts.
    traded = (
        enemy.select("order", "round", "attacker", "victim", "tick", "victim_team")
        .join(revenge, on=["round", "attacker"])
        .filter(
            (
                (pl.col("revenge_tick") > pl.col("tick"))
                | (
                    (pl.col("revenge_tick") == pl.col("tick"))
                    & (pl.col("trader") != pl.col("victim")).fill_null(True)
                )
            )
            & (pl.col("trader_team") == pl.col("victim_team"))
        )
        .select(
            "order",
            ((pl.col("revenge_tick") - pl.col("tick")) / tickrate).alias("trade_delay_s"),
            "trader",
        )
    )
    # For a kill of B by C: the latest earlier kill by B of a teammate of C.
    earlier = enemy.select(
        "round",
        pl.col("attacker").alias("victim"),
        pl.col("tick").alias("earlier_tick"),
        pl.col("victim").alias("earlier_victim"),
        pl.col("victim_team").alias("earlier_victim_team"),
    )
    avenging = (
        enemy.select("order", "round", "victim", "attacker", "tick", "killer_team")
        .join(earlier, on=["round", "victim"])
        .filter(
            (
                (pl.col("earlier_tick") < pl.col("tick"))
                | (
                    (pl.col("earlier_tick") == pl.col("tick"))
                    & (pl.col("earlier_victim") != pl.col("attacker")).fill_null(True)
                )
            )
            & (pl.col("earlier_victim_team") == pl.col("killer_team"))
        )
        .group_by("order")
        .agg(pl.col("tick").first(), pl.col("earlier_tick").max())
        .select(
            "order", ((pl.col("tick") - pl.col("earlier_tick")) / tickrate).alias("avenges_delay_s")
        )
    )
    return deaths.join(traded, on="order", how="left").join(avenging, on="order", how="left")
