# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Buy type per team and round (metrics-v1 § 5), aligned with CS Demo Manager."""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl


@dataclass(frozen=True)
class BuyThresholds:
    """⚙🎯 Thresholds on the team's average equipment value per player at freeze end + 7 s."""

    eco_max: float = 1000
    full_min_ct: float = 4500
    full_min_t: float = 4000
    half_rounds: int = 12
    """Regulation half length (MR12): pistol rounds are its first rounds (1 and 13)."""


def build_team_rounds(
    economy: pl.DataFrame,
    rounds: pl.DataFrame,
    teams: pl.DataFrame,
    thresholds: BuyThresholds | None = None,
) -> pl.DataFrame:
    t = thresholds or BuyThresholds()
    equipment = (
        economy.join(teams, on="steamid")
        .group_by("round", "team")
        .agg(pl.col("equip_value").mean().cast(pl.Float32))
    )
    per_team = pl.concat(
        [
            rounds.select(
                "round",
                pl.col(column).cast(pl.String).alias("team"),
                pl.lit(side).alias("side"),
                (pl.col("winner_team").cast(pl.String) == pl.col(column).cast(pl.String))
                .fill_null(False)
                .alias("won"),
            )
            for column, side in (("ct_team", "CT"), ("t_team", "T"))
        ]
    ).with_columns(pl.col("team").cast(teams.schema["team"]))
    pistol = (pl.col("round") - 1) % t.half_rounds == 0
    pistol = pistol & (pl.col("round") <= 2 * t.half_rounds)
    full = pl.col("equip_value") >= pl.when(pl.col("side") == "CT").then(t.full_min_ct).otherwise(
        t.full_min_t
    )
    eco = pl.col("equip_value") <= t.eco_max
    lost_before = pl.col("won").shift(1).over("team", order_by="round").not_().fill_null(False)
    return (
        per_team.join(equipment, on=["round", "team"], how="left")
        .sort("round", "team")
        .with_columns(
            pl.when(pistol)
            .then(pl.lit("pistol"))
            .when(eco)
            .then(pl.lit("eco"))
            .when(full)
            .then(pl.lit("full"))
            .when(lost_before)
            .then(pl.lit("force"))
            .otherwise(pl.lit("semi"))
            .alias("buy_type")
        )
    )
