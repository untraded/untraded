# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Economy metrics (metrics-v1 § 5) on hand-made tables."""

from __future__ import annotations

from typing import Any

import polars as pl

from untraded.metrics import Dataset, compute, compute_table

# Player 1 (team A) against 6 (team B), three rounds.
ROUND_PLAYER = pl.DataFrame(
    {
        "round": [1, 1, 2, 2, 3, 3],
        "steamid": [1, 6] * 3,
        "team": ["A", "B"] * 3,
        "side": ["CT", "T"] * 3,
        "team_won": [False, True, True, False, True, False],
    }
)
TEAM_ROUND = pl.DataFrame(
    {
        "round": [1, 1, 2, 2, 3, 3],
        "team": ["A", "B"] * 3,
        "buy_type": ["pistol", "pistol", "eco", "full", "eco", "full"],
    }
)
DEATH = pl.DataFrame(
    {
        "round": [1, 2, 3],
        "tick": [100, 300, 500],
        "victim": [1, 6, 6],
        "killer": [6, 1, 1],
        "is_enemy_kill": [True, True, True],
    }
)
KILL = pl.DataFrame(
    {
        "tick": [100, 300, 500],
        "victim": [1, 6, 6],
        "victim_equip_value": [700, 5600, 4900],
        "victim_inventory": [["knife", "USP-S"], ["knife", "Glock-18", "AWP"], ["AK-47"]],
    }
)
INVENTORY_CHANGE = pl.DataFrame(
    {
        "tick": [50, 50, 250, 450],
        "round": [1, 1, 2, 3],
        "steamid": [1, 6, 1, 1],
        "inventory": [["USP-S"], ["Glock-18"], ["P250", "MP9"], ["P250", "Nova"]],
    }
)


def dataset() -> Dataset:
    return Dataset.from_matches(
        [
            {
                "match": pl.DataFrame({"match_id": ["m"], "map": ["de_nuke"]}),
                "round_player": ROUND_PLAYER,
                "team_round": TEAM_ROUND,
                "death": DEATH,
                "kill": KILL,
                "inventory_change": INVENTORY_CHANGE,
            }
        ]
    )


def table(metric: str, ds: Dataset | None = None) -> list[dict[str, Any]]:
    out = compute_table(ds or dataset(), metric)
    return out.drop("metric", "version", "params").to_dicts()


def test_buy_type_rounds_and_win_pct() -> None:
    assert table("eco.buy_type") == [
        {"steamid": 1, "buy_type": "eco", "rounds": 2, "win_pct": 100.0},
        {"steamid": 1, "buy_type": "pistol", "rounds": 1, "win_pct": 0.0},
        {"steamid": 6, "buy_type": "full", "rounds": 2, "win_pct": 0.0},
        {"steamid": 6, "buy_type": "pistol", "rounds": 1, "win_pct": 100.0},
    ]


def test_win_pct_by_matchup() -> None:
    rows = table("eco.win_pct_by_matchup")
    assert {"steamid": 1, "buy_type": "eco", "opponent_buy_type": "full", "rounds": 2,
            "win_pct": 100.0} in rows  # fmt: skip
    assert len(rows) == 4


def test_buy_split() -> None:
    eco = dataset().split(buy="eco")
    assert eco.players()["steamid"].to_list() == [1]
    assert table("eco.buy_type", eco) == [
        {"steamid": 1, "buy_type": "eco", "rounds": 2, "win_pct": 100.0}
    ]


def test_equipment_lost_at_death() -> None:
    out = compute(dataset(), ["eco.equipment_lost_at_death"])
    assert dict(zip(out["steamid"], out["value"], strict=True)) == {1: 700.0, 6: 5250.0}


def test_kills_by_weapon_class() -> None:
    assert table("eco.kills_vs_buy") == [
        {"steamid": 1, "killer_class": "heavy", "victim_class": "rifle", "kills": 1},
        {"steamid": 1, "killer_class": "smg", "victim_class": "awp", "kills": 1},
        {"steamid": 6, "killer_class": "pistol", "victim_class": "pistol", "kills": 1},
    ]
