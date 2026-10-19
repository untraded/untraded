# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Utility metrics (metrics-v1 § 4) on hand-made tables."""

from __future__ import annotations

from typing import Any

import polars as pl

from untraded.metrics import Dataset, compute


def frame(rows: list[dict[str, Any]], defaults: dict[str, Any]) -> pl.DataFrame:
    return pl.DataFrame([{**defaults, **row} for row in rows])


# Players 1 and 2 (team A) against 6 and 7 (team B); sides swap in round 2. Tickrate 64.
ROUND_PLAYER = pl.DataFrame(
    {
        "round": [1, 1, 1, 1, 2, 2, 2, 2],
        "steamid": [1, 2, 6, 7] * 2,
        "team": ["A", "A", "B", "B"] * 2,
        "side": ["CT", "CT", "T", "T", "T", "T", "CT", "CT"],
    }
)
GRENADE = frame(
    [
        {"round": 1, "thrower": 1, "type": "flash"},
        {"round": 1, "thrower": 1, "type": "he"},
        {"round": 1, "thrower": 1, "type": "molotov"},
        {"round": 1, "thrower": 2, "type": "incendiary"},
        {"round": 1, "thrower": 2, "type": "smoke"},
        {"round": 2, "thrower": 1, "type": "flash"},
        {"round": 2, "thrower": 1, "type": "decoy"},
    ],
    {},
)
BLIND = frame(
    [
        {"round": 1, "tick": 100, "victim": 6, "duration": 2.0},
        {"round": 1, "tick": 100, "victim": 7, "duration": 0.5},  # under the 1 s minimum
        {"round": 1, "tick": 100, "victim": 2, "duration": 1.5, "is_teammate": True},
        {"round": 1, "tick": 100, "victim": 1, "duration": 1.2, "is_self": True},
        {"round": 1, "tick": 150, "victim": 7, "duration": 3.0},  # 7 died at 120: ignored
        {"round": 2, "tick": 300, "victim": 6, "duration": 1.0},  # exactly the minimum
    ],
    {"flasher": 1, "is_teammate": False, "is_self": False},
)
DEATH = frame(
    [
        # 6 is still blind (until 100 + 2 s * 64 = 228) when 2 kills them: decisive for 1
        {"round": 1, "tick": 160, "victim": 6, "killer": 2},
        # 7 still blind (until 132), killed by 1: decisive, even under the 1 s minimum
        {"round": 1, "tick": 120, "victim": 7, "killer": 1},
        # the flash on 6 ended at 364: not decisive
        {"round": 2, "tick": 400, "victim": 6, "killer": 2},
        {"round": 2, "tick": 500, "victim": 1, "killer": 6, "killer_team": "B"},
    ],
    {"killer_team": "A", "is_enemy_kill": True},
)
KILL = pl.DataFrame(
    {
        "tick": [160, 120, 400, 500],
        "victim": [6, 7, 6, 1],
        "victim_inventory": [
            ["knife", "Molotov"],
            [],
            ["knife", "High Explosive Grenade"],
            ["knife", "Flashbang", "Flashbang", "Smoke Grenade"],
        ],
    },
    schema_overrides={"victim_inventory": pl.List(pl.String)},
)
DAMAGE = frame(
    [
        {"victim": 6, "weapon": "hegrenade", "damage": 40, "grenade_id": 2},
        {"victim": 2, "weapon": "hegrenade", "damage": 10, "grenade_id": 2,
         "is_team_damage": True},
        {"victim": 1, "weapon": "hegrenade", "damage": 5, "grenade_id": 2},  # self-damage
        {"victim": 7, "weapon": "inferno", "damage": 20, "grenade_id": 3},
        {"victim": 7, "weapon": "inferno", "damage": 15},  # fire not linked to a grenade of 1
        {"victim": 6, "weapon": "ak47", "damage": 27},
    ],
    {"round": 1, "attacker": 1, "is_team_damage": False, "grenade_id": None},
)  # fmt: skip


def dataset() -> Dataset:
    return Dataset.from_matches(
        [
            {
                "match": pl.DataFrame({"match_id": ["m"], "map": ["de_nuke"], "tickrate": [64.0]}),
                "round_player": ROUND_PLAYER,
                "grenade": GRENADE,
                "blind": BLIND,
                "death": DEATH,
                "kill": KILL,
                "damage": DAMAGE,
            }
        ]
    )


def values(metric: str, ds: Dataset | None = None, /, **params: Any) -> dict[int, float | None]:
    out = compute(ds or dataset(), [metric], params=params or None)
    return dict(zip(out["steamid"].to_list(), out["value"].to_list(), strict=True))


def test_grenades_thrown() -> None:
    assert values("util.thrown_flash") == {1: 2.0, 2: 0.0, 6: 0.0, 7: 0.0}
    assert values("util.thrown_molotov") == {1: 1.0, 2: 1.0, 6: 0.0, 7: 0.0}
    assert values("util.thrown_decoy")[1] == 1.0
    assert values("util.thrown_per_round") == {1: 2.5, 2: 1.0, 6: 0.0, 7: 0.0}


def test_flashes_on_enemies_use_the_minimum_and_skip_dead_players() -> None:
    assert values("util.enemies_flashed") == {1: 2.0, 2: 0.0, 6: 0.0, 7: 0.0}
    assert values("util.enemies_flashed", **{"flash.min_blind_s": 0.4})[1] == 3.0
    assert values("util.enemy_blind_time")[1] == 3.5
    assert values("util.blind_per_flash") == {1: 1.75, 2: None, 6: None, 7: None}


def test_team_and_self_flashes() -> None:
    assert values("util.teammates_flashed")[1] == 1.0
    assert values("util.team_blind_time")[1] == 1.5
    assert values("util.self_flashed")[1] == 1.0
    assert values("util.self_flashed", **{"flash.min_blind_s": 1.5})[1] == 0.0


def test_decisive_flashes() -> None:
    assert values("util.flash_to_kill") == {1: 2.0, 2: 0.0, 6: 0.0, 7: 0.0}


def test_grenade_damage_excludes_self_damage_and_unlinked_fire() -> None:
    assert values("util.he_damage")[1] == 40.0
    assert values("util.he_team_damage")[1] == 10.0
    assert values("util.fire_damage")[1] == 20.0


def test_wasted_utility_is_averaged_over_deaths() -> None:
    assert values("util.unused_value_at_death") == {1: 700.0, 2: None, 6: 350.0, 7: 0.0}


def test_side_split() -> None:
    ct = dataset().split(side="CT")
    assert values("util.enemies_flashed", ct)[1] == 1.0
    assert values("util.thrown_flash", ct)[1] == 1.0
    assert values("util.unused_value_at_death", ct) == {1: None, 2: None, 6: 300.0, 7: None}
