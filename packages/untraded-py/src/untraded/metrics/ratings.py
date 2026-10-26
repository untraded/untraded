# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""§ 6 Ratings (docs/metrics-v1.md), from the per-round totals of the round model.

The formulas live in `untraded.ratings`, the public functions on match totals: the metrics only
gather those totals, so both always agree.
"""

from __future__ import annotations

from collections.abc import Mapping

import polars as pl

from untraded.metrics._helpers import per_player
from untraded.metrics.base import kast_round
from untraded.metrics.dataset import Dataset
from untraded.metrics.registry import ROUNDS, ParamValue, metric
from untraded.ratings import rating_hltv_1, rating_hltv_2_approx

KAST = {"trade.window_s": 5.0, "kast.count_flash_assist": False}


def _totals(ds: Dataset, params: Mapping[str, ParamValue] | None = None) -> pl.DataFrame:
    extra = [kast_round(params).sum().alias("kast_rounds")] if params is not None else []
    return (
        ds.round_players()
        .group_by("steamid")
        .agg(
            pl.len().alias("rounds"),
            pl.col("kills").sum(),
            pl.col("deaths").sum(),
            pl.col("assists").sum(),
            pl.col("damage").sum(),
            *[(pl.col("kills") == n).sum().alias(f"k{n}") for n in range(1, 6)],
            *extra,
        )
    )


@metric(
    "rating.hltv1",
    version="1.0.0",
    name="HLTV Rating 1.0",
    unit="ratio",
    better="higher",
    cases=(ROUNDS,),
    uses=("round_player",),
    doc="(KillRating + 0.7 * SurvivalRating + MultiKillRating) / 2.7, each component being the "
    "player's per-round value over HLTV's reference average (KPR 0.679, survival 0.317, "
    "multi-kill points 1.277, with N² points for a round of N kills). Public formula.",
)
def hltv1(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    rows = _totals(ds).to_dicts()
    values = [
        {
            "steamid": r["steamid"],
            "value": rating_hltv_1(
                r["rounds"], r["kills"], r["deaths"], {n: r[f"k{n}"] for n in range(1, 6)}
            ),
        }
        for r in rows
    ]
    return per_player(ds, _frame(values), fill=None)


@metric(
    "rating.hltv2_approx",
    version="1.1.0",
    name="HLTV 2.0 (approx.)",
    unit="ratio",
    better="higher",
    cases=(ROUNDS,),
    params=KAST,
    uses=("round_player",),
    doc="Community approximation, **always labeled approx.**: 0.0073 * KAST + 0.3591 * KPR - "
    "0.5329 * DPR + 0.2372 * Impact + 0.0032 * ADR + 0.1587, with Impact = 2.13 * KPR + "
    "0.42 * APR - 0.41 and KAST in % (`base.kast`, same parameters). Its error against "
    "HLTV's published values is not known.",
)
def hltv2_approx(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    rows = _totals(ds, p).to_dicts()
    values = [
        {
            "steamid": r["steamid"],
            "value": rating_hltv_2_approx(
                r["rounds"], r["kills"], r["deaths"], r["assists"], r["damage"], r["kast_rounds"]
            ),
        }
        for r in rows
    ]
    return per_player(ds, _frame(values), fill=None)


def _frame(values: list[dict[str, float]]) -> pl.DataFrame:
    return pl.DataFrame(values, schema={"steamid": pl.UInt64, "value": pl.Float64})


@metric(
    "rating.swing",
    version="1.1.0",
    name="Win-probability swing",
    unit="pct",
    better="higher",
    cases=(ROUNDS,),
    signed=True,
    uses=("swing", "round_player"),
    doc="The player's swings (`swing` table: how much each of their kills, deaths, plants and "
    "defuses moved their team's chance of winning the round, by the open win-probability "
    "model 1.0, docs/winprob.md), summed and divided by the rounds played, in percentage "
    "points. 0 is a player whose actions moved nothing on balance.",
)
def swing(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    if "swing" not in ds.tables:  # tables derived before the swing existed
        return per_player(ds, _frame([]), fill=None)
    credits = ds.kept(ds["swing"])
    # Only the matches that have swings: one derived before them has no row at all.
    rounds = (
        ds.played.join(credits.select("match_id").unique(), on="match_id", how="semi")
        .group_by("steamid")
        .agg(pl.len().alias("rounds"))
    )
    gained = credits.group_by("steamid").agg(pl.col("swing").cast(pl.Float64).sum())
    values = rounds.join(gained, on="steamid", how="left").select(
        "steamid", (pl.col("swing").fill_null(0.0) * 100 / pl.col("rounds")).alias("value")
    )
    return per_player(ds, values, fill=None)
