# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Kills of bots and disconnections in the `kill` table."""

from __future__ import annotations

import polars as pl

from untraded.parsing.core import drop_disconnections, mark_bot_victims
from untraded.parsing.schema import Side


def kills(rows: list[tuple[int, int, int, int | None, str | None, str]]) -> pl.DataFrame:
    """Rows of (tick, round, attacker, victim, victim_side, weapon); attackers are on CT."""
    return pl.DataFrame(
        {
            "tick": [r[0] for r in rows],
            "round": [r[1] for r in rows],
            "attacker": [r[2] for r in rows],
            "victim": [r[3] for r in rows],
            "attacker_side": ["CT"] * len(rows),
            "victim_side": [r[4] for r in rows],
            "weapon": [r[5] for r in rows],
        },
        schema_overrides={
            "attacker": pl.UInt64,
            "victim": pl.UInt64,
            "attacker_side": Side,
            "victim_side": Side,
        },
    )


def test_a_taken_over_bot_keeps_its_kills_and_its_death_is_nobodys() -> None:
    raw = kills(
        [
            (100, 1, 6, 1, "T", "awp"),
            (200, 1, 1, 7, "CT", "m4a1"),  # 1 now controls a bot: the kill stays credited to 1
            (300, 1, 7, 1, "T", "ak47"),  # the bot dies: a kill for 7, not a death of 1
            (400, 2, 6, 1, "T", "awp"),  # 1 can die again in round 2
        ]
    )
    notes: list[str] = []
    marked = mark_bot_victims(raw, notes)
    assert marked["victim_bot"].to_list() == [False, False, True, False]
    assert marked["victim"].to_list() == [1, 7, 1, 1]
    assert len(notes) == 1


def test_a_bot_nobody_controls_is_on_the_killer_s_opposite_side() -> None:
    marked = mark_bot_victims(kills([(100, 1, 6, None, None, "ak47")]), [])
    assert marked.select("victim_bot", "victim_side").rows() == [(True, "T")]


def test_a_disconnection_is_not_a_death() -> None:
    raw = kills([(100, 1, 3, 3, "CT", "world"), (200, 1, 6, 4, "T", "world")])
    left = pl.DataFrame(
        {"tick": [100], "victim": [3]}, schema={"tick": pl.Int64, "victim": pl.UInt64}
    )
    notes: list[str] = []
    kept = drop_disconnections(raw, left, notes)
    assert kept["tick"].to_list() == [200]
    assert notes == ["kill: 1 disconnections dropped (not deaths)"]
