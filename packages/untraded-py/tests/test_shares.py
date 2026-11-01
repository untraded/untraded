# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Choosing the ledger's shares: relative credit, reliability criteria and the search."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
import pytest

from untraded import fixtures
from untraded.winprob import default_model, shares
from untraded.winprob.ledger import DEFAULT_SHARES, Shares, credit, prepare
from untraded.winprob.shares import (
    MIN_FINAL,
    TOLERANCE,
    Match,
    _normalized,
    _with,
    ablations,
    between_matches,
    choose,
    decide,
    relative,
    split_half,
    split_half_gain,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def matches() -> list[Match]:
    out = []
    for name in ("premier-half", "premier-abandon", "faceit-bots"):
        out.append(Match(prepare(fixtures.read(FIXTURES / name), default_model()), name))
    return out


def test_relative_credit_is_zero_within_each_side(matches: list[Match]) -> None:
    m = matches[0]
    roster = m.prepared.rosters()
    credits = credit(m.prepared)
    rel = relative(credits, roster).join(roster, on=["steamid", "round"])
    sums = rel.group_by("round", "side").agg(pl.col("relative").sum())
    assert sums.select(pl.col("relative").abs().max()).item() < 1e-9
    # Every player of a round with a ledger is there, credited or not, on one side.
    assert rel.height == roster.height
    assert roster.select("steamid", "round").is_unique().all()
    # The roster's sides are those the ledger credits.
    sides = credits.select("steamid", "round", pl.col("side").alias("credited")).unique()
    both = sides.join(roster, on=["steamid", "round"])
    assert (both["credited"] == both["side"]).all()


def test_prepared_matches_can_be_credited_again(matches: list[Match]) -> None:
    m = matches[0]
    first = credit(m.prepared)
    credit(m.prepared, Shares(final=1.0, damage=0.0, flash=0.0, trade=0.0, plant=1.0))
    assert credit(m.prepared).equals(first)


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

    def check(low: float) -> dict[str, Any]:
        return {"gain": {"gain": low + 0.01, "low": low, "high": low + 0.02}}

    assert decide(start, chosen, [check(0.01), check(0.02)]) == chosen
    assert decide(start, chosen, [check(0.01), check(-0.01)]) == _normalized(start)
    assert decide(start, chosen, [check(float("nan")), check(0.02)]) == _normalized(start)
    assert decide(start, chosen, [check(0.01)]) == _normalized(start)


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


def test_choose_moves_only_beyond_the_tolerance(monkeypatch: pytest.MonkeyPatch) -> None:
    start = _normalized(DEFAULT_SHARES)
    gains = {0.25: TOLERANCE / 2, 0.75: TOLERANCE * 2, 1.0: float("nan")}

    def fake(_: Any, candidate: Shares, *__: Any) -> dict[str, float]:
        return {"split_half": 0.3 + gains.get(candidate.plant, 0.0)}

    monkeypatch.setattr(shares, "score", fake)
    near, _ = choose([], start, grid={"plant": (0.25, 0.5)}, passes=1)
    assert near == start  # a gain under the tolerance is a near tie
    far, steps = choose([], start, grid={"plant": (0.25, 0.5, 0.75, 1.0)}, passes=1)
    assert far.plant == 0.75  # beyond it, and a nan score is never the best
    assert steps[0]["kept"] == 0.75


def test_ablations_report_their_gain(matches: list[Match]) -> None:
    results = ablations(matches, _normalized(DEFAULT_SHARES))
    assert set(results) == {
        "chosen",
        "events only",
        "no trade share",
        "no flash share",
        "killer takes all",
    }
    assert set(results["events only"]["gain_over_chosen"]) == {"gain", "low", "high"}
