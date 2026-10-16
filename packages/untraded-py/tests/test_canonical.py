# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Canonical schemas, validation on creation, and the adapter on a real demo (opt-in)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from untraded.parsing import CanonicalError, UnsupportedModeError, parse_demo
from untraded.parsing.schema import TABLES, conform
from untraded.parsing.validate import validate

DEMO = os.environ.get("UNTRADED_TEST_DEMO")


def table(name: str, rows: list[dict[str, Any]]) -> pl.DataFrame:
    """A conforming table: columns not given are null."""
    schema = TABLES[name]
    return pl.DataFrame([{col: row.get(col) for col in schema} for row in rows], schema=schema)


def valid_tables() -> dict[str, pl.DataFrame]:
    return {
        "match": table(
            "match",
            [{"match_id": "x", "rounds_played": 2, "first_round": 1, "score_a": 1, "score_b": 1}],
        ),
        "player": table("player", [{"steamid": 1, "team": "A"}, {"steamid": 2, "team": "B"}]),
        "round": table(
            "round",
            [
                {"round": 1, "start_tick": 0, "freeze_end_tick": 10, "end_tick": 50},
                {"round": 2, "start_tick": 60, "freeze_end_tick": 70, "end_tick": 90},
            ],
        ),
        "kill": table("kill", [{"tick": 20, "round": 1}, {"tick": 80, "round": 2}]),
    }


def test_valid_tables_pass() -> None:
    validate(valid_tables())


def test_score_must_add_up_to_the_last_round() -> None:
    tables = valid_tables()
    tables["match"] = tables["match"].with_columns(pl.lit(2, pl.Int16).alias("score_a"))
    with pytest.raises(CanonicalError, match="does not add up"):
        validate(tables)


def test_truncated_start_still_counts_the_missing_rounds_in_the_score() -> None:
    tables = valid_tables()
    tables["round"] = tables["round"].with_columns(pl.col("round") + 4)  # rounds 5 and 6
    tables["kill"] = tables["kill"].with_columns(pl.col("round") + 4)
    tables["match"] = tables["match"].with_columns(
        pl.lit(5, pl.Int16).alias("first_round"),
        pl.lit(4, pl.Int16).alias("score_a"),
        pl.lit(2, pl.Int16).alias("score_b"),
    )
    validate(tables)


def test_rounds_must_be_consecutive_and_ordered() -> None:
    tables = valid_tables()
    tables["round"] = tables["round"].with_columns(
        pl.when(pl.col("round") == 2).then(pl.lit(40)).otherwise(pl.col("start_tick"))
        .cast(pl.Int32).alias("start_tick")
    )  # fmt: skip
    with pytest.raises(CanonicalError, match="not ordered"):
        validate(tables)


def test_a_kill_outside_live_rounds_is_rejected() -> None:
    tables = valid_tables()
    tables["kill"] = tables["kill"].with_columns(pl.lit(7, pl.Int16).alias("round"))
    with pytest.raises(CanonicalError, match="no live round"):
        validate(tables)


def test_conform_orders_and_casts_but_refuses_missing_or_extra_columns() -> None:
    frame = table("player", [{"steamid": 1, "team": "A"}])
    shuffled = frame.select(reversed(frame.columns)).with_columns(pl.col("rank").cast(pl.Int64))
    assert conform(shuffled, "player").schema == TABLES["player"]
    with pytest.raises(CanonicalError, match="missing"):
        conform(frame.drop("name"), "player")
    with pytest.raises(CanonicalError, match="unexpected"):
        conform(frame.with_columns(pl.lit(0).alias("ping")), "player")


def test_unsupported_modes_are_refused_before_parsing(tmp_path: Path) -> None:
    with pytest.raises(UnsupportedModeError):
        parse_demo(tmp_path / "x.dem", source="valve", mode="wingman")


@pytest.mark.skipif(DEMO is None, reason="set UNTRADED_TEST_DEMO to a real demo file")
def test_parses_a_real_demo(tmp_path: Path) -> None:
    match = parse_demo(Path(str(DEMO)), source="test", mode="premier", match_id="test")
    info = match.match.row(0, named=True)
    assert info["map"].startswith("de_")
    assert info["tickrate"] == pytest.approx(64, abs=0.5)
    assert info["rounds_played"] == match.round.height > 0
    assert match.kill.height > 0
    target = match.write(tmp_path)
    assert sorted(p.name for p in target.iterdir()) == [
        "kill.parquet",
        "match.parquet",
        "player.parquet",
        "round.parquet",
    ]
    assert pl.read_parquet(target / "round.parquet").schema == TABLES["round"]
