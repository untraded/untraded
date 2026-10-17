# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Shared building blocks of metric formulas."""

from __future__ import annotations

import polars as pl

from untraded.metrics.dataset import Dataset


def per_player(ds: Dataset, values: pl.DataFrame, *, fill: float | None = 0.0) -> pl.DataFrame:
    """Every player of the dataset with their `value`; players without a row get `fill`."""
    return (
        ds.players()
        .join(values.select("steamid", pl.col("value").cast(pl.Float64)), on="steamid", how="left")
        .with_columns(pl.col("value").fill_null(fill) if fill is not None else pl.col("value"))
    )


def total(ds: Dataset, column: str) -> pl.DataFrame:
    """Sum of a `round_player` column over the kept rounds."""
    return per_player(
        ds, ds.round_players().group_by("steamid").agg(pl.col(column).sum().alias("value"))
    )


def rate(numerator: pl.DataFrame, denominator: pl.DataFrame, *, scale: float = 1.0) -> pl.DataFrame:
    """numerator / denominator * scale per player; null when the denominator is 0."""
    return numerator.join(denominator, on="steamid", suffix="_den").select(
        "steamid",
        pl.when(pl.col("value_den") > 0)
        .then(pl.col("value") / pl.col("value_den") * scale)
        .otherwise(None)
        .alias("value"),
    )


def rounds(ds: Dataset) -> pl.DataFrame:
    return per_player(ds, ds.rounds_played().rename({"rounds": "value"}))


def round_share(ds: Dataset, condition: pl.Expr) -> pl.DataFrame:
    """% of the kept rounds where `condition` holds (on `round_player` columns)."""
    hits = ds.round_players().group_by("steamid").agg(condition.sum().alias("value"))
    return rate(per_player(ds, hits), rounds(ds), scale=100.0)
