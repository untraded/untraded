# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Choosing the ledger's shares: relative credit, reliability criteria and the search."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
import pytest

from untraded import fixtures
from untraded.winprob import default_model
from untraded.winprob.ledger import DEFAULT_SHARES, Shares, credit, prepare
from untraded.winprob.shares import (
    MIN_FINAL,
    Match,
    _normalized,
    _with,
    ablations,
    between_matches,
    choose,
    decide,
    played,
    relative,
    split_half,
    split_half_gain,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def matches() -> list[Match]:
    out = []
    for name in ("premier-half", "premier-abandon", "faceit-bots"):
        tables = fixtures.read(FIXTURES / name)
        out.append(Match(prepare(tables, default_model()), played(tables), name))
    return out


def test_relative_credit_is_zero_within_each_side(matches: list[Match]) -> None:
    m = matches[0]
    rel = relative(credit(m.prepared), m.played).join(m.played, on=["steamid", "round"])
    sums = rel.group_by("round", "side").agg(pl.col("relative").sum())
    assert sums.select(pl.col("relative").abs().max()).item() < 1e-9
    # Every player of a round with a ledger is there, credited or not.
    rounds = credit(m.prepared)["round"].unique()
    expected = m.played.filter(pl.col("round").is_in(rounds.implode())).height
    assert rel.height == expected


def _synthetic(signal: float, players: int = 40, matches: int = 30, seed: int = 0) -> pl.DataFrame:
    """Relative credits where each player has a true level times `signal`, plus noise."""
    rng = np.random.default_rng(seed)
    level = rng.normal(0, 1, players)
    rows = []
    for m in range(matches):
        for p in rng.choice(players, 10, replace=False):
            for r in range(1, 25):
                rows.append((f"m{m}", int(p), r, signal * level[p] + rng.normal(0, 1)))
    return pl.DataFrame(
        rows, schema=["match_id", "steamid", "round", "relative"], orient="row"
    ).with_columns(pl.col("round").cast(pl.Int16))


def test_reliability_grows_with_the_signal() -> None:
    noise, some, strong = (_synthetic(s) for s in (0.0, 0.3, 1.0))
    assert abs(split_half(noise)) < 0.2
    assert split_half(some) < split_half(strong)
    assert split_half(strong) > 0.8
    assert abs(between_matches(noise)) < 0.15
    assert between_matches(some) < between_matches(strong)
    assert between_matches(strong) > 0.8


def test_a_real_gain_has_an_interval_above_zero() -> None:
    strong, noise = _synthetic(1.0), _synthetic(0.0)
    gain = split_half_gain(strong, noise, resamples=200)
    assert gain["low"] > 0
    assert gain["low"] <= gain["gain"] <= gain["high"]
    same = split_half_gain(strong, strong, resamples=50)
    assert same == {"gain": 0.0, "low": 0.0, "high": 0.0}


def test_shares_are_adopted_only_when_they_gain_out_of_sample() -> None:
    start, chosen = DEFAULT_SHARES, Shares(final=0.55, damage=0.3, flash=0.15, trade=0.0)
    small = [{"chosen": {"split_half": 0.40}, "start": {"split_half": 0.40}}]
    large = [{"chosen": {"split_half": 0.45}, "start": {"split_half": 0.40}}]
    assert decide(start, chosen, small) == _normalized(start)
    assert decide(start, chosen, large) == chosen
    assert decide(start, chosen, []) == _normalized(start)


def test_the_killer_keeps_a_share() -> None:
    start = _normalized(DEFAULT_SHARES)
    total = start.final + start.damage + start.flash + start.trade
    assert total == pytest.approx(1.0)
    changed = _with(start, "damage", 0.45)
    assert changed is not None
    assert changed.final == pytest.approx(1 - 0.45 - start.flash - start.trade)
    assert _with(start, "damage", 0.9) is None  # would leave the killer under MIN_FINAL
    assert MIN_FINAL > 0
    assert _with(start, "plant", 0.75) == Shares(**{**start.__dict__, "plant": 0.75})


def test_choose_keeps_the_start_on_near_ties(matches: list[Match]) -> None:
    start = _normalized(DEFAULT_SHARES)
    chosen, steps = choose(matches, start, grid={"trade_window": (5.0,)}, passes=1)
    assert chosen == start
    assert steps == [
        {"share": "trade_window", "tried": {5.0: steps[0]["tried"][5.0]}, "kept": None}
    ]
    results = ablations(matches, chosen)
    assert set(results) == {
        "chosen",
        "no hold",
        "no trade share",
        "no flash share",
        "killer takes all",
    }
