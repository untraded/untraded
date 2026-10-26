# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The win-probability model: a logistic regression on the round's state, small enough to publish
as a table of coefficients.

Fitted by Newton's method with an L2 penalty on standardized features, each round weighing the
same whatever its length (its samples share a weight of 1). Signs listed in `MONOTONE` are
enforced: a coefficient on the wrong side is dropped and the model refitted without it. Maps are
one-hot features (the first map of the list is the baseline), so a map shifts the odds but the
game's rules stay shared, which suits a small corpus.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from untraded.winprob.features import MONOTONE, NUMERIC

FORMAT_VERSION = 1


@dataclass(frozen=True)
class Model:
    version: str
    """The model's version, e.g. `1.0`: bumped whenever the coefficients change."""
    features: list[str]
    """Input names, in coefficient order: `NUMERIC`, then `map=<name>` for each map but the
    baseline."""
    mean: list[float]
    scale: list[float]
    coef: list[float]
    """Coefficients on standardized features (`(x - mean) / scale`)."""
    intercept: float
    maps: list[str]
    """Maps seen in training; the first is the baseline, an unknown map counts as the baseline."""
    trained_on: dict[str, Any] = field(default_factory=dict)
    """What the model saw: matches, rounds, samples, dates, sources (no match ids: ADR 0010)."""
    validation: dict[str, Any] = field(default_factory=dict)
    """`untraded.winprob.validation.evaluate` on matches held out, newest last."""

    def design(self, frame: pl.DataFrame) -> np.ndarray:
        """The standardized input matrix of `frame` (columns `NUMERIC` and `map`)."""
        numeric = frame.select(NUMERIC).to_numpy().astype(float)
        maps = frame["map"].to_list()
        dummies = np.array(
            [[1.0 if m == name else 0.0 for name in self.maps[1:]] for m in maps], dtype=float
        ).reshape(len(maps), max(len(self.maps) - 1, 0))
        x = np.hstack([numeric, dummies])
        standardized: np.ndarray = (x - np.array(self.mean)) / np.array(self.scale)
        return standardized

    def predict(self, frame: pl.DataFrame) -> np.ndarray:
        """Probability that the counter-terrorists win the round, for each row of `frame`."""
        z = self.design(frame) @ np.array(self.coef) + self.intercept
        return _sigmoid(z)

    def to_json(self) -> str:
        return json.dumps({"format": FORMAT_VERSION, **asdict(self)}, indent=2, sort_keys=False)

    def save(self, path: Path) -> None:
        path.write_text(self.to_json() + "\n", encoding="utf-8", newline="\n")

    @classmethod
    def from_json(cls, text: str) -> Model:
        data = json.loads(text)
        if data.pop("format", None) != FORMAT_VERSION:
            raise ValueError("unknown win-probability model format")
        return cls(**data)

    @classmethod
    def load(cls, path: Path) -> Model:
        return cls.from_json(path.read_text(encoding="utf-8"))


def _sigmoid(z: np.ndarray) -> np.ndarray:
    p: np.ndarray = 1.0 / (1.0 + np.exp(-np.clip(z, -35, 35)))
    return p


def round_weights(frame: pl.DataFrame) -> np.ndarray:
    """1 / (samples of the round) for each sample: every round weighs 1 whatever its length."""
    counts = frame.group_by("match_id", "round").len()
    joined = frame.select("match_id", "round").join(counts, on=["match_id", "round"], how="left")
    return 1.0 / joined["len"].to_numpy().astype(float)


def _newton(
    x: np.ndarray, y: np.ndarray, w: np.ndarray, l2: float, iterations: int = 50
) -> tuple[np.ndarray, float]:
    """Weighted, L2-penalized logistic regression (the intercept is not penalized)."""
    n, k = x.shape
    xa = np.hstack([np.ones((n, 1)), x])
    beta = np.zeros(k + 1)
    penalty = np.full(k + 1, l2)
    penalty[0] = 0.0
    for _ in range(iterations):
        p = _sigmoid(xa @ beta)
        gradient = xa.T @ (w * (p - y)) + penalty * beta
        hessian = (xa * (w * p * (1 - p))[:, None]).T @ xa + np.diag(penalty)
        step = np.linalg.solve(hessian, gradient)
        beta -= step
        if np.max(np.abs(step)) < 1e-9:
            break
    return beta[1:], float(beta[0])


def fit(
    frame: pl.DataFrame,
    *,
    version: str,
    l2: float = 1.0,
    monotone: Mapping[str, int] = MONOTONE,
    trained_on: Mapping[str, Any] | None = None,
) -> Model:
    """Fits the model on `frame` (`untraded.winprob.features.samples`, several matches)."""
    maps = sorted(set(frame["map"].to_list()))
    names = [*NUMERIC, *(f"map={m}" for m in maps[1:])]
    numeric = frame.select(NUMERIC).to_numpy().astype(float)
    dummies = np.array([[1.0 if m == name else 0.0 for name in maps[1:]] for m in frame["map"]])
    raw = np.hstack([numeric, dummies.reshape(frame.height, len(maps) - 1)])
    mean, scale = raw.mean(axis=0), raw.std(axis=0)
    scale[scale == 0] = 1.0
    x = (raw - mean) / scale
    y = frame["ct_won"].cast(pl.Float64).to_numpy()
    w = round_weights(frame)
    w = w * len(w) / w.sum()  # mean weight 1: the penalty keeps the same strength
    active = list(range(len(names)))
    while True:
        coef_active, intercept = _newton(x[:, active], y, w, l2)
        wrong = [
            i
            for i, c in zip(active, coef_active, strict=True)
            if names[i] in monotone and np.sign(c) not in (0, monotone[names[i]])
        ]
        if not wrong:
            break
        active = [i for i in active if i not in wrong]
    coef = np.zeros(len(names))
    coef[active] = coef_active
    return Model(
        version=version,
        features=names,
        mean=[float(v) for v in mean],
        scale=[float(v) for v in scale],
        coef=[float(v) for v in coef],
        intercept=intercept,
        maps=maps,
        trained_on=dict(trained_on or {}),
    )


def describe(frame: pl.DataFrame, sources: Sequence[str]) -> dict[str, Any]:
    """What a training set holds, for `Model.trained_on`."""
    dates = frame["played_at"].drop_nulls()
    return {
        "matches": frame["match_id"].n_unique(),
        "rounds": frame.select("match_id", "round").unique().height,
        "samples": frame.height,
        "maps": dict(sorted(frame.group_by("map").agg(pl.col("match_id").n_unique()).iter_rows())),
        "from": str(dates.min()) if len(dates) else None,
        "to": str(dates.max()) if len(dates) else None,
        "sources": sorted(set(sources)),
        "trained": dt.date.today().isoformat(),
    }
