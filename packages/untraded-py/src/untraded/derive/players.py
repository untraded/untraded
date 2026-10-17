# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""`round_player`: one row per player and round played (metrics-v1 § 0 and § 1)."""

from __future__ import annotations

import polars as pl

SETUP_OFFSET_S = 20.0
"""⚙ `setup.offset_s`: the setup zone is read this long after freeze-time end (metrics-v1 § 3)."""


def build_round_players(
    *,
    economy: pl.DataFrame,
    teams: pl.DataFrame,
    rounds: pl.DataFrame,
    kills: pl.DataFrame,
    deaths: pl.DataFrame,
    damage: pl.DataFrame,
    states: pl.DataFrame,
    tickrate: float,
) -> pl.DataFrame:
    """Rounds played are the rows of `economy`: on a team at freeze-time end."""
    played = economy.select("round", "steamid", "side").join(teams, on="steamid")
    enemy = deaths.filter(pl.col("is_enemy_kill"))

    kill_counts = enemy.group_by("round", pl.col("killer").alias("steamid")).agg(
        pl.len().alias("kills"), pl.col("is_opening").any().alias("opening_kill")
    )
    death_rows = deaths.group_by("round", pl.col("victim").alias("steamid")).agg(
        pl.len().alias("deaths"),
        pl.col("tick").min().alias("death_tick"),
        pl.col("trade_delay_s").min().alias("death_trade_delay_s"),
        pl.col("is_opening").any().alias("opening_death"),
    )
    enemy_kills = kills.join(
        enemy.select("tick", "victim", "killer"),
        left_on=["tick", "victim", "attacker"],
        right_on=["tick", "victim", "killer"],
        how="semi",
    )
    assists = (
        enemy_kills.filter(pl.col("assister").is_not_null())
        .group_by("round", pl.col("assister").alias("steamid"))
        .agg(
            (~pl.col("flash_assist")).sum().alias("assists"),
            pl.col("flash_assist").sum().alias("flash_assists"),
        )
    )
    dealt = (
        damage.join(teams.rename({"steamid": "attacker", "team": "attacker_team"}), on="attacker")
        .join(teams.rename({"steamid": "victim", "team": "victim_team"}), on="victim")
        .filter(pl.col("attacker_team") != pl.col("victim_team"))
        .group_by("round", pl.col("attacker").alias("steamid"))
        .agg(pl.col("damage").sum().alias("damage"))
    )
    at_end = states.join(
        rounds.select("round", "end_tick"),
        left_on=["round", "tick"],
        right_on=["round", "end_tick"],
    ).select("round", "steamid", pl.col("is_alive").alias("survived"))
    offset = round(SETUP_OFFSET_S * tickrate)
    setup = (
        states.join(rounds.select("round", "freeze_end_tick"), on="round")
        .filter(pl.col("tick") >= pl.col("freeze_end_tick") + offset)
        .sort("tick")
        .group_by("round", "steamid")
        .agg(pl.col("is_alive").first(), pl.col("place").first())
        .select(
            "round",
            "steamid",
            pl.when(pl.col("is_alive")).then(pl.col("place")).alias("setup_place"),
        )
    )
    outcome = pl.concat(
        [
            rounds.select(
                "round",
                pl.col(column).cast(pl.String).alias("team"),
                (pl.col("winner_team").cast(pl.String) == pl.col(column).cast(pl.String))
                .fill_null(False)
                .alias("team_won"),
            )
            for column in ("ct_team", "t_team")
        ]
    ).with_columns(pl.col("team").cast(teams.schema["team"]))

    return (
        played.join(kill_counts, on=["round", "steamid"], how="left")
        .join(death_rows, on=["round", "steamid"], how="left")
        .join(assists, on=["round", "steamid"], how="left")
        .join(dealt, on=["round", "steamid"], how="left")
        .join(at_end, on=["round", "steamid"], how="left")
        .join(setup, on=["round", "steamid"], how="left")
        .join(outcome, on=["round", "team"], how="left")
        .with_columns(
            pl.col("kills", "deaths", "assists", "flash_assists", "damage").fill_null(0),
            pl.col("opening_kill", "opening_death", "survived").fill_null(False),
        )
        .sort("round", "steamid")
    )
