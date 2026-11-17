# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The demo's team: the demo's own matches with the same roster on the protagonist's side,
fresh opponents in every match, and nothing of the solo demo's identities but the protagonist."""

from __future__ import annotations

import datetime as dt
import itertools
import json
from pathlib import Path

import polars as pl
import pytest

from untraded import demo, demo_team, fixtures
from untraded.parsing import CanonicalMatch

FIXTURES = Path(__file__).parent / "fixtures"
REAL = 76561199000000000


@pytest.fixture(scope="module")
def solo(tmp_path_factory: pytest.TempPathFactory) -> list[demo.DemoMatch]:
    matches = []
    for day, name in enumerate(("premier-half", "premier-abandon", "faceit-bots"), start=1):
        tables = fixtures.read(FIXTURES / name)
        ids = tables["player"]["steamid"].to_list()
        tables = fixtures.replace_players(tables, {i: REAL + i for i in ids})
        tables["match"] = tables["match"].with_columns(
            pl.lit(dt.date(2026, 10, day)).alias("played_at")
        )
        matches.append(tables)
    built = demo.build(matches, REAL + 1, dt.datetime(2026, 10, 31, 12, tzinfo=dt.UTC))
    root = tmp_path_factory.mktemp("demo")
    demo.write(built, root)
    return demo.read(root)  # as `untraded demo team` reads it


def test_the_team_has_the_same_roster_and_new_opponents(solo: list[demo.DemoMatch]) -> None:
    team = demo_team.build(solo)
    roster = {p.steam_id for p in demo_team.PEOPLE if p.roster is not None}
    solo_ids = {s for m in solo for s in m.tables["player"]["steamid"].to_list()}
    opponents: list[set[int]] = []
    assert len(team.matches) == len(solo)
    for match, source in zip(team.matches, solo, strict=True):
        players = match.tables["player"]
        side = players.filter(pl.col("steamid") == demo.PROTAGONIST)["team"][0]
        ours = set(players.filter(pl.col("team") == side)["steamid"].to_list())
        theirs = set(players.filter(pl.col("team") != side)["steamid"].to_list())
        assert demo.PROTAGONIST in ours
        assert ours <= roster
        assert all(demo_team.OPPONENT_BASE <= s < demo.REAL_LOWEST for s in theirs)
        # Nobody of the solo demo but the protagonist, in any table holding a steamid.
        for table, columns in fixtures.PLAYER_COLUMNS.items():
            for column in columns:
                values = match.tables[table][column]
                values = values.explode() if values.dtype == pl.List else values
                assert not (set(values.drop_nulls().to_list()) & solo_ids) - {demo.PROTAGONIST, 0}
        opponents.append(theirs)
        # The real match: same rounds, kills and damage.
        for table in ("round", "kill", "damage", "grenade", "shot"):
            assert match.tables[table].height == source.tables[table].height
        assert match.match_id != source.match_id
        assert match.played_at == source.played_at - demo_team.SHIFT
        info = match.tables["match"].row(0, named=True)
        assert info["mode"] == match.mode
        assert info["played_at"] == match.played_at.date()
        others = players.filter(pl.col("steamid") != demo.PROTAGONIST)
        assert others["rank"].null_count() == others.height
    for a, b in itertools.pairwise(opponents):
        assert not a & b  # an opponent is never met twice
    # The same build gives the same ids: the import is replayable.
    assert [m.match_id for m in demo_team.build(solo).matches] == [m.match_id for m in team.matches]


def test_invented_names_are_not_the_solo_demos() -> None:
    solo_names = set(demo.PSEUDOS) | {demo.PROTAGONIST_NAME}
    team_names = {p.name for p in demo_team.PEOPLE if p is not demo_team.OWNER}
    assert not team_names & solo_names
    assert not set(demo_team.OPPONENT_NAMES) & (solo_names | team_names)
    ids = [p.steam_id for p in demo_team.PEOPLE]
    assert len(set(ids)) == len(ids)
    assert all(demo.FAKE_STEAM_BASE < i < demo.REAL_LOWEST for i in ids)


def test_the_review_points_at_real_rounds(solo: list[demo.DemoMatch], tmp_path: Path) -> None:
    team = demo_team.build(solo)
    manifest = json.loads(demo_team.write(team, tmp_path).read_text(encoding="utf-8"))
    rounds = {}
    for entry in manifest["matches"]:
        read = CanonicalMatch.read(tmp_path / "matches" / entry["match_id"])
        assert read.match_id == entry["match_id"]
        rounds[entry["match_id"]] = {
            r["round"]: (r["start_tick"], r["end_tick"])
            for r in read.tables()["round"].iter_rows(named=True)
        }
    people = {p["steam_id"]: p for p in manifest["people"]}
    assert manifest["comments"]
    for c in manifest["comments"]:
        start, end = rounds[c["match_id"]][c["round"]]
        assert c["tick"] is None or start <= c["tick"] <= end
        assert people[c["author"]]["role"] in ("coach", "player")
        assert 1 <= len(c["body"]) <= 2000
    for t in manifest["tags"]:
        assert t["round"] in rounds[t["match_id"]]
        assert all(1 <= len(label) <= 32 for label in t["labels"])
    assert [p["name"] for p in manifest["playlists"]] == [p[0] for p in demo_team.PLAYLISTS]
    for p in manifest["playlists"]:
        assert all(r["round"] in rounds[r["match_id"]] for r in p["rounds"])
    assert {m["sent_by"] for m in manifest["matches"]} <= set(people)


def test_a_retake_and_a_post_plant_are_found() -> None:
    tables = fixtures.read(FIXTURES / "premier-half")
    rows = tables["round"]
    side = str(rows["ct_team"][0])
    found = demo_team.moments(tables, side)
    planted = rows.filter(pl.col("bomb_planted_tick").is_not_null())
    assert {m.round for m in found} >= set(planted["round"].to_list())
    for m in found:
        r = rows.filter(pl.col("round") == m.round).row(0, named=True)
        if m.kind.startswith("retake"):
            assert r["ct_team"] == side
            assert m.tick in (r["bomb_planted_tick"], None)
        if m.kind.startswith("post_plant"):
            assert r["t_team"] == side
        assert m.kind.endswith("_won") == (r["winner_team"] == side)
