# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The win-probability model: features from the fixtures, fitting, validation and swings."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from untraded import fixtures
from untraded.winprob import (
    NUMERIC,
    Model,
    default_model,
    fit,
    samples,
    split_by_time,
    swings,
    train_and_validate,
)
from untraded.winprob.features import MONOTONE
from untraded.winprob.swing import FLASH_SHARE
from untraded.winprob.validation import auc, calibration

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def tables() -> dict[str, pl.DataFrame]:
    return fixtures.read(FIXTURES / "premier-half")


@pytest.fixture(scope="module")
def corpus() -> pl.DataFrame:
    """The three fixtures' samples, each dated so the time split has an order."""
    frames = []
    for day, name in enumerate(("premier-half", "premier-abandon", "faceit-bots"), start=1):
        frame = samples(fixtures.read(FIXTURES / name))
        frames.append(frame.with_columns(pl.lit(dt.date(2026, 10, day)).alias("played_at")))
    return pl.concat(frames)


def test_samples_are_open_states_one_per_second(tables: dict[str, pl.DataFrame]) -> None:
    frame = samples(tables)
    assert frame.columns == ["match_id", "map", "played_at", "round", "tick", *NUMERIC, "ct_won"]
    assert frame["round"].unique().sort().to_list() == [11, 12, 13, 14, 15]
    alive = frame.select(
        pl.col("alive_ct").min().alias("low"), pl.col("alive_ct").max().alias("high")
    )
    assert alive["low"].item() >= 1
    assert alive["high"].item() <= 5
    tickrate = float(tables["match"]["tickrate"][0])
    gap = frame.select(pl.col("tick").diff().over("round").max()).item()
    assert gap <= tickrate * 1.1  # about a second apart
    # Nothing after the round is decided.
    ends = tables["round"].select("round", "end_tick")
    late = frame.join(ends, on="round").filter(pl.col("tick") >= pl.col("end_tick"))
    assert late.is_empty()
    # Once the bomb is down, the clock is the bomb's.
    planted = frame.filter(pl.col("planted") > 0)
    assert planted.select(pl.col("time_left").max()).item() == 0
    assert planted.select(pl.col("time_left_planted").max()).item() <= 4.0


def test_fit_respects_the_signs_and_round_trips(corpus: pl.DataFrame) -> None:
    model = fit(corpus, version="test", l2=5.0)
    for name, sign in MONOTONE.items():
        coef = model.coef[model.features.index(name)]
        assert coef == 0 or np.sign(coef) == sign, name
    again = Model.from_json(model.to_json())
    assert np.allclose(again.predict(corpus), model.predict(corpus))
    p = model.predict(corpus)
    assert ((p > 0) & (p < 1)).all()


def test_a_wrong_sign_is_dropped() -> None:
    # Synthetic rounds where, against the rules, more CT health loses: the sign is enforced.
    rng = np.random.default_rng(0)
    n = 400
    hp = rng.uniform(1, 5, n)
    rows = {name: np.zeros(n) for name in NUMERIC}
    rows["alive_ct"] = rng.integers(1, 6, n).astype(float)
    rows["alive_t"] = rng.integers(1, 6, n).astype(float)
    rows["hp_ct"] = hp
    won = (rng.uniform(0, 1, n) < 1 / (1 + np.exp(hp - 3))).astype(bool)
    frame = pl.DataFrame(
        {
            "match_id": [f"m{i % 20}" for i in range(n)],
            "map": ["de_mirage"] * n,
            "played_at": [None] * n,
            "round": list(range(n)),
            "tick": [0] * n,
            **rows,
            "ct_won": won,
        }
    )
    model = fit(frame, version="test", l2=0.1)
    assert model.coef[model.features.index("hp_ct")] == 0


def test_auc_and_calibration() -> None:
    y = np.array([0, 0, 1, 1], dtype=float)
    w = np.ones(4)
    assert auc(y, np.array([0.1, 0.4, 0.35, 0.8]), w) == pytest.approx(0.75)
    assert auc(y, np.array([0.5, 0.5, 0.5, 0.5]), w) == pytest.approx(0.5)
    bins = calibration(y, np.array([0.05, 0.05, 0.95, 0.95]), w)
    assert [(b["predicted"], b["observed"]) for b in bins] == [(0.05, 0.0), (0.95, 1.0)]


def test_the_newest_matches_are_held_out(corpus: pl.DataFrame) -> None:
    train, test = split_by_time(corpus, held_out=0.34)
    assert (
        train.select(pl.col("played_at").max()).item()
        < test.select(pl.col("played_at").min()).item()
    )
    model = train_and_validate(corpus, version="test", held_out=0.34, l2=5.0)
    report = model.validation
    assert report["test_matches"] == 1
    assert set(report["model"]) == {"auc", "brier", "log_loss"}
    assert report["calibration"]


def test_swings_are_zero_sum_and_credit_damage(
    tables: dict[str, pl.DataFrame], corpus: pl.DataFrame
) -> None:
    model = fit(corpus, version="test", l2=5.0)
    credits = swings(tables, model)
    kills = credits.filter(pl.col("event") == "kill")
    by_kill = kills.group_by("round", "tick").agg(pl.col("swing").sum())
    attacked = tables["kill"].filter(pl.col("attacker").is_not_null(), ~pl.col("is_team_kill"))
    zero_sum = by_kill.join(attacked.select("round", "tick"), on=["round", "tick"])
    assert zero_sum.select(pl.col("swing").abs().max()).item() < 1e-9
    # The victim is debited what the killers gain.
    first = kills.filter(pl.col("tick") == kills["tick"].min())
    victim = tables["kill"].filter(pl.col("tick") == kills["tick"].min())["victim"][0]
    debit = first.filter(pl.col("steamid") == victim)["swing"][0]
    assert debit == pytest.approx(-first.filter(pl.col("steamid") != victim)["swing"].sum())
    # A kill that ends the round sets the probability to the result.
    eliminated = (
        tables["round"].filter(pl.col("reason") == "elimination").select("round", "winner_side")
    )
    last = (
        kills.sort("tick")
        .group_by("round")
        .agg(pl.col("p_ct_after").last())
        .join(eliminated, on="round")
    )
    for row in last.iter_rows(named=True):
        assert row["p_ct_after"] == (1.0 if row["winner_side"] == "CT" else 0.0)
    flashed = tables["kill"].filter(pl.col("flash_assist") & pl.col("assister").is_not_null())
    for row in flashed.iter_rows(named=True):
        rows = kills.filter(pl.col("tick") == row["tick"])
        gain = rows.filter(pl.col("steamid") != row["victim"]).select(pl.col("swing").sum()).item()
        flash = (
            rows.filter(pl.col("steamid") == row["assister"]).select(pl.col("swing").sum()).item()
        )
        assert flash >= gain * FLASH_SHARE - 1e-9


def test_the_published_model_loads_and_predicts(tables: dict[str, pl.DataFrame]) -> None:
    model = default_model()
    assert model.trained_on["matches"] > 0
    assert "pro" not in model.trained_on["sources"]
    p = model.predict(samples(tables))
    assert ((p > 0) & (p < 1)).all()
