# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Duel, trade and clutch metrics (metrics-v1 § 2) on hand-made round models."""

from __future__ import annotations

from typing import Any

import polars as pl
import pytest

from untraded.metrics import Dataset, compute


def frame(rows: list[dict[str, Any]], defaults: dict[str, Any]) -> pl.DataFrame:
    return pl.DataFrame([{**defaults, **row} for row in rows])


# Players 1 and 2 (team A) against 6 (team B), one match, three rounds.
ROUND_PLAYER = frame(
    [
        {"round": 1, "steamid": 1, "opening_kill": True, "team_won": True, "kills": 1},
        {"round": 1, "steamid": 6, "opening_death": True, "deaths": 1, "team": "B", "side": "T"},
        {"round": 2, "steamid": 1, "deaths": 1, "opening_death": True},
        {"round": 2, "steamid": 2, "kills": 1},
        {"round": 2, "steamid": 6, "opening_kill": True, "deaths": 1, "kills": 1, "team": "B",
         "side": "T"},
        {"round": 3, "steamid": 1, "deaths": 1},
        {"round": 3, "steamid": 2},
        {"round": 3, "steamid": 6, "team": "B", "side": "T"},
    ],
    {"side": "CT", "team": "A", "kills": 0, "deaths": 0, "opening_kill": False,
     "opening_death": False, "team_won": False, "survived": False},
)  # fmt: skip
DEATH = frame(
    [
        # round 1: 1 kills 6 (opening)
        {"round": 1, "tick": 100, "victim": 6, "killer": 1, "is_opening": True},
        # round 2: 6 kills 1 (opening), 2 kills 6 four seconds later: a trade
        {"round": 2, "tick": 200, "victim": 1, "killer": 6, "is_opening": True,
         "trade_delay_s": 4.0, "trader": 2, "nearest_teammate_distance": 300.0,
         "last_sight_s": 0.5},
        {"round": 2, "tick": 456, "victim": 6, "killer": 2, "avenges_delay_s": 4.0,
         "last_sight_s": 3.0},
        # round 3: 1 dies alone, 1,500 u from the nearest teammate, untraded
        {"round": 3, "tick": 300, "victim": 1, "killer": 6, "nearest_teammate_distance": 1500.0,
         "last_sight_s": 1.0},
    ],
    {"is_enemy_kill": True, "is_opening": False, "trade_delay_s": None, "trader": None,
     "avenges_delay_s": None, "nearest_teammate_distance": None, "last_sight_s": None},
)  # fmt: skip
# 1 had hurt 6 in round 2 before dying; 6 is killed with a molotov in round 2.
KILL = pl.DataFrame(
    {"tick": [100, 200, 456, 300], "victim": [6, 1, 6, 1],
     "weapon": ["ak47", "ak47", "inferno", "awp"], "victim_flash_duration": [0.0] * 4}
)  # fmt: skip
DAMAGE = pl.DataFrame({"round": [2], "tick": [150], "attacker": [1], "victim": [6]})
# 1 is flashed in round 2 for 1 s (over by the death at 200) and in round 3 until after the death.
BLIND = pl.DataFrame(
    {"round": [2, 3], "tick": [100, 280], "victim": [1, 1], "duration": [1.0, 0.5]}
)
# 2 never spots 6 in round 2 but trades him; in round 3, 2 spots 6 one second after the kill.
OPPORTUNITY = pl.DataFrame(
    {"round": [2, 3], "tick": [200, 300], "victim": [1, 1], "killer": [6, 6],
     "teammate": [2, 2], "distance_to_killer": [600.0, 1800.0], "sight_delay_s": [None, 1.0]}
)  # fmt: skip
CLUTCH = pl.DataFrame({"round": [3, 2], "steamid": [6, 1], "enemies": [1, 2], "won": [True, False]})


def dataset() -> Dataset:
    return Dataset.from_matches(
        [
            {
                "match": pl.DataFrame({"match_id": ["m"], "map": ["de_nuke"], "tickrate": [64.0]}),
                "round_player": ROUND_PLAYER,
                "death": DEATH,
                "trade_opportunity": OPPORTUNITY,
                "clutch": CLUTCH,
                "kill": KILL,
                "damage": DAMAGE,
                "blind": BLIND,
            }
        ]
    )


def values(metric: str, **params: Any) -> dict[int, float | None]:
    out = compute(dataset(), [metric], params=params or None)
    return dict(zip(out["steamid"].to_list(), out["value"].to_list(), strict=True))


def test_openings() -> None:
    assert values("duel.opening_kills") == {1: 1.0, 2: 0.0, 6: 1.0}
    assert values("duel.opening_success_pct") == {1: 50.0, 2: None, 6: 50.0}
    assert values("duel.opening_win_conversion_pct") == {1: 100.0, 2: None, 6: 0.0}


def test_trades_follow_the_window() -> None:
    assert values("trade.traded_deaths") == {1: 1.0, 2: 0.0, 6: 0.0}
    assert values("trade.trade_kills") == {1: 0.0, 2: 1.0, 6: 0.0}
    # 6 is alone on team B: nobody could trade his two deaths
    assert values("trade.untraded_deaths") == {1: 1.0, 2: 0.0, 6: 0.0}
    # the 4 s trade is outside the 3 s variant
    assert values("trade.traded_deaths_w3") == {1: 0.0, 2: 0.0, 6: 0.0}
    assert values("trade.traded_deaths", **{"trade.window_s": 3.0}) == {1: 0.0, 2: 0.0, 6: 0.0}


def test_trade_opportunities_follow_the_distance_and_the_sighting() -> None:
    assert values("trade.kill_opportunities") == {1: 0.0, 2: 1.0, 6: 0.0}
    assert values("trade.kill_conversion_pct") == {1: None, 2: 100.0, 6: None}
    assert values("trade.death_opportunities") == {1: 1.0, 2: 0.0, 6: 0.0}
    assert values("trade.kill_opportunities", **{"trade.opportunity_distance": 2000.0}) == {
        1: 0.0,
        2: 2.0,
        6: 0.0,
    }
    # within 0.5 s, 2 neither saw 6 nor traded him
    wide_but_quick = {"trade.opportunity_distance": 2000.0, "trade.window_s": 0.5}
    assert values("trade.kill_opportunities", **wide_but_quick) == {1: 0.0, 2: 0.0, 6: 0.0}


def test_duels_lost_need_a_sighting_a_gun_and_clear_eyes() -> None:
    # 1 lost the round 2 duel, having hurt 6 (the flash before had worn off); in round 3, 1 was
    # still blind. 6 never saw 1 in round 1 and burnt in round 2.
    assert values("duel.duels_lost") == {1: 1.0, 2: 0.0, 6: 0.0}
    assert values("duel.lost_without_damage_pct") == {1: 0.0, 2: None, 6: None}
    # with a 0.25 s sighting, round 2's duel (seen 0.5 s before) is a shot in the back
    assert values("duel.duels_lost", **{"duel.sight_s": 0.25}) == {1: 0.0, 2: 0.0, 6: 0.0}


def test_conversion_counts_the_opportunities_traded() -> None:
    # 2 traded round 2's death (an opportunity) and saw round 3's killer without trading
    wide = {"trade.opportunity_distance": 2000.0}
    assert values("trade.kill_conversion_pct", **wide) == {1: None, 2: 50.0, 6: None}


def test_isolation_counts_untraded_deaths_far_from_teammates() -> None:
    assert values("duel.isolated_deaths") == {1: 1.0, 2: 0.0, 6: 0.0}
    assert values("duel.isolated_death_pct") == {1: 50.0, 2: None, 6: 0.0}
    assert values("duel.nearest_teammate_at_death") == {1: 900.0, 2: None, 6: None}


def test_clutches() -> None:
    assert values("clutch.attempts_1v2") == {1: 1.0, 2: 0.0, 6: 0.0}
    assert values("clutch.wins_1v1") == {1: 0.0, 2: 0.0, 6: 1.0}
    assert values("clutch.win_pct") == {1: 0.0, 2: None, 6: 100.0}


def test_side_split_drops_the_other_side_events() -> None:
    ct = compute(dataset().split(side="CT"), ["trade.untraded_deaths"])
    assert dict(zip(ct["steamid"].to_list(), ct["value"].to_list(), strict=True)) == {
        1: 1.0,
        2: 0.0,
    }
    assert pytest.approx(1.0) == ct["value"].sum()
