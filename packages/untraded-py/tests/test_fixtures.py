# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Anonymized fixtures (ADR 0010): non-regression of derived tables and metrics in CI, and of
the parser when the source demos are available."""

from __future__ import annotations

import math
import os
import tomllib
from pathlib import Path
from typing import Any

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from untraded import fixtures
from untraded.cli import _round_range
from untraded.parsing import parse_demo
from untraded.parsing.schema import TABLES

FIXTURES = Path(__file__).parent / "fixtures"
NAMES = sorted(p.name for p in FIXTURES.iterdir() if (p / fixtures.META).exists())
MANIFEST = Path(__file__).parents[3] / "corpus" / "manifest.toml"
CORPUS = os.environ.get("UNTRADED_CORPUS_DIR")
SOURCES = os.environ.get("UNTRADED_FIXTURE_SOURCES")
"""A private TOML file, `<fixture name> = "<corpus demo id>"`: the source demos are not named in
this public repository (the manifest would date the matches and lead back to the players)."""


def test_the_three_fixtures_exist() -> None:
    assert NAMES == ["faceit-bots", "premier-abandon", "premier-half"]


@pytest.mark.parametrize("name", NAMES)
def test_metrics_match_the_expected_values(name: str) -> None:
    """Fails when a change moves a metric. If the change is intended, run
    `just fixtures-expect` and review the diff."""
    directory = FIXTURES / name
    actual = fixtures.expected_metrics(fixtures.read(directory))
    _assert_close(actual, fixtures.read_expected(directory), path=name)


@pytest.mark.parametrize("name", NAMES)
def test_fixtures_hold_no_personal_data(name: str) -> None:
    tables = fixtures.read(FIXTURES / name)
    players = tables["player"]
    assert players["steamid"].to_list() == list(range(1, players.height + 1))
    assert all(n[0] in "AB" and n[1:].isdigit() for n in players["name"].to_list())
    assert players["rank"].null_count() == players["comp_wins"].null_count() == players.height
    match = tables["match"].row(0, named=True)
    assert match["match_id"] == f"fixture-{name}"
    assert match["server_name"] == "anonymized"
    assert match["played_at"] is match["team_a_name"] is match["team_b_name"] is None
    for table, columns in fixtures.PLAYER_COLUMNS.items():
        for column in columns:
            values = tables[table][column]
            flat = values.explode() if values.dtype == pl.List else values
            assert set(flat.drop_nulls().to_list()) <= {0, *range(1, players.height + 1)}
    for table, columns in fixtures.ITEM_COLUMNS.items():
        for column in columns:
            items = set(tables[table][column].explode().drop_nulls().to_list())
            assert not {i for i in items if "nife" in i or "ayonet" in i} - {fixtures.KNIFE}
    for table, columns in fixtures.ITEM_NAME_COLUMNS.items():
        for column in columns:
            items = set(tables[table][column].drop_nulls().to_list())
            assert not {i for i in items if "nife" in i or "ayonet" in i} - {fixtures.KNIFE}
    for table, columns in fixtures.WEAPON_COLUMNS.items():
        for column in columns:
            weapons = set(tables[table][column].to_list())
            assert not {w for w in weapons if w.startswith(("knife", "bayonet"))} - {"knife"}
    assert "demo" not in fixtures.read_meta(FIXTURES / name)


def test_every_steamid_column_of_the_schema_is_anonymized() -> None:
    """A new steamid column in the canonical schema must be added to PLAYER_COLUMNS."""
    steamid_types = (pl.UInt64, pl.List(pl.UInt64))
    columns = {
        (table, column)
        for table, schema in TABLES.items()
        for column, dtype in schema.items()
        if dtype in steamid_types
    }
    listed = {(t, c) for t, cs in fixtures.PLAYER_COLUMNS.items() for c in cs}
    assert columns == listed


def test_extract_keeps_a_valid_window_with_the_real_score() -> None:
    tables = fixtures.read(FIXTURES / "premier-half")
    window = fixtures.extract(tables, 12, 13)
    info = window["match"].row(0, named=True)
    assert (info["first_round"], info["rounds_played"]) == (12, 2)
    assert info["score_a"] + info["score_b"] == 13
    assert window["kill"]["round"].unique().sort().to_list() == [12, 13]
    thrown = window["grenade"]["grenade_id"].to_list()
    assert window["grenade_path"]["grenade_id"].is_in(thrown).all()
    assert set(window["player"]["rounds_on_team"].to_list()) == {2}
    fixtures.anonymize(window, "window")  # validates


def test_extract_refuses_rounds_outside_the_match() -> None:
    with pytest.raises(fixtures.FixtureError, match="not all in the match"):
        fixtures.extract(fixtures.read(FIXTURES / "premier-half"), 14, 20)


def test_anonymize_refuses_a_steamid_that_is_not_a_player() -> None:
    tables = fixtures.read(FIXTURES / "premier-half")
    leaked = tables["kill"].with_columns(
        pl.when(pl.int_range(pl.len()) == 0)
        .then(pl.lit(76561197960265728, pl.UInt64))
        .otherwise(pl.col("attacker"))
        .alias("attacker")
    )
    with pytest.raises(fixtures.FixtureError, match=r"kill\.attacker"):
        fixtures.anonymize({**tables, "kill": leaked}, "leak")


@pytest.mark.parametrize(("text", "bounds"), [("11-15", (11, 15)), ("7", (7, 7))])
def test_round_range(text: str, bounds: tuple[int, int]) -> None:
    assert _round_range(text) == bounds


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.skipif(
    CORPUS is None or SOURCES is None,
    reason="set UNTRADED_CORPUS_DIR and UNTRADED_FIXTURE_SOURCES to check the parser",
)
def test_parser_still_produces_the_fixture(name: str) -> None:
    """Parses the source demo again and compares the extract with the committed fixture."""
    directory = FIXTURES / name
    meta = fixtures.read_meta(directory)
    source = tomllib.loads(Path(str(SOURCES)).read_text(encoding="utf-8")).get(name)
    if source is None:
        pytest.skip(f"{name} has no source in {SOURCES}")
    demos = {d["id"]: d for d in tomllib.loads(MANIFEST.read_text(encoding="utf-8"))["demo"]}
    found = list((Path(str(CORPUS)) / "demos").glob(demos[source]["sha256"] + ".*"))
    if not found:
        pytest.skip(f"{source} is not in the local corpus")
    first, last = meta["rounds"]
    tables = parse_demo(found[0], source="upload", mode=meta["mode"]).tables()
    fresh = fixtures.anonymize(fixtures.extract(tables, first, last), name)
    for table, frame in fixtures.read(directory).items():
        assert_frame_equal(fresh[table], frame, check_exact=False, rel_tol=1e-6)


def _assert_close(actual: Any, expected: Any, path: str) -> None:
    if isinstance(expected, dict):
        assert isinstance(actual, dict), path
        assert sorted(actual) == sorted(expected), f"{path}: keys differ"
        for key in expected:
            _assert_close(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(expected, list):
        assert isinstance(actual, list), path
        assert len(actual) == len(expected), f"{path}: {len(actual)} rows, expected {len(expected)}"
        for i, (a, e) in enumerate(zip(actual, expected, strict=True)):
            _assert_close(a, e, f"{path}[{i}]")
    elif isinstance(expected, float) and isinstance(actual, (int, float)):
        assert math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9), (
            f"{path}: {actual} != {expected}"
        )
    else:
        assert actual == expected, f"{path}: {actual!r} != {expected!r}"
