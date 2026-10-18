# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Metrics (workstream E5): a versioned registry (ADR 0003) with explicit parameters (ADR 0007).

    ds = Dataset.from_matches([{**canonical.tables(), **derive(canonical.tables()).tables()}])
    compute(ds)                    # every metric, default parameters
    compute(ds.split(side="CT"))   # CT rounds only

Results record each metric's version and the parameter values used.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping

import polars as pl

from untraded.metrics import base as _base  # noqa: F401 (registers the metrics)
from untraded.metrics import duels as _duels  # noqa: F401
from untraded.metrics.dataset import Dataset
from untraded.metrics.registry import REGISTRY, Metric, ParamValue, metric

__all__ = ["REGISTRY", "Dataset", "Metric", "compute", "metric"]

RESULT = pl.Schema(
    {
        "steamid": pl.UInt64,
        "metric": pl.String,
        "version": pl.String,
        "value": pl.Float64,
        "params": pl.String,
    }
)


def compute(
    ds: Dataset,
    ids: Iterable[str] | None = None,
    *,
    params: Mapping[str, ParamValue] | None = None,
) -> pl.DataFrame:
    """Long table: one row per player and metric, with its version and parameters (JSON).

    `params` overrides defaults by name (e.g. `{"trade.window_s": 3.0}`) for every metric that
    declares that parameter.
    """
    overrides = dict(params or {})
    unknown = set(overrides) - {name for m in REGISTRY.values() for name in m.params}
    if unknown:
        raise ValueError(f"unknown parameters: {sorted(unknown)}")
    wanted = list(ids) if ids is not None else sorted(REGISTRY)
    frames = []
    for metric_id in wanted:
        definition = REGISTRY[metric_id]
        used = {name: overrides.get(name, default) for name, default in definition.params.items()}
        values = definition.compute(ds, used)
        frames.append(
            values.select(
                pl.col("steamid").cast(pl.UInt64),
                pl.lit(metric_id).alias("metric"),
                pl.lit(definition.version).alias("version"),
                pl.col("value").cast(pl.Float64),
                pl.lit(json.dumps(used, sort_keys=True)).alias("params"),
            )
        )
    if not frames:
        return pl.DataFrame(schema=RESULT)
    return pl.concat(frames).sort("metric", "steamid")
