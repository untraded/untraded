# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""How good the win-probability model is, on matches it did not see.

The split is in time: the newest matches are held out, as the model will always predict matches
played after its training. Every score weighs each round the same (its samples share a weight
of 1). Three baselines frame the numbers: the counter-terrorists' win rate alone, a model that
only knows how many players each side has alive, and model 1's features fitted on the same
matches. Differences come with a 95 % interval from resampling the test matches (bootstrap by
match: the states of one match are not independent).

`cross_fit` gives every sample a probability from a model that did not see its match: the swings
of the corpus's own matches must come from it, or the model's overfitting inflates them.
"""

from __future__ import annotations

import hashlib
import itertools
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import polars as pl

from untraded.winprob.features import CANDIDATES, FEATURE_SETS, NUMERIC
from untraded.winprob.model import Model, _newton, _sigmoid, fit, round_weights

CONTESTED_EQUIP = 1.5
"""States are contested when both sides have as many players alive and their equipment is within
this many thousand dollars: where the alive count alone says nothing."""
BOOTSTRAP = 1000
LEARNING_CURVE = (0.25, 0.5, 0.75, 1.0)
"""Shares of the training matches (oldest first) the learning curve is fitted on."""


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


def brier_parts(y: np.ndarray, p: np.ndarray, w: np.ndarray, bins: int = 10) -> dict[str, float]:
    """Murphy's decomposition of the Brier score, by tenths of predicted probability: Brier is
    about reliability - resolution + uncertainty (lower reliability is better calibrated, higher
    resolution separates wins from losses better). Binned, so only approximate."""
    total = w.sum()
    rate = float(np.sum(w * y) / total)
    reliability = resolution = 0.0
    index = np.minimum((p * bins).astype(int), bins - 1)
    for b in range(bins):
        inside = index == b
        if not inside.any():
            continue
        weight = w[inside].sum()
        predicted = np.sum(w[inside] * p[inside]) / weight
        observed = np.sum(w[inside] * y[inside]) / weight
        reliability += weight * (predicted - observed) ** 2
        resolution += weight * (observed - rate) ** 2
    return {
        "reliability": round(float(reliability / total), 4),
        "resolution": round(float(resolution / total), 4),
        "uncertainty": round(rate * (1 - rate), 4),
    }


def contested(frame: pl.DataFrame) -> np.ndarray:
    """The contested states of `frame` (`CONTESTED_EQUIP`)."""
    mask = (pl.col("alive_ct") == pl.col("alive_t")) & (
        (pl.col("equip_ct") - pl.col("equip_t")).abs() < CONTESTED_EQUIP
    )
    return frame.select(mask.alias("contested"))["contested"].to_numpy()


def _per_match_loss(test: pl.DataFrame, p: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Each test match's weighted log loss sum and weight, in a fixed match order."""
    eps = 1e-12
    y = test["ct_won"].cast(pl.Float64).to_numpy()
    w = round_weights(test)
    loss = -w * (y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps))
    frame = pl.DataFrame({"match_id": test["match_id"], "loss": loss, "w": w})
    per = frame.group_by("match_id").agg(pl.col("loss").sum(), pl.col("w").sum()).sort("match_id")
    return per["loss"].to_numpy(), per["w"].to_numpy()


def compare(
    test: pl.DataFrame,
    p: np.ndarray,
    others: Mapping[str, np.ndarray],
    *,
    resamples: int = BOOTSTRAP,
    seed: int = 0,
) -> dict[str, dict[str, float]]:
    """How much lower the log loss of `p` is than each of `others` on `test`, with a 95 %
    interval from resampling the test matches: a gain whose interval excludes zero is real."""
    loss, weight = _per_match_loss(test, p)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(loss), size=(resamples, len(loss)))
    out = {}
    for name, q in others.items():
        other, _ = _per_match_loss(test, q)
        gain = (other.sum() - loss.sum()) / weight.sum()
        boot = (other[draws].sum(axis=1) - loss[draws].sum(axis=1)) / weight[draws].sum(axis=1)
        low, high = np.percentile(boot, [2.5, 97.5])
        out[name] = {
            "log_loss_gain": round(float(gain), 4),
            "low": round(float(low), 4),
            "high": round(float(high), 4),
        }
    return out


def evaluate(model: Model, test: pl.DataFrame, train: pl.DataFrame) -> dict[str, Any]:
    """The model's scores on `test`, against the baselines fitted on `train`, with the
    calibration table, the Brier decomposition, and the scores before and after the plant and on
    contested states."""
    y = test["ct_won"].cast(pl.Float64).to_numpy()
    w = round_weights(test)
    p = model.predict(test)
    base_rate = float(np.sum(round_weights(train) * train["ct_won"].cast(pl.Float64).to_numpy()))
    base_rate /= float(round_weights(train).sum())
    alive_only = _alive_only(train)(test)
    planted = test["planted"].to_numpy() > 0
    close = contested(test)

    def part(mask: np.ndarray) -> dict[str, float] | None:
        return scores(y[mask], p[mask], w[mask]) if mask.any() else None

    report: dict[str, Any] = {
        "split": "time (newest matches held out)",
        "test_matches": test["match_id"].n_unique(),
        "test_rounds": test.select("match_id", "round").unique().height,
        "model": scores(y, p, w),
        "baseline_ct_rate": scores(y, np.full_like(y, base_rate), w),
        "baseline_alive_only": scores(y, alive_only, w),
        "before_plant": part(~planted),
        "after_plant": part(planted),
        "contested": part(close),
        "brier_parts": brier_parts(y, p, w),
        "calibration": calibration(y, p, w),
        "calibration_after_plant": calibration(y[planted], p[planted], w[planted]),
    }
    others = {"alive_only": alive_only}
    if model.numeric != FEATURE_SETS["v1"]:
        v1 = fit(train, version="baseline", numeric=FEATURE_SETS["v1"])
        report["baseline_v1_features"] = scores(y, v1.predict(test), w)
        others["v1_features"] = v1.predict(test)
    report["gain_over"] = compare(test, p, others)
    return report


def learning_curve(
    train: pl.DataFrame,
    test: pl.DataFrame,
    shares: Sequence[float] = LEARNING_CURVE,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """The test scores of the model fitted on the oldest `share` of the training matches, for
    each share: where the curve flattens, more matches stop paying."""
    order = (
        train.select("match_id", "played_at")
        .unique("match_id")
        .sort("played_at", "match_id", nulls_last=False)["match_id"]
        .to_list()
    )
    y = test["ct_won"].cast(pl.Float64).to_numpy()
    w = round_weights(test)
    points = []
    for share in shares:
        ids = order[: max(2, round(len(order) * share))]
        subset = train.filter(pl.col("match_id").is_in(ids))
        model = fit(subset, version="curve", **kwargs)
        points.append({"matches": len(ids), **scores(y, model.predict(test), w)})
    return points


def _fold(match_id: str, folds: int) -> int:
    """A match's fold: stable across runs and machines (no salted `hash`)."""
    return int(hashlib.sha256(match_id.encode()).hexdigest(), 16) % folds


def cross_fit(frame: pl.DataFrame, folds: int = 5, **kwargs: Any) -> np.ndarray:
    """The probability of every sample of `frame` from a model fitted without its match: each
    match falls in one of `folds` groups, predicted by the model fitted on the others."""
    fold = np.array([_fold(m, folds) for m in frame["match_id"].to_list()])
    p = np.full(frame.height, np.nan)
    for k in range(folds):
        inside = fold == k
        if not inside.any():
            continue
        if inside.all():
            raise ValueError("cross-fitting needs matches in more than one fold")
        mask = pl.Series(inside)
        model = fit(frame.filter(~mask), version="cross-fit", **kwargs)
        p[inside] = model.predict(frame.filter(mask))
    return p


def select_features(
    frame: pl.DataFrame,
    *,
    base: Sequence[str] = NUMERIC,
    candidates: Mapping[str, Sequence[str]] = CANDIDATES,
    folds: int = 5,
    **kwargs: Any,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Forward selection of feature families, on cross-fitted probabilities: at each step the
    family that lowers the log loss most joins, if the 95 % interval of its gain (resampling
    matches) is above zero; it stops when none does. Returns the features and the steps tried, so
    the choice can be published."""
    chosen = list(base)
    left = dict(candidates)
    steps: list[dict[str, Any]] = []
    current = cross_fit(frame, folds, numeric=chosen, **kwargs)
    while left:
        tried = {
            name: cross_fit(frame, folds, numeric=[*chosen, *extra], **kwargs)
            for name, extra in left.items()
        }
        gains = {
            name: compare(frame, p, {"current": current})["current"] for name, p in tried.items()
        }
        best = max(gains, key=lambda name: gains[name]["log_loss_gain"])
        kept = gains[best]["low"] > 0
        steps.append({"candidates": gains, "kept": best if kept else None})
        if not kept:
            break
        chosen.extend(left.pop(best))
        current = tried[best]
    return chosen, steps


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
    frame: pl.DataFrame,
    *,
    version: str,
    held_out: float = 0.3,
    select: bool = False,
    **kwargs: Any,
) -> Model:
    """The published model: validated on the newest matches, then refitted on all of them, with
    the held-out scores and the learning curve recorded in `Model.validation`.

    With `select`, the features come from `select_features`: on the training matches alone for
    the held-out scores (the test matches never weigh on the choice), then on every match for the
    published model, whose steps are recorded."""
    train, test = split_by_time(frame, held_out)
    if select:
        numeric, _ = select_features(train, **kwargs)
        kwargs = {**kwargs, "numeric": numeric}
    checked = fit(train, version=version, **kwargs)
    report = evaluate(checked, test, train)
    report["learning_curve"] = learning_curve(train, test, **kwargs)
    if select:
        kwargs["numeric"], report["selection"] = select_features(
            frame, **{k: v for k, v in kwargs.items() if k != "numeric"}
        )
        report["selected_on_train"] = checked.numeric
    final = fit(frame, version=version, **kwargs)
    return Model(**{**final.__dict__, "validation": report})
