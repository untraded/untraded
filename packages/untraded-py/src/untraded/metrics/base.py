# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""§ 1 Base (docs/metrics-v1.md)."""

from __future__ import annotations

from collections.abc import Mapping

import polars as pl

from untraded.metrics._helpers import per_player, rate, round_share, rounds, total
from untraded.metrics.dataset import Dataset
from untraded.metrics.registry import ParamValue, metric

RP = ("round_player",)


@metric(
    "base.kills",
    version="1.0.0",
    name="Kills",
    unit="count",
    better="higher",
    uses=RP,
    doc="Number of kills (enemy kills only).",
)
def kills(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return total(ds, "kills")


@metric(
    "base.deaths",
    version="1.0.0",
    name="Deaths",
    unit="count",
    better="lower",
    uses=RP,
    doc="Number of deaths: by an enemy, a teammate, suicide, fall damage or the bomb.",
)
def deaths(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return total(ds, "deaths")


@metric(
    "base.assists",
    version="1.0.0",
    name="Assists",
    unit="count",
    better="higher",
    uses=RP,
    doc="Enemy kills where the player is the assister, flash assists excluded.",
)
def assists(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return total(ds, "assists")


@metric(
    "base.flash_assists",
    version="1.0.0",
    name="Flash assists",
    unit="count",
    better="higher",
    uses=RP,
    doc="Enemy kills with `assistedflash` credited to the player.",
)
def flash_assists(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return total(ds, "flash_assists")


@metric(
    "base.assist_score",
    version="1.0.0",
    name="Weighted assists",
    unit="count",
    better="higher",
    uses=RP,
    params={"assist.flash_weight": 0.5},
    doc="Assists + `assist.flash_weight` * flash assists: a flash assist counts, but less "
    "than an assist.",
)
def assist_score(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    return (
        total(ds, "assists")
        .join(total(ds, "flash_assists"), on="steamid", suffix="_f")
        .select(
            "steamid",
            (pl.col("value") + float(p["assist.flash_weight"]) * pl.col("value_f")).alias("value"),
        )
    )


def _kill_flag(ds: Dataset, flag: str) -> pl.DataFrame:
    rows = ds.kept(ds["kill"].filter(pl.col(flag)), player="attacker")
    return per_player(
        ds, rows.group_by(pl.col("attacker").alias("steamid")).agg(pl.len().alias("value"))
    )


@metric(
    "base.team_kills",
    version="1.0.0",
    name="Team kills",
    unit="count",
    better="lower",
    uses=("kill",),
    doc="Teammates killed by the player.",
)
def team_kills(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return _kill_flag(ds, "is_team_kill")


@metric(
    "base.suicides",
    version="1.0.0",
    name="Suicides",
    unit="count",
    better="lower",
    uses=("kill",),
    doc="Deaths where the player is both attacker and victim.",
)
def suicides(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return _kill_flag(ds, "is_suicide")


@metric(
    "base.kd_diff",
    version="1.0.0",
    name="K-D",
    unit="count",
    better="higher",
    uses=RP,
    doc="kills - deaths.",
)
def kd_diff(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return (
        total(ds, "kills")
        .join(total(ds, "deaths"), on="steamid", suffix="_deaths")
        .select("steamid", (pl.col("value") - pl.col("value_deaths")).alias("value"))
    )


@metric(
    "base.kpr",
    version="1.0.0",
    name="Kills per round",
    unit="per_round",
    better="higher",
    uses=RP,
    doc="Kills ÷ rounds played.",
)
def kpr(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return rate(total(ds, "kills"), rounds(ds))


@metric(
    "base.dpr",
    version="1.0.0",
    name="Deaths per round",
    unit="per_round",
    better="lower",
    uses=RP,
    doc="Deaths ÷ rounds played.",
)
def dpr(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return rate(total(ds, "deaths"), rounds(ds))


@metric(
    "base.apr",
    version="1.0.0",
    name="Assists per round",
    unit="per_round",
    better="higher",
    uses=RP,
    doc="Assists ÷ rounds played.",
)
def apr(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return rate(total(ds, "assists"), rounds(ds))


@metric(
    "base.adr",
    version="1.0.0",
    name="ADR",
    unit="damage_per_round",
    better="higher",
    uses=RP,
    doc="Sum of capped damage to enemies ÷ rounds played.",
)
def adr(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return rate(total(ds, "damage"), rounds(ds))


@metric(
    "base.hs_pct",
    version="1.0.0",
    name="HS %",
    unit="pct",
    better="higher",
    uses=("death", "kill"),
    doc="Headshot kills ÷ kills * 100.",
)
def hs_pct(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    enemy = (
        ds["death"].filter(pl.col("is_enemy_kill")).select("match_id", "tick", "victim", "killer")
    )
    shots = ds.kept(
        enemy.join(
            ds["kill"].select("match_id", "tick", "victim", "round", "headshot"),
            on=["match_id", "tick", "victim"],
        ),
        player="killer",
    )
    by_player = shots.group_by(pl.col("killer").alias("steamid"))
    headshots = per_player(ds, by_player.agg(pl.col("headshot").sum().alias("value")))
    return rate(headshots, per_player(ds, by_player.agg(pl.len().alias("value"))), scale=100.0)


@metric(
    "base.kast",
    version="1.1.0",
    name="KAST",
    unit="pct",
    better="higher",
    uses=RP,
    params={"trade.window_s": 5.0, "kast.count_flash_assist": False},
    doc="% of rounds played where the player got a Kill, an Assist (flash assists excluded "
    "by default), Survived (alive at round end, no death after it), or was Traded (death "
    "traded within `trade.window_s`).",
)
def kast(ds: Dataset, params: Mapping[str, ParamValue]) -> pl.DataFrame:
    return round_share(ds, kast_round(params))


def kast_round(params: Mapping[str, ParamValue]) -> pl.Expr:
    """Whether a `round_player` row counts for KAST (also used by the HLTV 2.0 approximation)."""
    assisted = pl.col("assists") > 0
    if params["kast.count_flash_assist"]:
        assisted = assisted | (pl.col("flash_assists") > 0)
    traded = (pl.col("death_trade_delay_s") <= params["trade.window_s"]).fill_null(False)
    return (pl.col("kills") > 0) | assisted | pl.col("survived") | traded


def _multikill(count: int) -> None:
    @metric(
        f"base.multikills_{count}",
        version="1.0.0",
        name=f"{count}K",
        unit="count",
        # A 1K is also a round without a multi-kill: neither better nor worse.
        better="higher" if count > 1 else "neutral",
        uses=RP,
        doc=f"Number of rounds with exactly {count} kill{'s' if count > 1 else ''}.",
    )
    def multikills(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
        hits = (
            ds.round_players()
            .group_by("steamid")
            .agg((pl.col("kills") == count).sum().alias("value"))
        )
        return per_player(ds, hits)


for _count in range(1, 6):
    _multikill(_count)


@metric(
    "base.rounds_with_kill_pct",
    version="1.0.0",
    name="Rounds with a kill",
    unit="pct",
    better="higher",
    uses=RP,
    doc="% of rounds with at least one kill.",
)
def rounds_with_kill_pct(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return round_share(ds, pl.col("kills") > 0)


@metric(
    "base.survival_pct",
    version="1.1.0",
    name="Survival",
    unit="pct",
    better="higher",
    uses=RP,
    doc="% of rounds where the player is alive at round end and does not die after it (a death "
    "after the round end drops the weapons).",
)
def survival_pct(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return round_share(ds, pl.col("survived"))
