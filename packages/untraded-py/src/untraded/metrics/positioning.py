# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""§ 3 Positioning (docs/metrics-v1.md): distributions per map and side, as `table` metrics.

Zones are the engine navmesh place names (`last_place_name`, metrics-v1 § 0).
"""

from __future__ import annotations

import math
from collections.abc import Mapping

import polars as pl

from untraded.metrics.dataset import Dataset
from untraded.metrics.registry import ParamValue, metric

WINDOW = {"trade.window_s": 5.0}
RECURRING = {"pos.recurring_death_share": 0.25, "pos.recurring_min_rounds": 8}
KEYS = ["steamid", "map", "side"]


def _placed(ds: Dataset, rows: pl.DataFrame, player: str) -> pl.DataFrame:
    """Rows in a kept round of `player`, with that player's map and side, as `steamid`."""
    return rows.join(
        ds.played.rename({"steamid": player}), on=["match_id", "round", player]
    ).rename({player: "steamid"})


def _deaths(ds: Dataset) -> pl.DataFrame:
    """The player's deaths in kept rounds, with the zone and position of the death."""
    deaths = ds["death"].join(
        ds["kill"].select(
            "match_id", "tick", "victim", "victim_place", "victim_x", "victim_y", "victim_z"
        ),
        on=["match_id", "tick", "victim"],
    )
    return _placed(ds, deaths, "victim")


def _kills(ds: Dataset) -> pl.DataFrame:
    """The player's enemy kills in kept rounds, with the killer's zone and position."""
    kills = (
        ds["death"]
        .filter(pl.col("is_enemy_kill"))
        .join(
            ds["kill"].select(
                "match_id",
                "tick",
                "victim",
                "attacker_place",
                "attacker_x",
                "attacker_y",
                "attacker_z",
            ),
            on=["match_id", "tick", "victim"],
        )
    )
    return _placed(ds, kills, "killer")


def _traded(window: ParamValue) -> pl.Expr:
    return (pl.col("trade_delay_s") <= window).fill_null(False)


@metric(
    "pos.death_zones",
    version="1.0.0",
    name="Death zones",
    unit="table",
    kind="table",
    params=WINDOW,
    uses=("death", "kill"),
    doc="Deaths by zone, per map and side, with the traded % in each zone. Columns: "
    "`steamid`, `map`, `side`, `zone`, `deaths`, `traded_pct`.",
)
def death_zones(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    return (
        _deaths(ds)
        .group_by(*KEYS, pl.col("victim_place").alias("zone"))
        .agg(
            pl.len().alias("deaths"),
            (_traded(p["trade.window_s"]).mean() * 100).alias("traded_pct"),
        )
        .sort(*KEYS, "deaths", descending=[False, False, False, True])
    )


@metric(
    "pos.kill_zones",
    version="1.0.0",
    name="Kill zones",
    unit="table",
    kind="table",
    uses=("death", "kill"),
    doc="Enemy kills by the killer's zone, per map and side. Columns: `steamid`, `map`, "
    "`side`, `zone`, `kills`.",
)
def kill_zones(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return (
        _kills(ds)
        .group_by(*KEYS, pl.col("attacker_place").alias("zone"))
        .agg(pl.len().alias("kills"))
        .sort(*KEYS, "kills", descending=[False, False, False, True])
    )


def _setups(ds: Dataset) -> pl.DataFrame:
    rows = ds.round_players().drop_nulls("setup_place")
    return (
        rows.join(
            ds.played.select("match_id", "round", "steamid", "map"),
            on=["match_id", "round", "steamid"],
        )
        .group_by(*KEYS, pl.col("setup_place").alias("zone"))
        .agg(pl.len().alias("rounds"))
    )


@metric(
    "pos.setup_zone_t20",
    version="1.0.0",
    name="Position at T+20 s",
    unit="table",
    kind="table",
    uses=("round_player",),
    doc="The player's zone 20 s after freeze-time end (rounds where they are alive then), "
    "per map and side: CT setups, T defaults. Columns: `steamid`, `map`, `side`, "
    "`zone`, `rounds`, `share_pct`.",
)
def setup_zone_t20(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return (
        _setups(ds)
        .with_columns(
            (pl.col("rounds") / pl.col("rounds").sum().over(KEYS) * 100).alias("share_pct")
        )
        .sort(*KEYS, "rounds", descending=[False, False, False, True])
    )


def _normalized_entropy(counts: list[int]) -> float:
    total = sum(counts)
    if len(counts) < 2 or total == 0:
        return 0.0
    entropy = -sum(c / total * math.log(c / total) for c in counts if c)
    return entropy / math.log(len(counts))


@metric(
    "pos.setup_diversity",
    version="1.0.0",
    name="Predictability",
    unit="table",
    kind="table",
    uses=("round_player",),
    doc="Normalized entropy of the T+20 s zone distribution, per map and side: 0 = always "
    "the same zone, 1 = spread evenly over the zones used (entropy ÷ ln of the number "
    "of distinct zones; 0 with a single zone). Columns: `steamid`, `map`, `side`, "
    "`rounds`, `zones`, `diversity`.",
)
def setup_diversity(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    grouped = _setups(ds).group_by(KEYS).agg(pl.col("rounds"))
    return grouped.select(
        *KEYS,
        pl.col("rounds").list.sum().alias("rounds"),
        pl.col("rounds").list.len().alias("zones"),
        pl.col("rounds")
        .map_elements(lambda counts: _normalized_entropy(list(counts)), return_dtype=pl.Float64)
        .alias("diversity"),
    ).sort(KEYS)


@metric(
    "pos.recurring_death_spot",
    version="1.0.0",
    name="Recurring death spot",
    unit="table",
    kind="table",
    params={**WINDOW, **RECURRING},
    uses=("death", "kill", "round_player"),
    doc="Per map and side: zones holding at least `pos.recurring_death_share` of the "
    "player's **untraded** deaths, when the player played at least "
    "`pos.recurring_min_rounds` rounds there. Columns: `steamid`, `map`, `side`, `zone`, "
    "`untraded_deaths`, `share_pct`, `rounds`.",
)
def recurring_death_spot(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    untraded = _deaths(ds).filter(~_traded(p["trade.window_s"]))
    zones = (
        untraded.group_by(*KEYS, pl.col("victim_place").alias("zone"))
        .agg(pl.len().alias("untraded_deaths"))
        .with_columns(
            (pl.col("untraded_deaths") / pl.col("untraded_deaths").sum().over(KEYS) * 100).alias(
                "share_pct"
            )
        )
    )
    rounds = ds.played.group_by(KEYS).agg(pl.len().alias("rounds"))
    return (
        zones.join(rounds, on=KEYS)
        .filter(
            (pl.col("share_pct") >= float(p["pos.recurring_death_share"]) * 100)
            & (pl.col("rounds") >= p["pos.recurring_min_rounds"])
        )
        .sort(*KEYS, "untraded_deaths", descending=[False, False, False, True])
    )


@metric(
    "pos.heatmap_points",
    version="1.0.0",
    name="Heatmap points",
    unit="table",
    kind="table",
    uses=("death", "kill"),
    doc="Raw kill and death positions per map and side (rendering comes in phase 2). "
    "Columns: `steamid`, `match_id`, `round`, `map`, `side`, `role` (`kill`, `death`), "
    "`zone`, `x`, `y`, `z`.",
)
def heatmap_points(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    columns = ["steamid", "match_id", "round", "map", "side", "role", "zone", "x", "y", "z"]
    kills = _kills(ds).select(
        *KEYS,
        "match_id",
        "round",
        pl.lit("kill").alias("role"),
        pl.col("attacker_place").alias("zone"),
        pl.col("attacker_x").alias("x"),
        pl.col("attacker_y").alias("y"),
        pl.col("attacker_z").alias("z"),
    )
    deaths = _deaths(ds).select(
        *KEYS,
        "match_id",
        "round",
        pl.lit("death").alias("role"),
        pl.col("victim_place").alias("zone"),
        pl.col("victim_x").alias("x"),
        pl.col("victim_y").alias("y"),
        pl.col("victim_z").alias("z"),
    )
    return pl.concat([kills.select(columns), deaths.select(columns)]).sort(
        "steamid", "match_id", "round"
    )
