# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Cleaning of impossible player_death events in the kill table."""

from __future__ import annotations

import polars as pl

from untraded.parsing.core import drop_ghost_kills


def test_ghost_kills_are_cleaned_in_the_kill_table() -> None:
    raw = pl.DataFrame(
        {
            "tick": [100, 200, 300, 400],
            "round": [1, 1, 1, 1],
            "attacker": [6, 1, 7, 1],
            "victim": [1, 7, 1, 8],
            "weapon": ["awp", "awp", "ak47", "hegrenade"],
            "attacker_side": ["T", "CT", "T", "CT"],
        }
    )
    notes: list[str] = []
    cleaned = drop_ghost_kills(raw, notes)
    # 1 died at 100: its awp kill at 200 has no attacker, its second death at 300 is dropped,
    # and its grenade can still kill at 400
    assert cleaned.select("tick", "attacker").rows() == [(100, 6), (200, None), (400, 1)]
    assert len(notes) == 2
