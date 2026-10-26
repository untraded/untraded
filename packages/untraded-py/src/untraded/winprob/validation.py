# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""How good the win-probability model is, on matches it did not see.

The split is in time: the newest matches are held out, as the model will always predict matches
played after its training. Every score weighs each round the same (its samples share a weight
of 1). Two baselines frame the numbers: the counter-terrorists' win rate alone, and a model that
only knows how many players each side has alive.
"""

from __future__ import annotations

import itertools
from typing import Any

import numpy as np
import polars as pl

from untraded.winprob.model import Model, _newton, _sigmoid, fit, round_weights


def split_by_time(frame: pl.DataFrame, held_out: float = 0.3) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Training and test samples: the newest `held_out` share of the matches is the test set
    (by `played_at`, then match id for matches without a date or on the same day)."""
    order = (
        frame.select("match_id", "played_at")
        .unique("match_id")
        .sort("played_at", "match_id", nulls_last=False)["match_id"]
        .to_list()
    )
    cut = max(1, min(len(order) - 1, round(len(order) * (1 - held_out))))
    train_ids = set(order[:cut])
    in_train = pl.col("match_id").is_in(list(train_ids))
    return frame.filter(in_train), frame.filter(~in_train)


def auc(y: np.ndarray, p: np.ndarray, w: np.ndarray) -> float:
    """Weighted area under the ROC curve: the chance that a winning state gets a higher
    probability than a losing one (ties count half)."""
    order = np.argsort(p, kind="mergesort")
    p, y, w = p[order], y[order], w[order]
    positive, negative = w * y, w * (1 - y)
    total_pos, total_neg = positive.sum(), negative.sum()
    if total_pos == 0 or total_neg == 0:
        return float("nan")
    area = 0.0
    neg_below = 0.0
    i = 0
    while i < len(p):
        j = i
        while j + 1 < len(p) and p[j + 1] == p[i]:
            j += 1
        pos_here, neg_here = positive[i : j + 1].sum(), negative[i : j + 1].sum()
        area += pos_here * (neg_below + neg_here / 2)
        neg_below += neg_here
        i = j + 1
    return float(area / (total_pos * total_neg))


def scores(y: np.ndarray, p: np.ndarray, w: np.ndarray) -> dict[str, float]:
    """AUC, Brier score and log loss, weighted."""
    eps = 1e-12
    brier = float(np.sum(w * (p - y) ** 2) / w.sum())
    log_loss = float(-np.sum(w * (y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps))) / w.sum())
    return {"auc": round(auc(y, p, w), 4), "brier": round(brier, 4), "log_loss": round(log_loss, 4)}


def calibration(
    y: np.ndarray, p: np.ndarray, w: np.ndarray, bins: int = 10
) -> list[dict[str, float]]:
    """Predicted against observed, by tenths of predicted probability (weighted rounds)."""
    out = []
    edges = np.linspace(0, 1, bins + 1)
    for low, high in itertools.pairwise(edges):
        inside = (p >= low) & ((p < high) if high < 1 else (p <= high))
        if not inside.any():
            continue
        weight = w[inside].sum()
        out.append(
            {
                "from": round(float(low), 1),
                "to": round(float(high), 1),
                "predicted": round(float(np.sum(w[inside] * p[inside]) / weight), 3),
                "observed": round(float(np.sum(w[inside] * y[inside]) / weight), 3),
                "rounds": round(float(weight), 1),
            }
        )
    return out


def evaluate(model: Model, test: pl.DataFrame, train: pl.DataFrame) -> dict[str, Any]:
    """The model's scores on `test`, against the two baselines fitted on `train`, with the
    calibration table and the scores before and after the plant."""
    y = test["ct_won"].cast(pl.Float64).to_numpy()
    w = round_weights(test)
    p = model.predict(test)
    base_rate = float(np.sum(round_weights(train) * train["ct_won"].cast(pl.Float64).to_numpy()))
    base_rate /= float(round_weights(train).sum())
    alive_only = _alive_only(train)
    planted = test["planted"].to_numpy() > 0
    return {
        "split": "time (newest matches held out)",
        "test_matches": test["match_id"].n_unique(),
        "test_rounds": test.select("match_id", "round").unique().height,
        "model": scores(y, p, w),
        "baseline_ct_rate": scores(y, np.full_like(y, base_rate), w),
        "baseline_alive_only": scores(y, alive_only(test), w),
        "before_plant": scores(y[~planted], p[~planted], w[~planted]) if (~planted).any() else None,
        "after_plant": scores(y[planted], p[planted], w[planted]) if planted.any() else None,
        "calibration": calibration(y, p, w),
    }


def _alive_only(train: pl.DataFrame) -> Any:
    """A baseline that only knows the players alive on each side."""

    def design(frame: pl.DataFrame) -> np.ndarray:
        return frame.select("alive_ct", "alive_t").to_numpy().astype(float)

    coef, intercept = _newton(
        design(train), train["ct_won"].cast(pl.Float64).to_numpy(), round_weights(train), 0.0
    )

    def predict(frame: pl.DataFrame) -> np.ndarray:
        return _sigmoid(design(frame) @ coef + intercept)

    return predict


def train_and_validate(
    frame: pl.DataFrame, *, version: str, held_out: float = 0.3, **kwargs: Any
) -> Model:
    """The published model: validated on the newest matches, then refitted on all of them, with
    the held-out scores recorded in `Model.validation`."""
    train, test = split_by_time(frame, held_out)
    checked = fit(train, version=version, **kwargs)
    report = evaluate(checked, test, train)
    final = fit(frame, version=version, **kwargs)
    return Model(**{**final.__dict__, "validation": report})
