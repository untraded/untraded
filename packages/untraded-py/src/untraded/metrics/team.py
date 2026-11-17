# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""§ 6b Team metrics (docs/metrics-v1.md): one side of a match (`team` A or B), not a player.

A team metric returns counts, never rates: `match_id`, `team`, `key`, `sub_key`, `cases` and
`hits` (the rate is hits ÷ cases). Counts add up, so a rate over many matches is recomputed over
all their rounds, never averaged per match (metrics-v1 § 0). Which team a side belongs to is
decided when the numbers are read (the roster on the match's date), so nothing here depends on
it.

Only rounds whose winner is known count: a last round cut by the end of the demo is left out. A
bomb planted once the round was decided does not count as a plant.
Team metrics read whole matches: `Dataset.split` does not apply to them.
"""

from __future__ import annotations

from collections.abc import Mapping

import polars as pl

from untraded.metrics.dataset import Dataset
from untraded.metrics.registry import ParamValue, metric

TEAM_COLUMNS = pl.Schema(
    {
        "match_id": pl.String,
        "team": pl.String,
        "key": pl.String,
        "sub_key": pl.String,
        "cases": pl.Int64,
        "hits": pl.Int64,
    }
)
"""What every team metric returns, in this order."""
NO_PLANT = "none"
UNKNOWN_SITE = "unknown"
"""A plant whose site the planter's place does not name (`round.bomb_site` empty)."""


def _rounds(ds: Dataset) -> pl.DataFrame:
    """Rounds with a known winner, teams as strings. A plant after the round was decided (the
    last defender killed, then the bomb planted) is no plant: it changed nothing (as in the
    ledger, `untraded.winprob.ledger`)."""
    rounds = ds["round"].filter(pl.col("winner_team").is_not_null())
    over = pl.min_horizontal(
        *(c for c in ("end_tick", "bomb_defused_tick", "bomb_exploded_tick") if c in rounds.columns)
    )
    planted = pl.col("bomb_planted_tick").is_not_null() & (pl.col("bomb_planted_tick") < over)
    return rounds.select(
        "match_id",
        "round",
        pl.col("winner_team").cast(pl.String),
        pl.col("ct_team").cast(pl.String),
        pl.col("t_team").cast(pl.String),
        pl.when(planted).then(pl.col("bomb_planted_tick")).alias("bomb_planted_tick"),
        pl.when(planted).then(pl.col("bomb_site").cast(pl.String)).alias("bomb_site"),
    )


def _counts(rows: pl.DataFrame, *, hit: pl.Expr) -> pl.DataFrame:
    """`cases` (rows) and `hits` per match, team, key and sub-key."""
    return (
        rows.group_by("match_id", "team", "key", "sub_key")
        .agg(pl.len().cast(pl.Int64).alias("cases"), hit.sum().cast(pl.Int64).alias("hits"))
        .select(TEAM_COLUMNS.names())
        .cast(TEAM_COLUMNS)
        .sort("match_id", "team", "key", "sub_key")
    )


def _site() -> pl.Expr:
    return pl.col("bomb_site").fill_null(UNKNOWN_SITE)


@metric(
    "team.site_t",
    version="1.0.0",
    name="T rounds by site",
    unit="table",
    better="higher",
    kind="team",
    uses=("round",),
    doc="Rounds the team played on T, by the site of the plant (`key`: `A`, `B`, `none` without "
    "a plant, `unknown` when the planter's place names no site): `cases` rounds, `hits` won. A "
    "bomb planted after the round was decided is no plant.",
)
def site_t(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    rows = _rounds(ds).select(
        "match_id",
        pl.col("t_team").alias("team"),
        pl.when(pl.col("bomb_planted_tick").is_null())
        .then(pl.lit(NO_PLANT))
        .otherwise(_site())
        .alias("key"),
        pl.lit("").alias("sub_key"),
        (pl.col("winner_team") == pl.col("t_team")).alias("won"),
    )
    return _counts(rows, hit=pl.col("won"))


def _alive_at_plant(ds: Dataset) -> pl.DataFrame:
    """Planted rounds with the players alive on each side at the plant: `alive_ct`, `alive_t`.

    Alive = players present in the round (`round_player`) minus those of them dead at the plant's
    tick or before. A bot's death is not counted (it is not a present player)."""
    planted = _rounds(ds).filter(pl.col("bomb_planted_tick").is_not_null())
    present = ds["round_player"].select(
        "match_id", "round", "steamid", pl.col("team").cast(pl.String)
    )
    deaths = (
        ds["death"]
        .select("match_id", "round", pl.col("victim").alias("steamid"), "tick")
        .join(present, on=["match_id", "round", "steamid"])
        .join(planted.select("match_id", "round", "bomb_planted_tick"), on=["match_id", "round"])
        .filter(pl.col("tick") <= pl.col("bomb_planted_tick"))
        .group_by("match_id", "round", "team")
        .agg(pl.len().alias("dead"))
    )
    alive = (
        present.group_by("match_id", "round", "team")
        .agg(pl.len().alias("present"))
        .join(deaths, on=["match_id", "round", "team"], how="left")
        .select(
            "match_id",
            "round",
            "team",
            (pl.col("present") - pl.col("dead").fill_null(0)).clip(lower_bound=0).alias("alive"),
        )
    )
    for side in ("ct", "t"):
        planted = planted.join(
            alive.rename({"team": f"{side}_team", "alive": f"alive_{side}"}),
            on=["match_id", "round", f"{side}_team"],
            how="left",
        ).with_columns(pl.col(f"alive_{side}").fill_null(0))
    return planted


def _plant_rows(ds: Dataset, side: str) -> pl.DataFrame:
    us, them = ("t", "ct") if side == "T" else ("ct", "t")
    rows = _alive_at_plant(ds).select(
        "match_id",
        pl.col(f"{us}_team").alias("team"),
        _site().alias("key"),
        pl.format("{}v{}", pl.col(f"alive_{us}"), pl.col(f"alive_{them}")).alias("sub_key"),
        (pl.col("winner_team") == pl.col(f"{us}_team")).alias("won"),
    )
    return _counts(rows, hit=pl.col("won"))


@metric(
    "team.post_plant",
    version="1.0.0",
    name="Post-plants",
    unit="table",
    better="higher",
    kind="team",
    uses=("round", "round_player", "death"),
    doc="Rounds the team played on T with the bomb planted, by site (`key`: `A`, `B` or "
    "`unknown`) and by the players alive at the plant (`sub_key`: `{us}v{them}`, e.g. `3v2`): "
    "`cases` rounds, `hits` won.",
)
def post_plant(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return _plant_rows(ds, "T")


@metric(
    "team.retake",
    version="1.0.0",
    name="Retakes",
    unit="table",
    better="higher",
    kind="team",
    uses=("round", "round_player", "death"),
    doc="Rounds the team played on CT where the enemy planted the bomb, by site (`key`: `A`, `B` "
    "or `unknown`) and by the players alive at the plant (`sub_key`: `{us}v{them}`): `cases` "
    "rounds, `hits` won.",
)
def retake(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return _plant_rows(ds, "CT")


@metric(
    "team.buy",
    version="1.0.0",
    name="Rounds by buy type",
    unit="table",
    better="higher",
    kind="team",
    uses=("team_round", "round"),
    doc="Rounds by the team's buy type (`key`: `pistol`, `eco`, `semi`, `force`, `full`, from the "
    "round model) and the enemy's (`sub_key`): `cases` rounds, `hits` won.",
)
def buy(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    rounds = _rounds(ds).select("match_id", "round", "winner_team")
    buys = ds["team_round"].select(
        "match_id",
        "round",
        pl.col("team").cast(pl.String),
        pl.col("buy_type").cast(pl.String).alias("key"),
    )
    enemy = buys.rename({"team": "enemy", "key": "sub_key"})
    rows = (
        buys.join(rounds, on=["match_id", "round"])
        .join(enemy, on=["match_id", "round"])
        .filter(pl.col("team") != pl.col("enemy"))
        .with_columns(pl.col("key").fill_null(""), pl.col("sub_key").fill_null(""))
    )
    return _counts(rows, hit=pl.col("winner_team") == pl.col("team"))


@metric(
    "team.trades",
    version="1.0.0",
    name="Trade network",
    unit="table",
    better="higher",
    kind="team",
    uses=("death", "round_player", "round"),
    params={"trade.window_s": 5.0},
    doc="Who trades whose death. For each player of the team (`key`, a SteamID): their deaths "
    "(`cases`, every death as in `trade.traded_death_pct`, in the rounds with a known winner) "
    "and the deaths traded within `trade.window_s` (`hits`), in total (`sub_key` empty) and by "
    "the teammate who traded them (`sub_key`, a SteamID). A death is traded when a teammate "
    "kills the killer within the window (the `death` table, built from `kill`).",
)
def trades(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    window = float(p["trade.window_s"])
    present = ds["round_player"].select(
        "match_id", "round", "steamid", pl.col("team").cast(pl.String)
    )
    deaths = (
        ds["death"]
        .join(_rounds(ds).select("match_id", "round"), on=["match_id", "round"], how="semi")
        .select("match_id", "round", pl.col("victim").alias("steamid"), "trade_delay_s", "trader")
        # A present player's death: a bot's is nobody's (metrics-v1 § 0).
        .join(present, on=["match_id", "round", "steamid"])
        .with_columns((pl.col("trade_delay_s") <= window).fill_null(False).alias("traded"))
    )
    total = _counts(
        deaths.select(
            "match_id",
            "team",
            pl.col("steamid").cast(pl.String).alias("key"),
            pl.lit("").alias("sub_key"),
            "traded",
        ),
        hit=pl.col("traded"),
    )
    # The trader is a present teammate (a bot of the team trades the death, but links nobody).
    by_trader = (
        deaths.filter(pl.col("traded"))
        .join(
            present.rename({"steamid": "trader", "team": "trader_team"}),
            on=["match_id", "round", "trader"],
        )
        .filter(pl.col("trader_team") == pl.col("team"))
        .group_by(
            "match_id",
            "team",
            pl.col("steamid").cast(pl.String).alias("key"),
            pl.col("trader").cast(pl.String).alias("sub_key"),
        )
        .agg(pl.len().cast(pl.Int64).alias("hits"))
        .join(
            total.select("match_id", "team", "key", "cases"),
            on=["match_id", "team", "key"],
        )
        .select(TEAM_COLUMNS.names())
    )
    return pl.concat([total, by_trader.cast(TEAM_COLUMNS)]).sort(
        "match_id", "team", "key", "sub_key"
    )
