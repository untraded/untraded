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
         "trade_delay_s": 4.0, "trader": 2, "nearest_teammate_distance": 300.0},
        {"round": 2, "tick": 456, "victim": 6, "killer": 2, "avenges_delay_s": 4.0},
        # round 3: 1 dies alone, 1,500 u from the nearest teammate, untraded
        {"round": 3, "tick": 300, "victim": 1, "killer": 6, "nearest_teammate_distance": 1500.0},
    ],
    {"is_enemy_kill": True, "is_opening": False, "trade_delay_s": None, "trader": None,
     "avenges_delay_s": None, "nearest_teammate_distance": None},
)  # fmt: skip
OPPORTUNITY = pl.DataFrame(
    {"round": [2, 3], "tick": [200, 300], "victim": [1, 1], "killer": [6, 6],
     "teammate": [2, 2], "distance_to_killer": [600.0, 1800.0]}
)  # fmt: skip
CLUTCH = pl.DataFrame({"round": [3, 2], "steamid": [6, 1], "enemies": [1, 2], "won": [True, False]})


def dataset() -> Dataset:
    return Dataset.from_matches(
        [
            {
                "match": pl.DataFrame({"match_id": ["m"], "map": ["de_nuke"]}),
                "round_player": ROUND_PLAYER,
                "death": DEATH,
                "trade_opportunity": OPPORTUNITY,
                "clutch": CLUTCH,
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
    assert values("trade.untraded_deaths") == {1: 1.0, 2: 0.0, 6: 2.0}
    # the 4 s trade is outside the 3 s variant
    assert values("trade.traded_deaths_w3") == {1: 0.0, 2: 0.0, 6: 0.0}
    assert values("trade.traded_deaths", **{"trade.window_s": 3.0}) == {1: 0.0, 2: 0.0, 6: 0.0}


def test_trade_opportunities_follow_the_distance() -> None:
    assert values("trade.kill_opportunities") == {1: 0.0, 2: 1.0, 6: 0.0}
    assert values("trade.kill_conversion_pct") == {1: None, 2: 100.0, 6: None}
    assert values("trade.death_opportunities") == {1: 1.0, 2: 0.0, 6: 0.0}
    assert values("trade.kill_opportunities", **{"trade.opportunity_distance": 2000.0}) == {
        1: 0.0,
        2: 2.0,
        6: 0.0,
    }


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
