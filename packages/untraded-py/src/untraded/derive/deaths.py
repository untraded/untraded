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
        .sort("tick", "victim", "teammate")
    )
    death = (
        deaths.join(near, on="order", how="left")
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
        )
    )
    return death, opportunities


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
