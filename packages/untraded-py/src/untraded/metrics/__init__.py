# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Metrics (workstream E5): a versioned registry (ADR 0003) with explicit parameters (ADR 0007).

    ds = Dataset.from_matches([{**canonical.tables(), **derive(canonical.tables()).tables()}])
    compute(ds)                    # every metric, default parameters
    compute(ds.split(side="CT"))   # CT rounds only
    compute_team(ds)               # team metrics: counts per side of each match

Results record each metric's version and the parameter values used.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping

import polars as pl

from untraded.metrics import base as _base  # noqa: F401 (registers the metrics)
from untraded.metrics import duels as _duels  # noqa: F401
from untraded.metrics import economy as _economy  # noqa: F401
from untraded.metrics import positioning as _positioning  # noqa: F401
from untraded.metrics import ratings as _ratings  # noqa: F401
from untraded.metrics import team as _team  # noqa: F401
from untraded.metrics import utility as _utility  # noqa: F401
from untraded.metrics.dataset import Dataset
from untraded.metrics.registry import REGISTRY, Metric, ParamValue, metric

__all__ = ["REGISTRY", "Dataset", "Metric", "compute", "compute_table", "compute_team", "metric"]

RESULT = pl.Schema(
    {
        "steamid": pl.UInt64,
        "metric": pl.String,
        "version": pl.String,
        "value": pl.Float64,
        "params": pl.String,
    }
)


TEAM_RESULT = pl.Schema(
    {
        "match_id": pl.String,
        "team": pl.String,
        "metric": pl.String,
        "version": pl.String,
        "params": pl.String,
        "key": pl.String,
        "sub_key": pl.String,
        "cases": pl.Int64,
        "hits": pl.Int64,
    }
)


def _params(definition: Metric, overrides: Mapping[str, ParamValue]) -> dict[str, ParamValue]:
    return {name: overrides.get(name, default) for name, default in definition.params.items()}


def _check_params(overrides: Mapping[str, ParamValue]) -> None:
    unknown = set(overrides) - {name for m in REGISTRY.values() for name in m.params}
    if unknown:
        raise ValueError(f"unknown parameters: {sorted(unknown)}")


def compute(
    ds: Dataset,
    ids: Iterable[str] | None = None,
    *,
    params: Mapping[str, ParamValue] | None = None,
) -> pl.DataFrame:
    """Long table of the `value` metrics: one row per player and metric, with its version and
    parameters (JSON).

    `params` overrides defaults by name (e.g. `{"trade.window_s": 3.0}`) for every metric that
    declares that parameter.
    """
    overrides = dict(params or {})
    _check_params(overrides)
    wanted = (
        list(ids)
        if ids is not None
        else sorted(m.id for m in REGISTRY.values() if m.kind == "value")
    )
    frames = []
    for metric_id in wanted:
        definition = REGISTRY[metric_id]
        if definition.kind != "value":
            kind = definition.kind
            raise ValueError(f"{metric_id} is a {kind} metric: use compute_{kind}()")
        used = _params(definition, overrides)
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


def compute_table(
    ds: Dataset, metric_id: str, *, params: Mapping[str, ParamValue] | None = None
) -> pl.DataFrame:
    """A `table` metric, with `metric`, `version` and `params` columns added."""
    overrides = dict(params or {})
    _check_params(overrides)
    definition = REGISTRY[metric_id]
    if definition.kind != "table":
        use = "compute" if definition.kind == "value" else f"compute_{definition.kind}"
        raise ValueError(f"{metric_id} is a {definition.kind} metric: use {use}()")
    used = _params(definition, overrides)
    return definition.compute(ds, used).with_columns(
        pl.lit(metric_id).alias("metric"),
        pl.lit(definition.version).alias("version"),
        pl.lit(json.dumps(used, sort_keys=True)).alias("params"),
    )


def compute_team(
    ds: Dataset,
    ids: Iterable[str] | None = None,
    *,
    params: Mapping[str, ParamValue] | None = None,
) -> pl.DataFrame:
    """Long table of the `team` metrics: `match_id`, `team`, `metric`, `version`, `params`,
    `key`, `sub_key`, `cases` and `hits` (`untraded.metrics.team`)."""
    overrides = dict(params or {})
    _check_params(overrides)
    team = sorted(m.id for m in REGISTRY.values() if m.kind == "team")
    wanted = list(ids) if ids is not None else team
    frames = []
    for metric_id in wanted:
        definition = REGISTRY[metric_id]
        if definition.kind != "team":
            raise ValueError(f"{metric_id} is not a team metric")
        used = _params(definition, overrides)
        frames.append(
            definition.compute(ds, used).select(
                "match_id",
                "team",
                pl.lit(metric_id).alias("metric"),
                pl.lit(definition.version).alias("version"),
                pl.lit(json.dumps(used, sort_keys=True)).alias("params"),
                "key",
                "sub_key",
                "cases",
                "hits",
            )
        )
    if not frames:
        return pl.DataFrame(schema=TEAM_RESULT)
    return pl.concat(frames).sort("metric", "match_id", "team", "key", "sub_key")
