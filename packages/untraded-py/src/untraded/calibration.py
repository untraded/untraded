# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Calibration of the v0 thresholds marked 🎯 (workstream E9, ADR 0007 and 0010).

Each function measures, on a corpus, what a threshold should separate, and suggests a value
with an explicit rule. The suggestions are evidence for a decision, not new defaults: a default
only changes when the data clearly contradicts it, with a version bump (docs/calibration.md).
Only demos of consenting players at the target level may be used (ADR 0010).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import polars as pl

from untraded.metrics import Dataset

DISTANCE_STEP = 250.0
"""Width of the distance buckets, in units."""
MONEY_STEP = 250.0
"""Width of the equipment value buckets, in $."""


@dataclass(frozen=True)
class Suggestion:
    parameter: str
    current: float
    suggested: float | None
    rule: str


# --- Buy types (buy.eco_max, buy.full_min_ct, buy.full_min_t) -------------------------------


def buy_profile(ds: Dataset) -> pl.DataFrame:
    """Team rounds outside pistol rounds, by side and equipment value bucket (average value per
    player at freeze-time end + 7 s): `side`, `bucket`, `rounds`, `win_pct`, `buy_type` (the
    most frequent type in the bucket under the current thresholds)."""
    rounds = ds["team_round"].filter(pl.col("buy_type").cast(pl.String) != "pistol")
    return (
        rounds.with_columns(
            (pl.col("equip_value") // MONEY_STEP * MONEY_STEP).alias("bucket"),
            pl.col("side").cast(pl.String),
        )
        .group_by("side", "bucket")
        .agg(
            pl.len().alias("rounds"),
            (pl.col("won").mean() * 100).alias("win_pct"),
            pl.col("buy_type").cast(pl.String).mode().first().alias("buy_type"),
        )
        .sort("side", "bucket")
    )


def buy_valleys(profile: pl.DataFrame, low: float, high: float) -> dict[str, float | None]:
    """Per side, the least populated bucket between `low` and `high` $: where a threshold
    between two buy clusters belongs. None without data in the range."""
    valleys: dict[str, float | None] = {}
    for side in ("CT", "T"):
        rows = profile.filter(
            (pl.col("side") == side) & pl.col("bucket").is_between(low, high)
        ).sort("rounds", "bucket")
        valleys[side] = float(rows["bucket"][0] + MONEY_STEP / 2) if rows.height else None
    return valleys


# --- Distances (isolation.radius, trade.opportunity_distance) ------------------------------


def isolation_profile(ds: Dataset, window_s: float = 5.0) -> pl.DataFrame:
    """Enemy-kill deaths with a living teammate, by distance to the nearest one: `bucket`,
    `deaths`, `traded_pct` (traded within `window_s`)."""
    deaths = ds["death"].filter(
        pl.col("is_enemy_kill") & pl.col("nearest_teammate_distance").is_not_null()
    )
    return (
        deaths.with_columns(
            (pl.col("nearest_teammate_distance") // DISTANCE_STEP * DISTANCE_STEP).alias("bucket"),
            (pl.col("trade_delay_s") <= window_s).fill_null(False).alias("traded"),
        )
        .group_by("bucket")
        .agg(pl.len().alias("deaths"), (pl.col("traded").mean() * 100).alias("traded_pct"))
        .sort("bucket")
    )


def isolation_radius(profile: pl.DataFrame, min_deaths: int = 20) -> float | None:
    """The distance where the traded share falls below half of its value at close range
    (under 500 units): beyond it, a teammate is too far to trade. Buckets with fewer than
    `min_deaths` deaths are ignored."""
    solid = profile.filter(pl.col("deaths") >= min_deaths)
    close = solid.filter(pl.col("bucket") < 500)
    if close.is_empty():
        return None
    reference = float((close["traded_pct"] * close["deaths"]).sum()) / float(close["deaths"].sum())
    beyond = solid.filter((pl.col("bucket") >= 500) & (pl.col("traded_pct") < reference / 2))
    return float(beyond["bucket"].min()) if beyond.height else None  # type: ignore[arg-type]


def trade_distances(ds: Dataset, window_s: float = 5.0) -> pl.Series:
    """For each death traded within `window_s`, the distance from the trader to the killer at
    the moment of the death."""
    traded = ds["death"].filter(pl.col("trade_delay_s") <= window_s)
    joined = traded.join(
        ds["trade_opportunity"].select(
            "match_id", "tick", "victim", pl.col("teammate").alias("trader"), "distance_to_killer"
        ),
        on=["match_id", "tick", "victim", "trader"],
    )
    return joined["distance_to_killer"]


# --- Recurring death spots (pos.recurring_death_share, pos.recurring_min_rounds) ------------


def recurring_replication(
    ds: Dataset,
    shares: Sequence[float] = (0.2, 0.25, 0.33, 0.4),
    min_rounds: Sequence[int] = (6, 8, 12, 16),
    window_s: float = 5.0,
) -> pl.DataFrame:
    """Does a recurring death spot found in half of a player's rounds come back in the other
    half? The rounds of each player on a map and side are split by parity (in match and round
    order); a spot is recurring in a half when its share of the half's untraded deaths reaches
    `share` (and holds at least 2 of them), on a half of at least `rounds` rounds.

    Returns one row per (`share`, `rounds`): `spots` found in the first half, `replicated` (also
    recurring in the second half), `precision_pct`."""
    played = ds.played.sort("steamid", "map", "side", "match_id", "round").with_columns(
        (pl.int_range(pl.len()).over("steamid", "map", "side") % 2).alias("half")
    )
    deaths = (
        ds["death"]
        .filter(pl.col("is_enemy_kill") & ~(pl.col("trade_delay_s") <= window_s).fill_null(False))
        .join(
            ds["kill"].select("match_id", "tick", "victim", "victim_place"),
            on=["match_id", "tick", "victim"],
        )
        .join(
            played.rename({"steamid": "victim"}),
            on=["match_id", "round", "victim"],
        )
    )
    halves = played.group_by("steamid", "map", "side", "half").agg(pl.len().alias("rounds"))
    zones = (
        deaths.group_by("victim", "map", "side", "half", "victim_place")
        .agg(pl.len().alias("deaths"))
        .with_columns(
            (pl.col("deaths") / pl.col("deaths").sum().over("victim", "map", "side", "half")).alias(
                "zone_share"
            )
        )
        .rename({"victim": "steamid", "victim_place": "zone"})
        .join(halves, on=["steamid", "map", "side", "half"])
    )
    rows = []
    for share in shares:
        for rounds in min_rounds:
            spots = zones.filter(
                (pl.col("zone_share") >= share)
                & (pl.col("deaths") >= 2)
                & (pl.col("rounds") >= rounds)
            )
            first = spots.filter(pl.col("half") == 0).select("steamid", "map", "side", "zone")
            second = spots.filter(pl.col("half") == 1).select("steamid", "map", "side", "zone")
            replicated = first.join(second, on=["steamid", "map", "side", "zone"]).height
            rows.append(
                {
                    "share": share,
                    "rounds": rounds,
                    "spots": first.height,
                    "replicated": replicated,
                    "precision_pct": replicated / first.height * 100 if first.height else None,
                }
            )
    return pl.DataFrame(rows)
