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
from untraded.winprob.rating import Z95
from untraded.winprob.rating2 import default_rating

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


RATING_PARTS = ("shooting", "utility", "trade", "objective", "taken", "team")
"""The ledger's parts the match rating adds up from (the hold is left out, docs/winprob.md)."""


def _ledger_rounds(ds: Dataset) -> pl.DataFrame | None:
    """Every player's ledger credit in every round with a ledger, in percentage points, the hold
    left out and recentred so that the round's players average zero (`untraded.winprob.rating2`):
    `match_id`, `round`, `steamid`, `credit`, one column per `RATING_PARTS` and `balance` (the
    recentring), which add up to `credit`. Only the player's kept rounds. None without a ledger
    (tables derived before it existed)."""
    if "ledger" not in ds.tables:
        return None
    ledger = ds["ledger"].filter(pl.col("part").cast(pl.String) != "hold")
    rounds = ds["ledger"].select("match_id", "round").unique()
    players = (
        ds["round_player"]
        .select("match_id", "round", "steamid")
        .join(rounds, on=["match_id", "round"], how="semi")
    )
    parts = (
        ledger.with_columns(pl.col("part").cast(pl.String))
        .group_by("match_id", "round", "steamid", "part")
        .agg((pl.col("credit").sum() * 100).alias("points"))
        .pivot("part", index=["match_id", "round", "steamid"], values="points")
    )
    for part in RATING_PARTS:
        if part not in parts.columns:
            parts = parts.with_columns(pl.lit(0.0).alias(part))
    per = (
        players.join(parts, on=["match_id", "round", "steamid"], how="left")
        .with_columns(pl.col(p).cast(pl.Float64).fill_null(0.0) for p in RATING_PARTS)
        .with_columns(pl.sum_horizontal(*RATING_PARTS).alias("raw"))
        .with_columns((-pl.col("raw").mean().over("match_id", "round")).alias("balance"))
        .with_columns((pl.col("raw") + pl.col("balance")).alias("credit"))
        .drop("raw")
    )
    return ds.kept(per)


_UNTRADED_DOC = (
    "The match rating: 1 + credit / s, the credit being the player's ledger credit per round "
    "played (docs/winprob.md: every change of the round's win probability credited, the hold "
    "left out and each round recentred so that its players average zero), in percentage points. "
    "s is the credit worth 1.00, chosen so that the rating spreads over the corpus's "
    "player-matches as HLTV 1.0 does (`rating-v2.json`): 1.00 is the average player of the "
    "match, a 1.20 reads as at HLTV. What the player's actions were worth; "
    "`rating.untraded_level` says what the player is worth. Beta: measured on 54 high-level "
    "matches."
)


@metric(
    "rating.untraded",
    version="2.0.0",
    name="Untraded Rating",
    unit="ratio",
    better="higher",
    cases=(ROUNDS,),
    uses=("ledger", "round_player"),
    doc=_UNTRADED_DOC,
)
def untraded(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    rounds = _ledger_rounds(ds)
    if rounds is None:  # tables derived before the ledger: no value, rather than a wrong one
        return per_player(ds, _frame([]), fill=None)
    s = default_rating().points_per_rating
    values = rounds.group_by("steamid").agg((1 + pl.col("credit").mean() / s).alias("value"))
    return per_player(ds, values, fill=None)


@metric(
    "rating.untraded_level",
    version="1.0.0",
    name="Untraded Rating level",
    unit="ratio",
    better="higher",
    cases=(ROUNDS,),
    uses=("ledger", "round_player"),
    doc="The level: what the player is worth, on the scale of `rating.untraded` (1.00 = the "
    "average player). A ridge regression of the ledger's credit on kills, deaths and damage per "
    "round, trained to predict the credit of rounds it has not seen (`rating-v2.json`), centred "
    "on each match's players; the ledger's credit then corrects it by n / (n + k) as rounds add "
    "up (on 54 matches the box alone predicted best, so k is not set yet and the level is the "
    "box). Closer to 1.00 than the match rating, as an estimate should be. Over several matches, "
    "the round-weighted average of each match's level.",
)
def untraded_level(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    rounds = _ledger_rounds(ds)
    if rounds is None:
        return per_player(ds, _frame([]), fill=None)
    rating = default_rating()
    stats = ds.round_players().select(
        "match_id",
        "round",
        "steamid",
        pl.col("kills").cast(pl.Float64).alias("kpr"),
        pl.col("deaths").cast(pl.Float64).alias("dpr"),
        (pl.col("damage").cast(pl.Float64) / 100).alias("adr"),
    )
    per_match = (
        rounds.join(stats, on=["match_id", "round", "steamid"])
        .group_by("match_id", "steamid")
        .agg(
            pl.len().alias("n"),
            pl.col("credit").mean(),
            *(pl.col(f).mean() for f in rating.box.features),
        )
    )
    if per_match.is_empty():
        return per_player(ds, _frame([]), fill=None)
    box = rating.box.predict(per_match.select(rating.box.features).to_numpy())
    per_match = per_match.with_columns(pl.Series("box", box)).with_columns(
        (
            pl.col("box")
            - (pl.col("box") * pl.col("n")).sum().over("match_id")
            / pl.col("n").sum().over("match_id")
        ).alias("box")
    )
    totals = per_match.group_by("steamid").agg(
        pl.col("n").sum(),
        ((pl.col("box") * pl.col("n")).sum() / pl.col("n").sum()).alias("box"),
        ((pl.col("credit") * pl.col("n")).sum() / pl.col("n").sum()).alias("credit"),
    )
    values = [
        {
            "steamid": row["steamid"],
            "value": 1
            + rating.level(row["box"], row["credit"], int(row["n"])) / rating.points_per_rating,
        }
        for row in totals.iter_rows(named=True)
    ]
    return per_player(ds, _frame(values), fill=None)


@metric(
    "rating.untraded_margin",
    version="2.0.0",
    name="Untraded Rating margin",
    unit="table",
    better="neutral",
    kind="table",
    uses=("ledger", "round_player"),
    doc="Half-width of the 95 % interval of `rating.untraded`: 1.96 x the standard deviation of "
    "the player's credit per round / sqrt(rounds) / s. A rating over few rounds is a rough one. "
    "Columns: `steamid`, `rounds`, `margin` (null under 2 rounds).",
)
def untraded_margin(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    schema = pl.Schema({"steamid": pl.UInt64, "rounds": pl.Int64, "margin": pl.Float64})
    rounds = _ledger_rounds(ds)
    if rounds is None:
        return pl.DataFrame(schema=schema)
    s = default_rating().points_per_rating
    spread = rounds.group_by("steamid").agg(
        pl.len().alias("rounds"), pl.col("credit").std().alias("sd")
    )
    return (
        spread.select(
            "steamid",
            "rounds",
            pl.when(pl.col("rounds") > 1)
            .then(Z95 * pl.col("sd") / pl.col("rounds").cast(pl.Float64).sqrt() / s)
            .alias("margin"),
        )
        .cast(schema)
        .sort("steamid")
    )


@metric(
    "rating.untraded_parts",
    version="2.0.0",
    name="Untraded Rating by action",
    unit="table",
    better="neutral",
    kind="table",
    uses=("ledger", "round_player"),
    doc="Where `rating.untraded` comes from, in rating points: `shooting` (damage and kills with "
    "guns, the player's shares of the kills they made or helped), `utility` (grenade damage and "
    "kills, flashes on the victims), `trade` (the share given back when a teammate trades the "
    "player's killer), `objective` (plants and defuses, and their cost to the other side), "
    "`taken` (damage and deaths suffered), `team` (harm to one's own side), `balance` (the "
    "recentring that keeps the round's average player at zero) and `baseline` (1.00), so that the "
    "parts add up to the rating. Columns: `steamid`, `part`, `points`.",
)
def untraded_parts(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    schema = pl.Schema({"steamid": pl.UInt64, "part": pl.String, "points": pl.Float64})
    rounds = _ledger_rounds(ds)
    if rounds is None or rounds.is_empty():
        return pl.DataFrame(schema=schema)
    s = default_rating().points_per_rating
    names = [*RATING_PARTS, "balance"]
    means = rounds.group_by("steamid").agg(pl.col(p).mean() / s for p in names)
    points = means.unpivot(index="steamid", on=names, variable_name="part", value_name="points")
    baseline = means.select(
        "steamid", pl.lit("baseline").alias("part"), pl.lit(1.0).alias("points")
    )
    return pl.concat([points, baseline]).cast(schema).sort("steamid", "part")
