# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Links from damage and blinds to the grenade that caused them."""

from __future__ import annotations

from typing import Any

import polars as pl

from untraded.parsing.grenades import link_grenades
from untraded.parsing.schema import TABLES


def table(name: str, rows: list[dict[str, Any]]) -> pl.DataFrame:
    schema = TABLES[name]
    return pl.DataFrame([{col: row.get(col) for col in schema} for row in rows], schema=schema)


GRENADES = table(
    "grenade",
    [
        # player 1: an HE, then a molotov burning from 2100 to 2550
        {"grenade_id": 1, "thrower": 1, "type": "he", "throw_tick": 1000, "detonate_tick": 1100},
        {
            "grenade_id": 2,
            "thrower": 1,
            "type": "molotov",
            "throw_tick": 2000,
            "detonate_tick": 2100,
            "end_tick": 2550,
        },
        # player 2: a flash detonating at 3000
        {"grenade_id": 3, "thrower": 2, "type": "flash", "throw_tick": 2900, "detonate_tick": 3000},
    ],
)


def test_damage_links_to_the_attacker_grenade_of_that_kind_and_time() -> None:
    damage = table(
        "damage",
        [
            {"tick": 1100, "attacker": 1, "weapon": "hegrenade"},
            {"tick": 2400, "attacker": 1, "weapon": "inferno"},
            {"tick": 2401, "attacker": 1, "weapon": "ak47"},  # not a grenade
            {"tick": 2402, "attacker": 2, "weapon": "inferno"},  # player 2 threw no fire
            {"tick": 9000, "attacker": 1, "weapon": "inferno"},  # long after the fire went out
        ],
    )
    linked, _ = link_grenades(damage, table("blind", []), GRENADES, tickrate=64)
    assert linked["grenade_id"].to_list() == [1, 2, None, None, None]


def test_blinds_link_to_the_flash_detonating_on_their_tick() -> None:
    blind = table(
        "blind",
        [{"tick": 3000, "victim": 7, "flasher": 2}, {"tick": 3001, "victim": 8, "flasher": 2}],
    )
    _, linked = link_grenades(table("damage", []), blind, GRENADES, tickrate=64)
    assert linked["grenade_id"].to_list() == [3, None]
