# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The Untraded Rating 2.0: the match rating, the level and how they are fitted."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from untraded import fixtures
from untraded.derive import derive
from untraded.winprob import default_model
from untraded.winprob.ledger import ledger
from untraded.winprob.rating2 import (
    BOX_FEATURES,
    FEATURES,
    Box,
    RatingModel,
    _variances,
    fit,
    halves,
    per_round,
    round_stats,
)

FIXTURES = Path(__file__).parent / "fixtures"
Half = tuple[dict[str, pl.DataFrame], dict[str, pl.DataFrame], pl.DataFrame]


@pytest.fixture(scope="module")
def half() -> Half:
    tables = fixtures.read(FIXTURES / "premier-half")
    return tables, derive(tables).tables(), ledger(tables, default_model())


def _model(ledger_rounds: float | None = 92.0) -> RatingModel:
    return RatingModel(
        version="test",
        model="1.0",
        shares={},
        hold=False,
        points_per_rating=15.0,
        box=Box(BOX_FEATURES, [0.7, 0.7, 0.8], [0.5, 0.45, 0.5], [0.5, -0.8, 0.8], 0.0),
        lam=100.0,
        ledger_rounds=ledger_rounds,
    )


def test_the_box_score_per_round(half: Half) -> None:
    tables, derived, _ = half
    stats = round_stats(tables, derived)
    assert stats.height == derived["round_player"].height
    assert set(FEATURES) <= set(stats.columns)
    for name in ("kast", "survival", "multikills", "opening_kills", "opening_deaths"):
        assert stats.select(pl.col(name).is_between(0, 1).all()).item(), name
    # One survives a round or dies in it.
    assert stats.filter((pl.col("survival") + pl.col("dpr")) != 1).is_empty()


def test_per_round_without_the_hold_still_averages_zero(
    half: Half,
) -> None:
    tables, derived, credits = half
    for hold in (True, False):
        rounds = per_round(tables, derived, credits, hold=hold)
        sums = rounds.group_by("round").agg(pl.col("credit").mean())
        assert sums.select(pl.col("credit").abs().max()).item() < 1e-9
    with_hold = per_round(tables, derived, credits, hold=True)
    without = per_round(tables, derived, credits, hold=False)
    assert not np.allclose(with_hold["credit"].to_numpy(), without["credit"].to_numpy())


def test_halves_split_the_rounds(half: Half) -> None:
    tables, derived, credits = half
    frame = halves(per_round(tables, derived, credits, hold=False), "m")
    assert set(frame["half"].unique().to_list()) == {"odd", "even", "all"}
    wide = frame.pivot("half", index="steamid", values="rounds").fill_null(0)
    assert (wide["odd"] + wide["even"] == wide["all"]).all()


def test_the_level_moves_from_the_box_to_the_ledger() -> None:
    model = _model(92.0)
    assert model.level(1.0, 5.0, 0) == pytest.approx(1.0)
    assert model.level(1.0, 5.0, 92) == pytest.approx(3.0)
    assert model.level(1.0, 5.0, 100_000) == pytest.approx(5.0, abs=0.01)
    # A box that leaves nothing for the ledger: the level is the box.
    flat = _model(None)
    assert flat.level(1.0, 5.0, 1000) == 1.0
    assert model.match_rating(15.0) == pytest.approx(2.0)


def test_the_published_rating_loads() -> None:
    from importlib import resources

    text = resources.files("untraded.winprob").joinpath("rating-v2.json").read_text("utf-8")
    model = RatingModel.from_json(text)
    assert model.box.features == BOX_FEATURES
    assert "level_error_by_ledger_rounds" in model.validation
    assert "match_id" not in text  # ADR 0010: no match ids in published files


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ('"points_per_rating": 15.0', '"points_per_rating": -1.0', "positive"),
        ('"points_per_rating": 15.0', '"points_per_rating": NaN', "NaN"),
        ('"lam": 100.0', '"lam": true', "finite"),
        ('"ledger_rounds": 92.0', '"ledger_rounds": 0', "positive"),
        ('"kpr",', '"kd",', "box must read"),
        ('"intercept": 0.0', '"intercept": "x"', "finite"),
        ('"version": "test",', "", "malformed"),
    ],
)
def test_a_bad_rating_file_is_refused(old: str, new: str, message: str) -> None:
    text = _model().to_json()
    assert old in text
    with pytest.raises(ValueError, match=message):
        RatingModel.from_json(text.replace(old, new, 1))


def test_the_model_round_trips() -> None:
    for k in (92.0, None):
        model = _model(k)
        assert RatingModel.from_json(model.to_json()) == model


def test_an_empty_match_rates_no_one() -> None:
    empty = pl.DataFrame(
        schema={"steamid": pl.UInt64, "round": pl.Int16, "credit": pl.Float64}
        | dict.fromkeys(FEATURES, pl.Float64)
    )
    assert _model().rate_match(empty).is_empty()


def test_a_match_averages_one(half: Half) -> None:
    tables, derived, credits = half
    rated = _model().rate_match(per_round(tables, derived, credits, hold=False))
    weights = rated["rounds"].to_numpy().astype(float)
    assert np.average(rated["rating"].to_numpy(), weights=weights) == pytest.approx(1.0)
    assert np.average(rated["level"].to_numpy(), weights=weights) == pytest.approx(1.0)
    assert (rated["margin"].drop_nulls() > 0).all()


def test_the_variances_are_recovered() -> None:
    # Levels around the box with variance 4, rounds around the level with variance 400.
    rng = np.random.default_rng(3)
    rows = []
    for m in range(200):
        for p in range(10):
            level = rng.normal(0, 2)
            for half_name in ("odd", "even"):
                n = 12
                credit = level + rng.normal(0, 20 / math.sqrt(n))
                rows.append((f"m{m}", p, half_name, n, credit))
    pairs = pl.DataFrame(
        rows, schema=["match_id", "steamid", "half", "rounds", "credit"], orient="row"
    )
    sigma2, tau2 = _variances(pairs, np.zeros(pairs.height))
    assert sigma2 == pytest.approx(400, rel=0.1)
    assert tau2 == pytest.approx(4, rel=0.35)


def test_fit_on_a_synthetic_corpus() -> None:
    # Players whose credit follows their kills and deaths: the box finds it, the level beats
    # the raw credit at predicting the other half.
    rng = np.random.default_rng(5)
    frames = []
    for m in range(40):
        rows = []
        skill = rng.normal(0, 1, 10)
        for p in range(10):
            for half_name in ("odd", "even"):
                kpr = max(0.0, 0.7 + 0.2 * skill[p] + rng.normal(0, 0.15))
                dpr = min(1.0, max(0.0, 0.7 - 0.1 * skill[p] + rng.normal(0, 0.1)))
                row = {f: float(rng.uniform(0, 1)) for f in FEATURES}
                row.update(kpr=kpr, dpr=dpr, adr=kpr * 1.1)
                credit = 3 * skill[p] + rng.normal(0, 6)
                rows.append(
                    {
                        "match_id": f"m{m}",
                        "steamid": p,
                        "half": half_name,
                        "rounds": 12,
                        "credit": credit,
                        **row,
                        "hltv1": 1 + 0.3 * skill[p] + rng.normal(0, 0.2),
                        "hltv2": 1.0,
                        "kd": kpr - dpr,
                        "swing1": 0.0,
                    }
                )
        frame = pl.DataFrame(rows)
        whole = (
            frame.group_by("match_id", "steamid")
            .agg(pl.col("rounds").sum(), pl.exclude("half", "rounds").mean())
            .with_columns(pl.lit("all").alias("half"))
            .select(frame.columns)
        )
        frames.append(pl.concat([frame, whole]))
    model = fit(frames, version="test", model="1.0", shares={})
    assert model.points_per_rating > 0
    assert model.box.coef[BOX_FEATURES.index("kpr")] > 0
    v = model.validation["predicts_other_half_credit"]
    assert v["level"] > v["match"]
    assert set(model.validation) >= {"split_half", "between_matches", "level_gain_credit"}
