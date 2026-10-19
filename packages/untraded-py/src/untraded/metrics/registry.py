# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The versioned metric registry (ADR 0003) with explicit parameters (ADR 0007)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Literal

import polars as pl

from untraded.metrics.dataset import Dataset

Unit = Literal[
    "count", "per_round", "pct", "damage_per_round", "ratio", "units", "seconds", "table"
]
Scope = Literal["player"]
Kind = Literal["value", "table"]
"""`value`: one number per player (`compute`). `table`: rows per player with dimensions such as
map, side and zone (`compute_table`), e.g. distributions and raw exports."""
ParamValue = float | int | bool
Compute = Callable[[Dataset, Mapping[str, ParamValue]], pl.DataFrame]
"""`value` metrics return one row per player: `steamid`, `value` (Float64, null when undefined).
`table` metrics return `steamid` plus their own columns, documented in `doc`."""


@dataclass(frozen=True)
class Metric:
    id: str
    """Stable identifier, e.g. `base.adr`. Never changes, even when the formula's version does."""
    version: str
    """Semantic version of the formula: a formula change bumps it (ADR 0003)."""
    name: str
    unit: Unit
    doc: str
    """Definition, as in docs/metrics-v1.md."""
    compute: Compute = field(repr=False)
    params: Mapping[str, ParamValue] = field(default_factory=dict)
    """Parameters with their defaults (ADR 0007)."""
    uses: tuple[str, ...] = ()
    """Tables read (canonical and derived)."""
    scope: Scope = "player"
    kind: Kind = "value"


REGISTRY: dict[str, Metric] = {}


def metric(
    id: str,
    *,
    version: str,
    name: str,
    unit: Unit,
    doc: str,
    params: Mapping[str, ParamValue] | None = None,
    uses: tuple[str, ...] = (),
    kind: Kind = "value",
) -> Callable[[Compute], Compute]:
    """Registers a metric. The decorated function computes it on a dataset."""

    def register(compute: Compute) -> Compute:
        if id in REGISTRY:
            raise ValueError(f"metric {id!r} registered twice")
        REGISTRY[id] = Metric(
            id=id,
            version=version,
            name=name,
            unit=unit,
            doc=doc,
            compute=compute,
            params=dict(params or {}),
            uses=uses,
            kind=kind,
        )
        return compute

    return register
