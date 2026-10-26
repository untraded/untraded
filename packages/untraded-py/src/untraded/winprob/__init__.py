# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Round win probability and the swing of each action: the base of Untraded's open rating.

- `features`: the round's state, sampled every second (counter-terrorists' point of view);
- `model`: a logistic regression on that state, published as coefficients (`Model`);
- `validation`: scores on the newest matches, held out, against two baselines;
- `swing`: the probability before and after each kill, plant and defuse, credited to players.

The published model (`default_model()`) is trained on demos of consenting players only (ADR 0010);
docs/winprob.md describes the method and its scores.
"""

from __future__ import annotations

from functools import cache
from importlib import resources

from untraded.winprob.features import BOMB_SECONDS, NUMERIC, ROUND_SECONDS, samples, state_at
from untraded.winprob.model import Model, fit
from untraded.winprob.swing import swings
from untraded.winprob.validation import evaluate, split_by_time, train_and_validate

__all__ = [
    "BOMB_SECONDS",
    "NUMERIC",
    "ROUND_SECONDS",
    "Model",
    "default_model",
    "evaluate",
    "fit",
    "samples",
    "split_by_time",
    "state_at",
    "swings",
    "train_and_validate",
]

DEFAULT = "winprob-v1.json"


@cache
def default_model() -> Model:
    """The published model shipped with the package."""
    return Model.from_json(
        resources.files(__package__).joinpath(DEFAULT).read_text(encoding="utf-8")
    )
