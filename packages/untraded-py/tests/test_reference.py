# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The player's own reference (E9): a session against the 30 days before it."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl
import pytest

from untraded import fixtures
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
