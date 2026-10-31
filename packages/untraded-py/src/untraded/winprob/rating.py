# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The Untraded Rating: a player's swings per round, on a scale where 1.00 is the average player.

`rating.swing` is the win probability a player's actions moved per round, in percentage points;
its average is about 0, so it cannot be divided by itself. The rating is an affine mapping of it:

    rating = 1 + (swing - mean) / scale

- `mean` is the corpus's swing per round, all rounds pooled: the average player rates 1.00;
- `scale` is the swing worth 1.00 of rating, chosen so that the spread of the rating over the
  corpus's player-matches equals that of HLTV 1.0 on the same matches: a 1.20 reads as at HLTV.

Both come from the corpus of consenting players (ADR 0010) and are published with the model
(`rating-v1.json`); docs/winprob.md gives the method and the check against HLTV 1.0 and 2.0.
"""

from __future__ import annotations

import datetime as dt
import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Any

import polars as pl

FORMAT_VERSION = 1
DEFAULT = "rating-v1.json"
Z95 = 1.96


@dataclass(frozen=True)
class RatingScale:
    version: str
    """The scale's version, e.g. `1.0`: bumped whenever `mean` or `scale` change."""
    model: str
    """The win-probability model the swings come from (`Model.version`)."""
    mean: float
    """The corpus's swing per round, in percentage points (all rounds pooled)."""
    scale: float
    """Percentage points of swing per round worth 1.00 of rating."""
    trained_on: dict[str, Any] = field(default_factory=dict)
    """What the scale was measured on, and its check against HLTV 1.0 and 2.0."""

    def rate(self, swing_per_round: float) -> float:
        """The rating of a swing per round (percentage points)."""
        return 1 + (swing_per_round - self.mean) / self.scale

    def to_json(self) -> str:
        return json.dumps({"format": FORMAT_VERSION, **asdict(self)}, indent=2)

    def save(self, path: Path) -> None:
        path.write_text(self.to_json() + "\n", encoding="utf-8", newline="\n")

    @classmethod
    def from_json(cls, text: str) -> RatingScale:
        data = json.loads(text)
        if data.pop("format", None) != FORMAT_VERSION:
            raise ValueError("unknown rating scale format")
        scale = cls(**data)
        numbers = (scale.mean, scale.scale)
        if not all(isinstance(n, int | float) and math.isfinite(n) for n in numbers):
            raise ValueError("the rating scale needs a finite mean and scale")
        if scale.scale <= 0:
            raise ValueError("the rating scale must be positive")
        return scale


@cache
def default_scale() -> RatingScale:
    """The published scale shipped with the package."""
    return RatingScale.from_json(
        resources.files(__package__).joinpath(DEFAULT).read_text(encoding="utf-8")
    )


def _std(values: list[float]) -> float:
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))


def _corr(a: list[float], b: list[float]) -> float:
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b, strict=True))
    return cov / math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))


def fit_scale(
    matches: Iterable[Mapping[str, pl.DataFrame]], *, version: str, model: str
) -> RatingScale:
    """Measures the scale on matches with their derived tables (`swing` included): the pooled
    swing per round, and the swing worth 1.00 of rating so that the rating's spread over the
    player-matches is HLTV 1.0's."""
    from untraded.metrics import Dataset, compute  # the metrics read this module

    rows: list[dict[str, Any]] = []
    maps: dict[str, int] = {}
    modes: dict[str, int] = {}
    for tables in matches:
        ds = Dataset.from_matches([tables])
        values = compute(ds, ["rating.swing", "rating.hltv1", "rating.hltv2_approx"])
        wide = values.pivot("metric", index="steamid", values="value").join(
            ds.rounds_played(), on="steamid"
        )
        rows.extend(r for r in wide.iter_rows(named=True) if r["rating.swing"] is not None)
        name = str(tables["match"]["map"][0])
        maps[name] = maps.get(name, 0) + 1
        mode = str(tables["match"]["mode"][0])
        modes[mode] = modes.get(mode, 0) + 1
    if len(rows) < 2:
        raise ValueError("not enough player-matches to measure a scale")
    swing = [float(r["rating.swing"]) for r in rows]
    hltv1 = [float(r["rating.hltv1"]) for r in rows]
    hltv2 = [float(r["rating.hltv2_approx"]) for r in rows]
    rounds = [int(r["rounds"]) for r in rows]
    mean = sum(s * n for s, n in zip(swing, rounds, strict=True)) / sum(rounds)
    scale = _std(swing) / _std(hltv1)
    return RatingScale(
        version=version,
        model=model,
        mean=round(mean, 4),
        scale=round(scale, 4),
        trained_on={
            "matches": sum(maps.values()),
            "player_matches": len(rows),
            "maps": dict(sorted(maps.items())),
            "modes": dict(sorted(modes.items())),
            "measured": dt.date.today().isoformat(),
            "correlation_hltv1": round(_corr(swing, hltv1), 3),
            "correlation_hltv2_approx": round(_corr(swing, hltv2), 3),
            "hltv1_std": round(_std(hltv1), 3),
        },
    )
