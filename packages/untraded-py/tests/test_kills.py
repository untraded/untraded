# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Repeated deaths in the kill table (bots taken over by a dead player)."""

from __future__ import annotations

import polars as pl

from untraded.parsing.core import drop_repeated_deaths


def test_a_taken_over_bot_keeps_its_kills_and_its_death_is_dropped() -> None:
    raw = pl.DataFrame(
        {
            "tick": [100, 200, 300, 400],
            "round": [1, 1, 1, 2],
            "attacker": [6, 1, 7, 6],
            "victim": [1, 7, 1, 1],
            "weapon": ["awp", "m4a1", "ak47", "awp"],
        }
    )
    notes: list[str] = []
    cleaned = drop_repeated_deaths(raw, notes)
    # 1 dies at 100, then controls a bot: its kill at 200 stays credited to 1, the bot's death
    # at 300 is dropped; 1 can die again in round 2
    assert cleaned.select("tick", "attacker", "victim").rows() == [
        (100, 6, 1),
        (200, 1, 7),
        (400, 6, 1),
    ]
    assert len(notes) == 1
