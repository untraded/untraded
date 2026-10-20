# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Calibration of the 🎯 thresholds (E9) on hand-made round models."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import polars as pl
import pytest

from untraded import calibration as c
from untraded.metrics import Dataset


def dataset(**tables: pl.DataFrame) -> Dataset:
    defaults: dict[str, Any] = {
        "match": pl.DataFrame({"match_id": ["m"], "map": ["de_nuke"]}),
        "round_player": pl.DataFrame({"round": [1], "steamid": [1], "side": ["CT"], "team": ["A"]}),
    }
    return Dataset.from_matches([{**defaults, **tables}])


def test_buy_profile_skips_pistol_rounds_and_finds_the_valley() -> None:
    team_round = pl.DataFrame(
        {
            "round": [1, 2, 3, 4, 5, 6],
            "side": ["CT"] * 6,
            "team": ["A"] * 6,
            "buy_type": ["pistol", "eco", "eco", "full", "full", "full"],
            "equip_value": [800.0, 600.0, 700.0, 4600.0, 4700.0, 2100.0],
            "won": [True, False, False, True, True, False],
        }
    )
    profile = c.buy_profile(dataset(team_round=team_round))
    ct = profile.filter(pl.col("side") == "CT")
    assert ct["rounds"].sum() == 5  # the pistol round is left out
    assert ct.filter(pl.col("bucket") == 500).row(0, named=True)["win_pct"] == 0.0
    # 600 and 700 share a bucket, 2100 is alone: the valley between 1000 and 3000 is there
    assert c.buy_valleys(profile, 1000, 3000) == {"CT": 2125.0, "T": None}


def deaths(rows: Sequence[tuple[float, float | None]]) -> pl.DataFrame:
    """(distance to the nearest teammate, trade delay) per death."""
    return pl.DataFrame(
        {
            "round": [1] * len(rows),
            "tick": list(range(len(rows))),
            "victim": [1] * len(rows),
            "trader": [2] * len(rows),
            "is_enemy_kill": [True] * len(rows),
            "nearest_teammate_distance": [r[0] for r in rows],
            "trade_delay_s": [r[1] for r in rows],
        }
    )


def test_isolation_radius_is_where_trades_fall_below_half_of_close_range() -> None:
    close = [(100.0, 2.0)] * 10 + [(100.0, None)] * 10  # 50 % traded under 500 u
    mid = [(600.0, 2.0)] * 6 + [(600.0, None)] * 4  # 60 %
    far = [(1100.0, 2.0)] * 2 + [(1100.0, None)] * 8  # 20 %: below half of 50 %
    profile = c.isolation_profile(dataset(death=deaths(close + mid + far)))
    assert profile["deaths"].to_list() == [20, 10, 10]
    assert c.isolation_radius(profile, min_deaths=5) == 1000.0
    assert c.isolation_radius(profile, min_deaths=50) is None


def test_trade_distances_are_those_of_the_actual_trader() -> None:
    death = deaths([(100.0, 2.0), (100.0, 9.0)])
    opportunity = pl.DataFrame(
        {
            "round": [1, 1, 1],
            "tick": [0, 0, 1],
            "victim": [1, 1, 1],
            "teammate": [2, 3, 2],
            "distance_to_killer": [700.0, 300.0, 400.0],
        }
    )
    distances = c.trade_distances(dataset(death=death, trade_opportunity=opportunity))
    # the second death is traded too late; on the first, the trader is player 2, not 3
    assert distances.to_list() == [700.0]


def test_a_spot_found_in_both_halves_is_replicated() -> None:
    # player 1 on de_nuke CT, 8 rounds; untraded deaths in Ramp in rounds 1, 2, 3, 4 (both
    # halves) and in Outside in rounds 5 and 7 (first half only)
    played = pl.DataFrame(
        {"round": list(range(1, 9)), "steamid": [1] * 8, "side": ["CT"] * 8, "team": ["A"] * 8}
    )
    rounds = [1, 2, 3, 4, 5, 7]
    death = pl.DataFrame(
        {
            "round": rounds,
            "tick": rounds,
            "victim": [1] * 6,
            "is_enemy_kill": [True] * 6,
            "trade_delay_s": [None] * 6,
        }
    )
    kill = pl.DataFrame(
        {
            "tick": rounds,
            "victim": [1] * 6,
            "victim_place": ["Ramp"] * 4 + ["Outside"] * 2,
        }
    )
    ds = dataset(round_player=played, death=death, kill=kill)
    result = c.recurring_replication(ds, shares=[0.25], min_rounds=[4])
    row = result.row(0, named=True)
    # first half (rounds 1, 3, 5, 7): Ramp 2 of 4, Outside 2 of 4; second half: Ramp 2 of 2
    assert (row["spots"], row["replicated"]) == (2, 1)
    assert row["precision_pct"] == pytest.approx(50.0)
    assert c.recurring_replication(ds, shares=[0.25], min_rounds=[5])["spots"].to_list() == [0]
