# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The round model (E4) on hand-made rounds."""

from __future__ import annotations

from typing import Any

import polars as pl

from untraded.derive.buys import BuyThresholds, build_team_rounds
from untraded.derive.clutches import build_clutches
from untraded.derive.deaths import build_deaths
from untraded.derive.players import build_round_players

# Team A: players 1-3 on CT. Team B: players 6-8 on T. Tickrate 64.
TEAMS = pl.DataFrame({"steamid": [1, 2, 3, 6, 7, 8], "team": ["A"] * 3 + ["B"] * 3})
ROUNDS = pl.DataFrame(
    {
        "round": [1],
        "freeze_end_tick": [100],
        "end_tick": [5000],
        "ct_team": ["A"],
        "t_team": ["B"],
        "winner_team": ["A"],
    }
)


def kills(*rows: tuple[int, int | None, int], bots: tuple[int, ...] = ()) -> pl.DataFrame:
    """Rows of (tick, attacker, victim); positions: player p stands at (p * 100, 0, 0). Kills
    at the ticks in `bots` are kills of a bot (`victim_bot`)."""
    return pl.DataFrame(
        {
            "tick": [r[0] for r in rows],
            "round": [1] * len(rows),
            "attacker": [r[1] for r in rows],
            "victim": [r[2] for r in rows],
            "attacker_x": [float((r[1] or 0) * 100) for r in rows],
            "attacker_y": [0.0] * len(rows),
            "attacker_z": [0.0] * len(rows),
            "victim_x": [float(r[2] * 100) for r in rows],
            "victim_y": [0.0] * len(rows),
            "victim_z": [0.0] * len(rows),
            "victim_bot": [r[0] in bots for r in rows],
        },
        schema_overrides={"attacker": pl.Int64},
    )


def states(ticks: list[int], dead: dict[int, int]) -> pl.DataFrame:
    """Every player at every tick, at (p * 100, 0, 0); `dead` maps player -> death tick."""
    rows: list[dict[str, Any]] = []
    for tick in ticks:
        for player in TEAMS["steamid"].to_list():
            rows.append(
                {
                    "tick": tick,
                    "round": 1,
                    "steamid": player,
                    "is_alive": tick < dead.get(player, 10**9),
                    "x": float(player * 100),
                    "y": 0.0,
                    "z": 0.0,
                    "side": "CT" if player <= 3 else "T",
                }
            )
    return pl.DataFrame(rows)


def test_a_kill_of_a_taken_over_bot_counts_for_the_killer_but_is_nobody_s_death() -> None:
    # 1 died at 200 and took over a bot, which 6 kills at 300
    found, _ = build_deaths(
        kills((200, 6, 1), (300, 6, 1), bots=(300,)),
        TEAMS,
        ROUNDS,
        states([100, 200, 300], {1: 200}),
        64,
    )
    bot = found.filter(pl.col("tick") == 300)
    assert bot.select("victim", "victim_team", "is_enemy_kill").rows() == [(None, "A", True)]


def test_a_trade_on_the_same_tick_counts_but_not_a_mutual_kill() -> None:
    # 6 kills 1 and 2 kills 6 on the same tick: traded after 0 s; 3 and 7 kill each other
    found, _ = build_deaths(
        kills((200, 6, 1), (200, 2, 6), (300, 3, 7), (300, 7, 3)),
        TEAMS,
        ROUNDS,
        states([100, 200, 300], {1: 200, 6: 200, 3: 300, 7: 300}),
        64,
    )
    traded = dict(zip(found["victim"].to_list(), found["trade_delay_s"].to_list(), strict=True))
    assert traded == {1: 0.0, 6: None, 7: None, 3: None}


def test_the_victim_s_own_fire_killing_the_killer_later_trades_the_death() -> None:
    # 6 kills 1 at 200; 1's molotov kills 6 at 300 (1.6 s later)
    found, _ = build_deaths(
        kills((200, 6, 1), (300, 1, 6)), TEAMS, ROUNDS, states([100, 200, 300], {1: 200}), 64
    )
    assert found.filter(pl.col("victim") == 1)["trade_delay_s"].to_list() == [1.5625]


def test_opening_trade_and_avenge() -> None:
    # 6 kills 1 (opening) at 200; 2 kills 6 at 400 (3.1 s later): 1's death is traded by 2
    found, _ = build_deaths(
        kills((200, 6, 1), (400, 2, 6)),
        TEAMS,
        ROUNDS,
        states([100, 200, 400], {1: 200, 6: 400}),
        64,
    )
    first, second = found.rows(named=True)
    assert first["is_opening"]
    assert not second["is_opening"]
    assert first["trader"] == 2
    assert first["trade_delay_s"] == (400 - 200) / 64
    assert second["avenges_delay_s"] == (400 - 200) / 64
    assert second["trade_delay_s"] is None


def test_kills_before_freeze_end_and_team_kills_are_not_openings() -> None:
    found, _ = build_deaths(
        kills((50, 6, 1), (150, 2, 3), (300, 7, 2)), TEAMS, ROUNDS, states([300], {}), 64
    )
    assert found["is_opening"].to_list() == [False, False, True]
    assert found["is_enemy_kill"].to_list() == [True, False, True]


def test_spacing_and_trade_opportunities_use_living_teammates() -> None:
    # 6 kills 1 at 200; teammates 2 (alive, 100 u from 1) and 3 (dead before)
    found, opportunities = build_deaths(
        kills((150, 7, 3), (200, 6, 1)), TEAMS, ROUNDS, states([150, 200], {3: 150, 1: 200}), 64
    )
    assert found.filter(pl.col("victim") == 1)["nearest_teammate_distance"].to_list() == [100.0]
    at_200 = opportunities.filter(pl.col("tick") == 200)
    # teammate 2 stands at 200 u, killer 6 at 600 u: 400 u away
    assert at_200.select("teammate", "distance_to_killer").rows() == [(2, 400.0)]


def test_clutch_starts_when_one_player_is_left_against_enemies() -> None:
    died = pl.DataFrame(
        {"tick": [200, 300, 300], "round": [1, 1, 1], "victim": [2, 3, 6]},
    )
    found = build_clutches(died, ROUNDS, states([100], {}), TEAMS)
    # at 300, team A is down to player 1, facing 7 and 8
    assert found.select("steamid", "enemies", "start_tick", "won").rows() == [(1, 2, 300, True)]


def test_both_last_players_are_in_a_1v1() -> None:
    # two players of each team die on the same tick: 1 and 8 are both left alone, in a 1v1
    died = pl.DataFrame({"tick": [200] * 4, "round": [1] * 4, "victim": [2, 3, 6, 7]})
    found = build_clutches(died, ROUNDS, states([100], {}), TEAMS)
    assert sorted(found.select("steamid", "enemies").rows()) == [(1, 1), (8, 1)]


def test_a_team_down_to_one_first_clutches_against_everyone_left() -> None:
    died = pl.DataFrame({"tick": [200, 200, 300, 300], "round": [1] * 4, "victim": [2, 3, 6, 7]})
    found = build_clutches(died, ROUNDS, states([100], {}), TEAMS)
    assert sorted(found.select("steamid", "enemies").rows()) == [(1, 3), (8, 1)]


def test_buy_types() -> None:
    rounds = pl.DataFrame(
        {
            "round": [1, 2, 3, 13],
            "ct_team": ["A"] * 3 + ["B"],
            "t_team": ["B"] * 3 + ["A"],
            "winner_team": ["A", "A", "B", "A"],
        }
    )
    economy = pl.DataFrame(
        {
            "round": [1, 1, 2, 2, 3, 3, 13, 13],
            "steamid": [1, 6, 1, 6, 1, 6, 1, 6],
            "equip_value": [800, 800, 4600, 2500, 900, 4100, 700, 700],
        }
    )
    found = build_team_rounds(economy, rounds, TEAMS, BuyThresholds())
    types = dict(
        zip(
            zip(found["round"].to_list(), found["team"].to_list(), strict=True),
            found["buy_type"].to_list(),
            strict=True,
        )
    )
    assert types == {
        (1, "A"): "pistol",
        (1, "B"): "pistol",
        (2, "A"): "full",  # CT at 4,600
        (2, "B"): "force",  # lost round 1, neither eco nor full
        (3, "A"): "eco",
        (3, "B"): "full",  # T at 4,100
        (13, "A"): "pistol",
        (13, "B"): "pistol",
    }


def test_a_death_after_the_round_end_is_not_a_survival() -> None:
    # 6 kills 1 at 5200, after the round end (5000): 1 was alive at the end but dropped the weapons
    found, _ = build_deaths(
        kills((5200, 6, 1)), TEAMS, ROUNDS, states([100, 5000, 5200], {1: 5200}), 64
    )
    rows = build_round_players(
        economy=pl.DataFrame({"round": [1, 1], "steamid": [1, 2], "side": ["CT", "CT"]}),
        teams=TEAMS,
        rounds=ROUNDS,
        kills=kills((5200, 6, 1)).with_columns(
            pl.lit(None, pl.Int64).alias("assister"), pl.lit(False).alias("flash_assist")
        ),
        deaths=found,
        damage=pl.DataFrame(
            schema={"round": pl.Int64, "attacker": pl.Int64, "victim": pl.Int64, "damage": pl.Int64}
        ),
        states=states([100, 5000, 5200], {1: 5200}).with_columns(
            pl.lit("BombsiteA").alias("place")
        ),
        tickrate=64,
    )
    assert dict(zip(rows["steamid"].to_list(), rows["survived"].to_list(), strict=True)) == {
        1: False,
        2: True,
    }
