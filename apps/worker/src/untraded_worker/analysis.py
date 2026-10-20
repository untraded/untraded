# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""One match, from its canonical tables to everything the worker stores: the round model and
the metrics, with their default parameters (no database here)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import polars as pl

from untraded.derive import derive
from untraded.metrics import REGISTRY, Dataset, compute, compute_table

SCOPES: dict[str, str | None] = {"match": None, "ct": "CT", "t": "T"}
"""SQL `metric_scope` -> the side the rounds are split on (metrics-v1 § 5)."""


@dataclass(frozen=True)
class Analysis:
    tables: dict[str, pl.DataFrame]
    """Canonical and derived tables: what goes to Parquet."""
    values: pl.DataFrame
    """`value` metrics: `scope`, `steamid`, `metric`, `version`, `value`."""
    table_values: dict[str, pl.DataFrame]
    """`table` metrics by id: `steamid` and the metric's own columns."""

    @property
    def match(self) -> dict[str, object]:
        return self.tables["match"].row(0, named=True)


def analyze(canonical: Mapping[str, pl.DataFrame]) -> Analysis:
    tables = {**canonical, **derive(canonical).tables()}
    dataset = Dataset.from_matches([tables])
    values = pl.concat(
        [
            compute(dataset if side is None else dataset.split(side=side)).select(
                pl.lit(scope).alias("scope"), "steamid", "metric", "version", "value"
            )
            for scope, side in SCOPES.items()
        ]
    )
    table_values = {
        m.id: compute_table(dataset, m.id).drop(
            "metric", "version", "params", "match_id", strict=False
        )
        for m in REGISTRY.values()
        if m.kind == "table"
    }
    return Analysis(tables=tables, values=values, table_values=table_values)
