# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The demo account: anonymized with the same fake ids everywhere, dated in sessions."""

from __future__ import annotations

import datetime as dt
import itertools
import json
from pathlib import Path

import polars as pl
import pytest

from untraded import demo, fixtures
from untraded.parsing import CanonicalMatch

FIXTURES = Path(__file__).parent / "fixtures"
REAL = 76561199000000000  # fixture players are renumbered 1..10: give them real-looking ids


@pytest.fixture(scope="module")
def matches() -> list[dict[str, pl.DataFrame]]:
    out = []
    for day, name in enumerate(("premier-half", "premier-abandon", "faceit-bots"), start=1):
        tables = fixtures.read(FIXTURES / name)
        ids = tables["player"]["steamid"].to_list()
        tables = fixtures.replace_players(tables, {i: REAL + i for i in ids})
        tables["match"] = tables["match"].with_columns(
            pl.lit(dt.date(2026, 10, day)).alias("played_at")
        )
        out.append(tables)
    return out


def test_nobody_real_is_left(matches: list[dict[str, pl.DataFrame]], tmp_path: Path) -> None:
    built = demo.build(matches, REAL + 1, dt.datetime(2026, 10, 31, 12, tzinfo=dt.UTC))
    for m in built:
        players = m.tables["player"]
        ids = players["steamid"].to_list()
        assert all(demo.FAKE_STEAM_BASE < i < REAL for i in ids)
        assert m.tables["match"]["server_name"][0] == "Untraded demo"
        assert demo.PROTAGONIST_NAME in players["name"].to_list()
        others = players.filter(pl.col("steamid") != demo.PROTAGONIST)
        assert others["rank"].null_count() == others.height
        kills = m.tables["kill"]
        assert all(i < REAL for i in kills["attacker"].drop_nulls().to_list())
    manifest = demo.write(built, tmp_path)
    entries = json.loads(manifest.read_text(encoding="utf-8"))
    assert [e["match_id"] for e in entries] == [m.match_id for m in built]
    for entry in entries:
        read = CanonicalMatch.read(tmp_path / "matches" / entry["match_id"])
        assert read.match_id == entry["match_id"]


def test_a_regular_teammate_keeps_the_same_fake_id(matches: list[dict[str, pl.DataFrame]]) -> None:
    mapping = demo.steam_mapping(matches, REAL + 1)
    assert mapping[REAL + 1] == demo.PROTAGONIST
    assert len(set(mapping.values())) == len(mapping)
    assert demo.fake_name(demo.PROTAGONIST) == demo.PROTAGONIST_NAME
    with pytest.raises(ValueError, match="protagonist"):
        demo.steam_mapping(matches, 1)


def test_sessions_end_before_the_given_day(matches: list[dict[str, pl.DataFrame]]) -> None:
    end = dt.datetime(2026, 10, 31, 12, tzinfo=dt.UTC)
    built = demo.build(matches, REAL + 1, end)
    starts = [m.played_at for m in built]
    assert starts == sorted(starts)
    assert starts[-1] < end
    assert len({m.match_id for m in built}) == len(built)
    assert starts[0].hour == 19
    for m in built:
        assert m.tables["match"]["played_at"][0] == m.played_at.date()


def test_matches_of_a_session_follow_each_other(matches: list[dict[str, pl.DataFrame]]) -> None:
    # The worker's session rule: at most an hour between a match's end and the next start.
    many = [matches[0]] * 9
    for i, tables in enumerate(many):
        many[i] = tables.copy()
        many[i]["match"] = tables["match"].with_columns(
            pl.lit(f"m{i}").alias("match_id"), pl.lit(dt.date(2026, 10, 1 + i)).alias("played_at")
        )
    built = demo.build(many, REAL + 1, dt.datetime(2026, 10, 31, 12, tzinfo=dt.UTC))
    gaps = []
    for previous, current in itertools.pairwise(built):
        info = previous.tables["match"].row(0, named=True)
        ended = previous.played_at + dt.timedelta(seconds=info["ticks"] / info["tickrate"])
        gaps.append(current.played_at - ended)
    within = [g for g in gaps if g <= dt.timedelta(hours=1)]
    assert len(within) == len(built) - len({m.played_at.date() for m in built})
    assert {m.played_at.date() for m in built[:3]} == {built[0].played_at.date()}  # 3, then 4...
