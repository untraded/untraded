# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""§ 2 Duels, trades and clutches (docs/metrics-v1.md), from the round model (docs/round-model.md).

The round model stores trade delays and distances; the thresholds below are applied here.
"""

from __future__ import annotations

from collections.abc import Mapping

import polars as pl

from untraded.metrics._helpers import per_player, rate, rounds, total
from untraded.metrics.dataset import Dataset
from untraded.metrics.registry import ParamValue, metric

WINDOW = {"trade.window_s": 5.0}
WINDOW_W3 = {"trade.window_w3_s": 3.0}
OPPORTUNITY = {"trade.opportunity_distance": 1300.0}
ISOLATION = {"isolation.radius": 1000.0}
RP = ("round_player",)


def _count(ds: Dataset, rows: pl.DataFrame, player: str) -> pl.DataFrame:
    """Rows of the player's kept rounds, counted per player (column `player`)."""
    kept = ds.kept(rows, player=player)
    return per_player(
        ds, kept.group_by(pl.col(player).alias("steamid")).agg(pl.len().alias("value"))
    )


# Openings


@metric(
    "duel.opening_kills",
    version="1.0.0",
    name="Opening kills",
    unit="count",
    better="higher",
    uses=RP,
    doc="Rounds where the player makes the opening kill (first enemy kill after freeze end).",
)
def opening_kills(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return total(ds, "opening_kill")


@metric(
    "duel.opening_deaths",
    version="1.0.0",
    name="Opening deaths",
    unit="count",
    better="lower",
    uses=RP,
    doc="Rounds where the player is the opening victim.",
)
def opening_deaths(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return total(ds, "opening_death")


def _attempts(ds: Dataset) -> pl.DataFrame:
    kills, deaths = total(ds, "opening_kill"), total(ds, "opening_death")
    return kills.join(deaths, on="steamid", suffix="_d").select(
        "steamid", (pl.col("value") + pl.col("value_d")).alias("value")
    )


@metric(
    "duel.opening_attempts",
    version="1.0.0",
    name="Opening duels",
    unit="count",
    better="neutral",
    uses=RP,
    doc="Opening kills + opening deaths.",
)
def opening_attempts(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return _attempts(ds)


@metric(
    "duel.opening_success_pct",
    version="1.0.0",
    name="Opening success",
    unit="pct",
    better="higher",
    uses=RP,
    doc="Opening kills ÷ opening duels * 100.",
)
def opening_success_pct(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return rate(total(ds, "opening_kill"), _attempts(ds), scale=100.0)


@metric(
    "duel.opening_attempt_pct",
    version="1.0.0",
    name="Opening frequency",
    unit="pct",
    better="neutral",
    uses=RP,
    doc="Opening duels ÷ rounds played * 100.",
)
def opening_attempt_pct(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return rate(_attempts(ds), rounds(ds), scale=100.0)


@metric(
    "duel.opening_win_conversion_pct",
    version="1.0.0",
    name="Opening conversion",
    unit="pct",
    better="higher",
    uses=RP,
    doc="% of rounds with an opening kill by the player that the team wins.",
)
def opening_win_conversion_pct(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    opened = ds.round_players().filter(pl.col("opening_kill")).group_by("steamid")
    won = per_player(ds, opened.agg(pl.col("team_won").sum().alias("value")))
    return rate(won, per_player(ds, opened.agg(pl.len().alias("value"))), scale=100.0)


# Trades


def _trade_kills(ds: Dataset, window: ParamValue) -> pl.DataFrame:
    rows = ds["death"].filter(pl.col("is_enemy_kill") & (pl.col("avenges_delay_s") <= window))
    return _count(ds, rows, "killer")


def _traded_deaths(ds: Dataset, window: ParamValue) -> pl.DataFrame:
    return _count(ds, ds["death"].filter(pl.col("trade_delay_s") <= window), "victim")


def _untraded(ds: Dataset, window: ParamValue) -> pl.DataFrame:
    return (
        total(ds, "deaths")
        .join(_traded_deaths(ds, window), on="steamid", suffix="_t")
        .select("steamid", (pl.col("value") - pl.col("value_t")).alias("value"))
    )


def _trade_metrics(suffix: str, param: str, default: float) -> None:
    seconds = f"{default:g} s"
    params = {param: default}

    @metric(
        f"trade.trade_kills{suffix}",
        version="1.1.0",
        name=f"Trade kills ({seconds})",
        unit="count",
        better="higher",
        params=params,
        uses=("death",),
        doc=f"Kills of an enemy who killed a teammate of the player within `{param}` before.",
    )
    def trade_kills(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
        return _trade_kills(ds, p[param])

    @metric(
        f"trade.traded_deaths{suffix}",
        version="1.1.0",
        name=f"Traded deaths ({seconds})",
        unit="count",
        better="neutral",
        params=params,
        uses=("death",),
        doc=f"The player's deaths whose killer was killed by a teammate within `{param}`.",
    )
    def traded_deaths(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
        return _traded_deaths(ds, p[param])

    @metric(
        f"trade.traded_death_pct{suffix}",
        version="1.1.0",
        name=f"Traded death % ({seconds})",
        unit="pct",
        better="higher",
        params=params,
        uses=("death", "round_player"),
        doc="Traded deaths ÷ deaths * 100.",
    )
    def traded_death_pct(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
        return rate(_traded_deaths(ds, p[param]), total(ds, "deaths"), scale=100.0)

    @metric(
        f"trade.untraded_deaths{suffix}",
        version="1.1.0",
        name=f"Untraded deaths ({seconds})",
        unit="count",
        better="lower",
        params=params,
        uses=("death", "round_player"),
        doc="Deaths - traded deaths (the product's signature metric).",
    )
    def untraded_deaths(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
        return _untraded(ds, p[param])


_trade_metrics("", "trade.window_s", WINDOW["trade.window_s"])
_trade_metrics("_w3", "trade.window_w3_s", WINDOW_W3["trade.window_w3_s"])


def _opportunities(ds: Dataset, distance: ParamValue) -> pl.DataFrame:
    rows = ds["trade_opportunity"].filter(pl.col("distance_to_killer") <= distance)
    return _count(ds, rows, "teammate")


@metric(
    "trade.kill_opportunities",
    version="1.1.0",
    name="Trade opportunities",
    unit="count",
    better="neutral",
    params=OPPORTUNITY,
    uses=("trade_opportunity",),
    doc="Times a teammate of the player was killed while the player was alive and within "
    "`trade.opportunity_distance` of the killer.",
)
def kill_opportunities(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    return _opportunities(ds, p["trade.opportunity_distance"])


@metric(
    "trade.kill_conversion_pct",
    version="1.2.0",
    name="Opportunity conversion",
    unit="pct",
    better="higher",
    params={**WINDOW, **OPPORTUNITY},
    uses=("death", "trade_opportunity"),
    doc="Trade kills ÷ trade opportunities * 100.",
)
def kill_conversion_pct(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    return rate(
        _trade_kills(ds, p["trade.window_s"]),
        _opportunities(ds, p["trade.opportunity_distance"]),
        scale=100.0,
    )


@metric(
    "trade.death_opportunities",
    version="1.1.0",
    name="Tradable deaths",
    unit="count",
    better="neutral",
    params=OPPORTUNITY,
    uses=("trade_opportunity",),
    doc="The player's deaths where at least one teammate had a trade opportunity.",
)
def death_opportunities(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    tradable = (
        ds["trade_opportunity"]
        .filter(pl.col("distance_to_killer") <= p["trade.opportunity_distance"])
        .select("match_id", "round", "tick", "victim")
        .unique()
    )
    return _count(ds, tradable, "victim")


# Spacing


def _isolated(ds: Dataset, window: ParamValue, radius: ParamValue) -> pl.DataFrame:
    rows = ds["death"].filter(
        (pl.col("trade_delay_s").is_null() | (pl.col("trade_delay_s") > window))
        & (pl.col("nearest_teammate_distance") > radius)
    )
    return _count(ds, rows, "victim")


ISOLATION_DOC = (
    "**Untraded** deaths where the nearest living teammate was more than `isolation.radius` away. "
    "A death with no living teammate (last player alive) is not isolated."
)


@metric(
    "duel.isolated_deaths",
    version="1.1.0",
    name="Isolated deaths",
    unit="count",
    better="lower",
    params={**WINDOW, **ISOLATION},
    uses=("death",),
    doc=ISOLATION_DOC,
)
def isolated_deaths(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    return _isolated(ds, p["trade.window_s"], p["isolation.radius"])


@metric(
    "duel.isolated_death_pct",
    version="1.1.0",
    name="Isolated death %",
    unit="pct",
    better="lower",
    params={**WINDOW, **ISOLATION},
    uses=("death", "round_player"),
    doc="Isolated deaths ÷ deaths * 100.",
)
def isolated_death_pct(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    return rate(
        _isolated(ds, p["trade.window_s"], p["isolation.radius"]), total(ds, "deaths"), scale=100.0
    )


@metric(
    "duel.nearest_teammate_at_death",
    version="1.0.0",
    name="Spacing at death",
    unit="units",
    better="lower",
    uses=("death",),
    doc="Median, over deaths with a living teammate, of the distance to the nearest one.",
)
def nearest_teammate_at_death(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    deaths = ds.kept(ds["death"].drop_nulls("nearest_teammate_distance"), player="victim")
    median = deaths.group_by(pl.col("victim").alias("steamid")).agg(
        pl.col("nearest_teammate_distance").median().alias("value")
    )
    return per_player(ds, median, fill=None)


# Clutches


def _clutches(ds: Dataset) -> pl.DataFrame:
    return ds.kept(ds["clutch"])


def _clutch_metrics(enemies: int) -> None:
    @metric(
        f"clutch.attempts_1v{enemies}",
        version="1.1.0",
        name=f"1v{enemies} attempts",
        unit="count",
        better="neutral",
        uses=("clutch",),
        doc=f"Rounds where the player becomes the last one alive on the team, facing "
        f"{enemies} living enem{'ies' if enemies > 1 else 'y'}.",
    )
    def attempts(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
        rows = _clutches(ds).filter(pl.col("enemies") == enemies)
        return per_player(ds, rows.group_by("steamid").agg(pl.len().alias("value")))

    @metric(
        f"clutch.wins_1v{enemies}",
        version="1.1.0",
        name=f"1v{enemies} wins",
        unit="count",
        better="higher",
        uses=("clutch",),
        doc=f"1v{enemies} clutches the team wins.",
    )
    def wins(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
        rows = _clutches(ds).filter((pl.col("enemies") == enemies) & pl.col("won"))
        return per_player(ds, rows.group_by("steamid").agg(pl.len().alias("value")))


for _enemies in range(1, 6):
    _clutch_metrics(_enemies)


@metric(
    "clutch.win_pct",
    version="1.1.0",
    name="Clutch success",
    unit="pct",
    better="higher",
    uses=("clutch",),
    doc="Clutch wins ÷ clutch attempts * 100, over all N.",
)
def clutch_win_pct(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    by_player = _clutches(ds).group_by("steamid")
    wins = per_player(ds, by_player.agg(pl.col("won").sum().alias("value")))
    return rate(wins, per_player(ds, by_player.agg(pl.len().alias("value"))), scale=100.0)
