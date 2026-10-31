# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The Untraded Rating: its scale, the published one, and the metrics built on it."""

from __future__ import annotations

import statistics
from pathlib import Path

import polars as pl
import pytest

from untraded import fixtures
from untraded.derive import derive
from untraded.metrics import REGISTRY, Dataset, compute, compute_table
from untraded.winprob import default_model
from untraded.winprob.rating import RatingScale, default_scale, fit_scale

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


def test_the_published_scale_goes_with_the_published_model() -> None:
    scale = default_scale()
    assert scale.model == default_model().version
    assert scale.scale > 0
    assert scale.trained_on["matches"] > 0
    # A new scale is a new version of the rating: they move together.
    assert (scale.version, REGISTRY["rating.untraded"].version) == ("1.0", "1.0.0")


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
        "kills",
        "deaths",
        "plants",
        "defuses",
        "baseline",
    }


@pytest.mark.parametrize("side", [None, "CT", "T"])
def test_the_parts_add_up_on_mixed_matches_and_sides(
    matches: list[dict[str, pl.DataFrame]], side: str | None
) -> None:
    older = {name: frame for name, frame in matches[1].items() if name != "swing"}
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


def test_without_swings_there_is_no_rating(matches: list[dict[str, pl.DataFrame]]) -> None:
    older = {name: frame for name, frame in matches[0].items() if name != "swing"}
    ds = Dataset.from_matches([older])
    values = compute(ds, ["rating.untraded"])
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
