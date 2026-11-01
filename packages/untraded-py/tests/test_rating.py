# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The Untraded Rating: its scale, the published one, and the metrics built on it."""

from __future__ import annotations

import statistics
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from untraded import fixtures
from untraded.derive import derive
from untraded.metrics import REGISTRY, Dataset, compute, compute_table
from untraded.winprob import default_model
from untraded.winprob.rating import RatingScale, default_scale, fit_scale
from untraded.winprob.rating2 import default_rating

FIXTURES = Path(__file__).parent / "fixtures"
NAMES = ("premier-half", "premier-abandon", "faceit-bots")


@pytest.fixture(scope="module")
def matches() -> list[dict[str, pl.DataFrame]]:
    out = []
    for name in NAMES:
        tables = fixtures.read(FIXTURES / name)
        out.append({**tables, **derive(tables).tables()})
    return out


def test_the_average_player_of_the_measured_matches_rates_one(
    matches: list[dict[str, pl.DataFrame]],
) -> None:
    scale = fit_scale(matches, version="test", model="1.0")
    swings, rounds = [], []
    for tables in matches:
        ds = Dataset.from_matches([tables])
        values = compute(ds, ["rating.swing"]).join(ds.rounds_played(), on="steamid")
        swings += values["value"].to_list()
        rounds += values["rounds"].to_list()
    pooled = sum(s * n for s, n in zip(swings, rounds, strict=True)) / sum(rounds)
    assert scale.rate(pooled) == pytest.approx(1.0, abs=1e-3)
    assert scale.scale > 0
    assert scale.rate(pooled + scale.scale) == pytest.approx(2.0, abs=1e-3)
    assert scale.trained_on["player_matches"] == len(swings)
    # k's defining property: the rating spreads over the player-matches as HLTV 1.0 does.
    hltv = []
    for tables in matches:
        ds = Dataset.from_matches([tables])
        hltv += compute(ds, ["rating.hltv1"])["value"].to_list()
    assert statistics.stdev([scale.rate(s) for s in swings]) == pytest.approx(
        statistics.stdev(hltv), rel=1e-3
    )
    assert RatingScale.from_json(scale.to_json()) == scale


def test_the_published_scales_go_with_the_published_model() -> None:
    scale = default_scale()
    assert scale.model == default_model().version
    assert scale.scale > 0
    assert scale.trained_on["matches"] > 0
    # A new rating file is a new version of the rating: they move together.
    rating = default_rating()
    assert rating.model == default_model().version
    assert (rating.version, REGISTRY["rating.untraded"].version) == ("2.0", "2.0.0")


def test_the_rating_adds_up_from_its_parts(matches: list[dict[str, pl.DataFrame]]) -> None:
    ds = Dataset.from_matches([matches[0]])
    values = compute(ds, ["rating.untraded"]).select("steamid", "value")
    parts = compute_table(ds, "rating.untraded_parts")
    margins = compute_table(ds, "rating.untraded_margin")
    totals = parts.group_by("steamid").agg(pl.col("points").sum())
    joined = values.join(totals, on="steamid").join(margins, on="steamid")
    assert joined.height == ds.players().height
    for row in joined.iter_rows(named=True):
        assert row["points"] == pytest.approx(row["value"], abs=1e-6)
        assert row["margin"] > 0  # wide: the fixture has 5 rounds
        assert row["rounds"] > 1
    assert set(parts["part"].unique().to_list()) == {
        "shooting",
        "utility",
        "trade",
        "objective",
        "taken",
        "team",
        "balance",
        "baseline",
    }


def test_the_average_player_of_a_match_rates_one(matches: list[dict[str, pl.DataFrame]]) -> None:
    for tables in matches:
        ds = Dataset.from_matches([tables])
        values = compute(ds, ["rating.untraded", "rating.untraded_level"]).pivot(
            "metric", index="steamid", values="value"
        )
        rounds = compute_table(ds, "rating.untraded_margin").select("steamid", "rounds")
        joined = values.join(rounds, on="steamid").drop_nulls()
        assert joined.height > 0
        w = joined["rounds"].to_numpy().astype(float)
        for name in ("rating.untraded", "rating.untraded_level"):
            assert np.average(joined[name].to_numpy(), weights=w) == pytest.approx(1.0, abs=1e-9)
        # The level is closer to 1.00 than the match rating: it is the rating to expect.
        spread = joined.select(
            (pl.col("rating.untraded") - 1).abs().mean().alias("match"),
            (pl.col("rating.untraded_level") - 1).abs().mean().alias("level"),
        ).row(0, named=True)
        assert spread["level"] < spread["match"]


@pytest.mark.parametrize("side", [None, "CT", "T"])
def test_the_parts_add_up_on_mixed_matches_and_sides(
    matches: list[dict[str, pl.DataFrame]], side: str | None
) -> None:
    older = {name: frame for name, frame in matches[1].items() if name != "ledger"}
    ds = Dataset.from_matches([matches[0], older, matches[2]])
    if side is not None:
        ds = ds.split(side=side)
    values = compute(ds, ["rating.untraded"]).drop_nulls("value")
    totals = (
        compute_table(ds, "rating.untraded_parts").group_by("steamid").agg(pl.col("points").sum())
    )
    joined = values.join(totals, on="steamid")
    assert joined.height == values.height > 0
    for row in joined.iter_rows(named=True):
        assert row["points"] == pytest.approx(row["value"], abs=1e-6)


def test_without_a_ledger_there_is_no_rating(matches: list[dict[str, pl.DataFrame]]) -> None:
    older = {name: frame for name, frame in matches[0].items() if name != "ledger"}
    ds = Dataset.from_matches([older])
    values = compute(ds, ["rating.untraded", "rating.untraded_level"])
    assert values["value"].null_count() == values.height
    assert compute_table(ds, "rating.untraded_parts").is_empty()
    assert compute_table(ds, "rating.untraded_margin").is_empty()


def test_a_broken_scale_file_is_refused() -> None:
    good = default_scale().to_json()
    for broken in (
        good.replace('"scale": 12.8914', '"scale": 0'),
        good.replace('"scale": 12.8914', '"scale": NaN'),
        good.replace('"mean": 0.4446', '"mean": "x"'),
    ):
        with pytest.raises(ValueError, match="scale"):
            RatingScale.from_json(broken)


def test_a_ledger_that_fails_leaves_the_match_without_a_rating(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from untraded.winprob import ledger as ledger_module

    monkeypatch.setattr(ledger_module, "MAX_PENDING", 0)
    tables = fixtures.read(FIXTURES / "premier-half")
    derived = derive(tables).tables()
    assert derived["ledger"].is_empty()
    assert not derived["round_player"].is_empty()  # the rest of the analysis stands
    values = compute(Dataset.from_matches([{**tables, **derived}]), ["rating.untraded"])
    assert values["value"].null_count() == values.height


def test_a_sides_level_is_centred_on_the_whole_match(
    matches: list[dict[str, pl.DataFrame]],
) -> None:
    # Each side's match rating and level are both measured against the whole match: the CT and
    # T rows of a player, weighted by rounds, average to the player's match values.
    ds = Dataset.from_matches([matches[0]])
    whole = compute(ds, ["rating.untraded_level"]).select("steamid", pl.col("value").alias("all"))
    rounds = ds.round_players().group_by("steamid", "side").agg(pl.len().alias("n"))
    sides = []
    for side in ("CT", "T"):
        values = compute(ds.split(side=side), ["rating.untraded_level"]).drop_nulls("value")
        sides.append(values.select("steamid", "value", pl.lit(side).alias("side")))
    per_side = (
        pl.concat(sides)
        .join(rounds.with_columns(pl.col("side").cast(pl.String)), on=["steamid", "side"])
        .group_by("steamid")
        .agg(((pl.col("value") * pl.col("n")).sum() / pl.col("n").sum()).alias("mixed"))
        .join(whole, on="steamid")
    )
    assert per_side.height > 0
    # Not equal (the box is not linear in the side split's averages of a ratio), but close.
    assert float(np.max(np.abs(per_side["mixed"].to_numpy() - per_side["all"].to_numpy()))) < 0.25
