# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The player's own reference (E9): a session against the 30 days before it."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from pathlib import Path

import polars as pl
import pytest

from untraded import fixtures, reference
from untraded.derive import derive
from untraded.metrics import REGISTRY, Dataset, compute
from untraded.metrics.dataset import MatchTables
from untraded.reference import ReferenceError, compare_to_self, is_total

FIXTURE = Path(__file__).parent / "fixtures" / "premier-half"
PLAYER = 1
SESSION_DAY = dt.date(2026, 10, 20)


def match(match_id: str, day: dt.date | None, *, without: int | None = None) -> MatchTables:
    """The `premier-half` fixture (5 rounds) as another match, played on `day`."""
    tables = dict(fixtures.read(FIXTURE))
    tables["match"] = tables["match"].with_columns(
        pl.lit(match_id).alias("match_id"), pl.lit(day, pl.Date).alias("played_at")
    )
    model = derive(tables).tables()
    if without is not None:
        model["round_player"] = model["round_player"].filter(pl.col("steamid") != without)
    return {**tables, **model}


def history(days_before: list[int]) -> list[MatchTables]:
    return [
        match(f"ref-{i}", SESSION_DAY - dt.timedelta(days=d)) for i, d in enumerate(days_before)
    ]


def test_the_reference_is_the_window_before_the_session_without_it() -> None:
    matches = [
        match("session", SESSION_DAY),
        *history([1, 10, 30]),  # in the window
        *history([31, 45]),  # too old
        match("undated", None),
        match("later", SESSION_DAY + dt.timedelta(days=1)),
    ]
    result = compare_to_self(matches, PLAYER, {"session"}, min_matches=1, min_rounds=1)
    assert (result.reference_from, result.reference_to) == (
        dt.date(2026, 9, 20),
        dt.date(2026, 10, 19),
    )
    assert (result.session_matches, result.session_rounds) == (1, 5)
    assert (result.reference_matches, result.reference_rounds) == (3, 15)
    assert result.enough


def test_values_are_recomputed_over_all_the_reference_rounds() -> None:
    matches = [match("session", SESSION_DAY), *history([1, 2])]
    result = compare_to_self(matches, PLAYER, {"session"}, min_matches=1, min_rounds=1)
    expected = compute(Dataset.from_matches(matches[1:])).filter(pl.col("steamid") == PLAYER)
    reference = dict(result.values.select("metric", "reference").iter_rows())
    basis = dict(result.values.select("metric", "basis").iter_rows())
    for metric, value in expected.select("metric", "value").iter_rows():
        if basis[metric] == "per_round":
            value = value / result.reference_rounds  # counts are compared per round
        assert reference[metric] == pytest.approx(value, nan_ok=True)
    assert basis["base.kills"] == "per_round"
    assert basis["base.kast"] == "value"
    # the same match three times: no difference
    deltas = result.values["delta"].drop_nulls().drop_nans()
    assert deltas.abs().max() == pytest.approx(0.0)


def test_not_enough_reference_is_not_shown() -> None:
    matches = [match("session", SESSION_DAY), *history([1, 2, 3, 4])]
    # 4 matches (default minimum 5), and 20 rounds (default minimum 100)
    result = compare_to_self(matches, PLAYER, {"session"})
    assert not result.enough
    assert result.reference_matches == 4
    assert result.values["reference"].null_count() == result.values.height
    assert result.values["delta"].null_count() == result.values.height
    assert result.values["session"].null_count() < result.values.height


def test_matches_the_player_did_not_play_are_ignored() -> None:
    matches = [
        match("session", SESSION_DAY),
        *history([1]),
        match("other", SESSION_DAY - dt.timedelta(days=2), without=PLAYER),
    ]
    result = compare_to_self(matches, PLAYER, {"session"}, min_matches=1, min_rounds=1)
    assert result.reference_matches == 1


def test_the_session_must_be_dated_and_played_by_the_player() -> None:
    with pytest.raises(ReferenceError, match="played_at"):
        compare_to_self([match("session", None)], PLAYER, {"session"})
    with pytest.raises(ReferenceError, match="without this player"):
        compare_to_self([match("session", SESSION_DAY)], PLAYER, {"session", "unknown"})


def test_totals_are_exactly_the_metrics_that_add_up_over_matches() -> None:
    """Twice the same match: a total doubles, a rate does not. Guards every future metric."""
    once = compute(Dataset.from_matches([match("a", SESSION_DAY)]))
    twice = compute(Dataset.from_matches([match("a", SESSION_DAY), match("b", SESSION_DAY)]))
    both = once.join(twice, on=["steamid", "metric"], suffix="_twice")
    for metric in sorted(m.id for m in REGISTRY.values() if m.kind == "value"):
        rows = both.filter((pl.col("metric") == metric) & (pl.col("value").abs() > 1e-9))
        if rows.is_empty():
            continue  # zero everywhere on this fixture: nothing to tell
        doubled = bool(((rows["value_twice"] - 2 * rows["value"]).abs() < 1e-6).all())
        same = bool(((rows["value_twice"] - rows["value"]).abs() < 1e-6).all())
        assert doubled != same, metric
        assert is_total(metric) == doubled, f"{metric}: total={is_total(metric)}"


def per_match(values: Sequence[float | None], version: str = "1.0.0") -> list[pl.DataFrame]:
    return [
        pl.DataFrame(
            {"metric": ["m"], "version": [version], "value": [v]},
            schema_overrides={"value": pl.Float64},
        )
        for v in values
    ]


def spread_of(values: Sequence[float | None]) -> pl.DataFrame:
    return reference.spread(per_match(values), min_matches=10)


def test_the_spread_is_the_linear_interpolation_of_the_per_match_values() -> None:
    # 11 values: the 10th percentile sits at index 1, the 90th at index 9 (numpy's default).
    found = spread_of([float(v) for v in range(11)][::-1])
    assert found.row(0, named=True) == {
        "metric": "m",
        "version": "1.0.0",
        "reference_p10": 1.0,
        "reference_p90": 9.0,
    }
    # 12 values 0..11: positions 1.1 and 9.9 are between two order statistics.
    found = spread_of([float(v) for v in range(12)])
    assert found["reference_p10"][0] == pytest.approx(1.1)
    assert found["reference_p90"][0] == pytest.approx(9.9)


def test_the_spread_needs_enough_matches_with_a_value() -> None:
    assert reference.spread(per_match([1.0] * 9), min_matches=10).is_empty()
    assert reference.spread([], min_matches=10).is_empty()
    # 12 matches but only 9 with a value (missing and NaN are left out): no spread for it.
    values: list[float | None] = [None, float("nan"), None, *[float(v) for v in range(9)]]
    found = spread_of(values)
    assert found["reference_p10"].null_count() == 1
    assert found["reference_p90"].null_count() == 1
    # And 10 values with a NaN among them: the NaN is not a value.
    found = spread_of([float("nan"), *[float(v) for v in range(10)]])
    assert found["reference_p10"][0] == pytest.approx(0.9)


def test_the_spread_keeps_a_metric_version_apart() -> None:
    old = per_match([1.0] * 10, "1.0.0")
    new = per_match([5.0] * 10, "2.0.0")
    found = reference.spread([*old, *new], min_matches=10)
    assert dict(zip(found["version"], found["reference_p10"], strict=True)) == {
        "1.0.0": 1.0,
        "2.0.0": 5.0,
    }


def test_a_match_played_for_a_few_rounds_has_no_values(monkeypatch: pytest.MonkeyPatch) -> None:
    tables = match("a", SESSION_DAY)  # 5 rounds
    assert reference.match_values(tables, PLAYER) is None  # under the 10 rounds minimum
    monkeypatch.setattr(reference, "MIN_SPREAD_ROUNDS", 5)
    values = reference.match_values(tables, PLAYER)
    assert values is not None
    # Totals are per round, as in the comparison.
    kills = values.filter(pl.col("metric") == "base.kills")["value"][0]
    pooled = compute(Dataset.from_matches([tables])).filter(
        (pl.col("steamid") == PLAYER) & (pl.col("metric") == "base.kills")
    )["value"][0]
    assert kills == pytest.approx(pooled / 5)


def test_the_comparison_carries_the_spread_of_the_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(reference, "MIN_SPREAD_ROUNDS", 5)
    matches = [match("session", SESSION_DAY), *history(list(range(1, 11)))]  # 10 reference matches
    result = compare_to_self(matches, PLAYER, {"session"}, min_matches=1, min_rounds=1)
    shown = result.values.filter(pl.col("reference_p10").is_not_null())
    assert shown.height > 0
    # The same match ten times: every percentile is the match's own value, in the reference's
    # unit (per round for totals).
    for row in shown.iter_rows(named=True):
        assert row["reference_p10"] == pytest.approx(row["reference"])
        assert row["reference_p90"] == pytest.approx(row["reference"])
    kills = result.values.filter(pl.col("metric") == "base.kills").row(0, named=True)
    assert kills["basis"] == "per_round"
    assert kills["reference_p10"] == pytest.approx(kills["reference"])  # per round, not a count


def test_the_spread_is_not_shown_below_the_minimum_of_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(reference, "MIN_SPREAD_ROUNDS", 5)
    matches = [match("session", SESSION_DAY), *history(list(range(1, 10)))]  # 9 reference matches
    result = compare_to_self(matches, PLAYER, {"session"}, min_matches=1, min_rounds=1)
    assert result.enough
    assert result.values["reference"].null_count() < result.values.height
    assert result.values["reference_p10"].null_count() == result.values.height
    assert result.values["reference_p90"].null_count() == result.values.height
    # The minimum is a parameter.
    lower = compare_to_self(
        matches, PLAYER, {"session"}, min_matches=1, min_rounds=1, min_spread_matches=9
    )
    assert lower.values["reference_p10"].null_count() < lower.values.height


def test_no_spread_without_a_reference() -> None:
    matches = [match("session", SESSION_DAY), *history([1, 2])]
    result = compare_to_self(matches, PLAYER, {"session"})  # not enough matches
    assert not result.enough
    assert result.values["reference_p10"].null_count() == result.values.height
    assert result.values["reference_p90"].null_count() == result.values.height


def test_an_infinite_value_is_not_a_percentile() -> None:
    values = [float("inf"), float("-inf"), *[float(v) for v in range(10)]]
    found = spread_of(values)
    assert found["reference_p10"][0] == pytest.approx(0.9)
    assert found["reference_p90"][0] == pytest.approx(8.1)
