# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The match report of `untraded analyze` (E7)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import polars as pl
import pytest

from untraded import report
from untraded.derive import derive
from untraded.parsing import parse_demo

DEMO = os.environ.get("UNTRADED_TEST_DEMO")

TABLES = {
    "round": pl.DataFrame(
        {
            "round": [1, 2, 3],
            "score_a": [1, 1, 2],
            "score_b": [0, 1, 1],
            "winner_team": ["A", "B", "A"],
            "winner_side": ["CT", "T", "CT"],
            "reason": ["elimination", "bomb_exploded", "bomb_defused"],
        }
    ),
    "round_player": pl.DataFrame(
        {"round": [1, 1, 2, 3], "steamid": [1, 6, 6, 1], "kills": [4, 1, 2, 5]}
    ),
    "clutch": pl.DataFrame(
        {"round": [2, 3], "steamid": [6, 1], "enemies": [2, 1], "won": [True, False]}
    ),
    "team_round": pl.DataFrame(
        {
            "round": [1, 1, 2, 2, 3, 3],
            "team": ["A", "B"] * 3,
            "won": [True, False, False, True, True, False],
            "buy_type": ["pistol", "pistol", "full", "eco", "full", "full"],
        }
    ),
}
NAMES = {1: "alice", 6: "bob"}


def test_key_rounds_hold_multi_kills_won_clutches_and_upset_buys() -> None:
    rounds = report._key_rounds(TABLES, NAMES)
    assert [(kr.round, kr.events) for kr in rounds] == [
        (1, ("alice 4K",)),
        (2, ("bob wins a 1v2", "team B wins an eco round against a full buy")),
        (3, ("alice ACE",)),
    ]
    assert (rounds[1].score_a, rounds[1].score_b, rounds[1].winner_side) == (1, 1, "T")


def sample() -> report.Report:
    metrics = {m: [1.0, None] for m in report.SUMMARY}
    players = pl.DataFrame(
        {"steamid": [1, 6], "name": ["alice", "bob"], "team": ["A", "B"], **metrics},
        schema_overrides={"steamid": pl.UInt64, **dict.fromkeys(report.SUMMARY, pl.Float64)},
    )
    sides = players.select("steamid", "name", "team", *report.BY_SIDE).with_columns(
        pl.lit("CT").alias("side")
    )
    return report.Report(
        match={"map": "de_nuke", "score_a": 13, "score_b": 7, "rounds_played": 20},
        side=None,
        players=players,
        sides=sides,
        key_rounds=report._key_rounds(TABLES, NAMES),
    )


def test_table_lists_players_sides_and_key_rounds() -> None:
    text = report.render_table(sample())
    assert text.startswith("de_nuke 13-7 (20 rounds)")
    assert report.APPROX_NOTE in text
    assert "By side" in text
    assert "Key rounds" in text
    assert "R2    1-1   T (bomb_exploded)" in text


def test_json_keeps_steam_ids_as_strings_and_metric_versions() -> None:
    data = report.to_json(sample())
    json.dumps(data)
    alice = data["players"][0]
    assert alice["steamid"] == "1"
    assert alice["metrics"]["base.kills"] == 1.0
    assert alice["by_side"]["CT"]["base.adr"] == 1.0
    assert data["metric_versions"]["rating.hltv1"] == "1.0.0"
    assert data["key_rounds"][0]["score"] == [1, 0]


@pytest.mark.skipif(DEMO is None, reason="set UNTRADED_TEST_DEMO to a real demo file")
def test_report_of_a_real_demo() -> None:
    match = parse_demo(Path(str(DEMO)), source="test", mode="premier", match_id="test")
    tables = {**match.tables(), **derive(match.tables()).tables()}
    full = report.build_report(tables)
    assert full.players.height == match.player.height
    assert set(full.sides["side"]) == {"CT", "T"}
    json.dumps(report.to_json(full))
    ct = report.build_report(tables, side="CT")
    assert set(ct.sides["side"]) == {"CT"}
