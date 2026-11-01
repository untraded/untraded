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
from untraded.derive import derive
from untraded.derive.schema import TABLES
from untraded.metrics import Dataset, compute
from untraded.winprob import (
    NUMERIC,
    NUMERIC_V2,
    Model,
    cross_fit,
    default_model,
    fit,
    samples,
    split_by_time,
    swings,
    train_and_validate,
)
from untraded.winprob.features import BOMB_SECONDS, CANDIDATES, MONOTONE, state_at
from untraded.winprob.swing import FLASH_SHARE
from untraded.winprob.validation import (
    _fold,
    auc,
    brier_parts,
    calibration,
    compare,
    select_features,
)

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
    assert frame.columns == [
        "match_id",
        "map",
        "played_at",
        "round",
        "tick",
        *NUMERIC_V2,
        "ct_won",
    ]
    assert set(NUMERIC) < set(NUMERIC_V2)
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


def test_what_the_living_carry_and_the_defuse_race(tables: dict[str, pl.DataFrame]) -> None:
    frame = samples(tables)
    for side in ("ct", "t"):
        primaries = pl.col(f"awp_{side}") + pl.col(f"rifles_{side}") + pl.col(f"smgs_{side}")
        # Nobody alive carries two primaries.
        assert frame.filter(primaries > pl.col(f"alive_{side}")).is_empty()
        assert frame.select(pl.col(f"rifles_{side}").max()).item() > 0
        assert frame.select(pl.col(f"smokes_{side}").max()).item() > 0
    # The defuse race only runs once the bomb is down, within its cap.
    before = frame.filter(pl.col("planted") == 0)
    assert before.select(pl.col("defuse_margin").abs().max()).item() == 0
    after = frame.filter(pl.col("planted") > 0)
    assert not after.is_empty()
    assert after.select(pl.col("defuse_margin").abs().max()).item() <= 2.0
    assert after.select(pl.col("defuse_margin").n_unique()).item() > 1
    # Seconds of bomb left minus the quickest counter-terrorist's run and defuse: never more
    # than the bomb's time minus a kit defuse.
    assert after.select(pl.col("defuse_margin").max()).item() <= (BOMB_SECONDS - 5) / 10
    # The clock's bends follow the clock.
    assert frame.filter(
        pl.col("time_left_over_30s") != (pl.col("time_left") - 3).clip(0)
    ).is_empty()
    # The state at a tick has the same features as the samples.
    row = frame.row(len(frame) // 2, named=True)
    state = state_at(tables, row["round"], row["tick"] + 1)
    assert set(NUMERIC_V2) <= set(state.columns)


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
    rows = {name: np.zeros(n) for name in NUMERIC_V2}
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
    # Model 2's features are compared with model 1's, fitted on the same matches.
    assert set(report["gain_over"]) == {"alive_only", "v1_features"}
    assert report["learning_curve"][-1]["matches"] == 2
    parts = report["brier_parts"]
    assert parts["uncertainty"] > 0
    v1 = train_and_validate(corpus, version="test", held_out=0.34, l2=5.0, numeric=NUMERIC)
    assert v1.numeric == NUMERIC
    assert "v1_features" not in v1.validation["gain_over"]


def test_a_v1_model_reads_the_new_samples(tables: dict[str, pl.DataFrame]) -> None:
    # A model 1 file names model 1's features only: it predicts from samples that have more.
    model = default_model()
    assert model.numeric == NUMERIC
    frame = samples(tables)
    assert np.allclose(model.predict(frame), model.predict(frame.select(*NUMERIC, "map")))


def test_brier_parts_add_up() -> None:
    rng = np.random.default_rng(1)
    p = rng.uniform(0, 1, 5000)
    y = (rng.uniform(0, 1, 5000) < p).astype(float)
    w = np.ones_like(p)
    parts = brier_parts(y, p, w)
    brier = float(np.mean((p - y) ** 2))
    approx = parts["reliability"] - parts["resolution"] + parts["uncertainty"]
    assert approx == pytest.approx(brier, abs=0.01)
    assert parts["reliability"] < 0.01  # these probabilities are calibrated


def _synthetic(n_matches: int = 40, rounds: int = 12, seed: int = 0) -> pl.DataFrame:
    """Rounds whose result depends on the players alive and on `defuse_margin`, nothing else."""
    rng = np.random.default_rng(seed)
    n = n_matches * rounds * 5
    rows = {name: np.zeros(n) for name in NUMERIC_V2}
    rows["alive_ct"] = rng.integers(1, 6, n).astype(float)
    rows["alive_t"] = rng.integers(1, 6, n).astype(float)
    rows["defuse_margin"] = rng.normal(0, 1, n)
    rows["smokes_ct"] = rng.integers(0, 4, n).astype(float)  # noise
    z = 0.8 * (rows["alive_ct"] - rows["alive_t"]) + 1.5 * rows["defuse_margin"]
    won = rng.uniform(0, 1, n) < 1 / (1 + np.exp(-z))
    match = np.arange(n) // (rounds * 5)
    return pl.DataFrame(
        {
            "match_id": [f"m{m:03d}" for m in match],
            "map": ["de_mirage"] * n,
            "played_at": [None] * n,
            "round": np.arange(n) // 5,
            "tick": [0] * n,
            **rows,
            "ct_won": won,
        }
    )


def test_cross_fitting_never_predicts_a_match_with_itself() -> None:
    frame = _synthetic()
    p = cross_fit(frame, folds=5, numeric=NUMERIC)
    assert not np.isnan(p).any()
    # A match's probabilities are those of the model fitted on the other folds.
    some = frame["match_id"][0]
    fold = _fold(some, 5)
    others = frame.filter(
        pl.col("match_id").map_elements(lambda m: _fold(m, 5) != fold, return_dtype=pl.Boolean)
    )
    model = fit(others, version="t", numeric=NUMERIC)
    mine = (frame["match_id"] == some).to_numpy()
    assert np.allclose(p[mine], model.predict(frame.filter(pl.col("match_id") == some)))
    with pytest.raises(ValueError, match="more than one fold"):
        cross_fit(frame.filter(pl.col("match_id") == some), folds=5, numeric=NUMERIC)


def test_a_family_joins_only_when_it_earns_its_place() -> None:
    frame = _synthetic()
    chosen, steps = select_features(frame, base=["alive_ct", "alive_t"], candidates=CANDIDATES)
    assert chosen == ["alive_ct", "alive_t", "defuse_margin"]
    assert steps[0]["kept"] == "defuse_race"
    assert steps[-1]["kept"] is None  # the grenades are noise here
    gain = steps[0]["candidates"]["defuse_race"]
    assert gain["low"] > 0
    assert gain["low"] <= gain["log_loss_gain"] <= gain["high"]


def test_compare_is_zero_against_itself() -> None:
    frame = _synthetic(n_matches=10)
    p = cross_fit(frame, numeric=NUMERIC)
    same = compare(frame, p, {"self": p})["self"]
    assert same == {"log_loss_gain": 0.0, "low": 0.0, "high": 0.0}


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
    # Nothing once the round is decided (round 12: a death to the explosion, after it).
    decided = tables["round"].select(
        "round",
        pl.min_horizontal("end_tick", "bomb_defused_tick", "bomb_exploded_tick").alias("at"),
    )
    late = credits.join(decided, on="round").filter(pl.col("tick") > pl.col("at"))
    assert late.is_empty()
    assert tables["kill"].join(decided, on="round").filter(pl.col("tick") > pl.col("at")).height
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


def test_the_swings_are_derived_and_summed_per_round(tables: dict[str, pl.DataFrame]) -> None:
    derived = derive(tables).tables()
    swing = derived["swing"]
    assert swing.schema == TABLES["swing"]
    assert set(swing["event"].unique().to_list()) <= {"kill", "plant", "defuse"}
    ds = Dataset.from_matches([{**tables, **derived}])
    values = compute(ds, ["rating.swing"])
    rounds = derived["round_player"].group_by("steamid").len()
    gained = swing.group_by("steamid").agg(pl.col("swing").cast(pl.Float64).sum())
    for row in rounds.join(gained, on="steamid", how="left").iter_rows(named=True):
        value = values.filter(pl.col("steamid") == row["steamid"])["value"].item()
        assert value == pytest.approx((row["swing"] or 0.0) * 100 / row["len"], abs=1e-6)
    # Tables derived before the swing existed: no value, rather than a wrong one.
    older = {name: frame for name, frame in {**tables, **derived}.items() if name != "swing"}
    missing = compute(Dataset.from_matches([older]), ["rating.swing"])
    assert missing["value"].null_count() == missing.height
