# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Positioning table metrics (metrics-v1 § 3) on a hand-made round model."""

from __future__ import annotations

import math

import polars as pl
import pytest

from untraded.metrics import Dataset, compute, compute_table
from untraded.metrics.positioning import _normalized_entropy

# Player 1 (CT) and player 6 (T), one match on Nuke, 8 rounds.
ROUND_PLAYER = pl.DataFrame(
    {
        "round": list(range(1, 9)) * 2,
        "steamid": [1] * 8 + [6] * 8,
        "side": ["CT"] * 8 + ["T"] * 8,
        "team": ["A"] * 8 + ["B"] * 8,
        "setup_place": ["Ramp"] * 6 + ["Outside", None] + ["Outside"] * 8,
    }
)
# 1 dies 4 times in Ramp (one traded) and once in Outside; 6 makes those kills from Outside
DEATH = pl.DataFrame(
    {
        "round": [1, 2, 3, 4, 5],
        "tick": [100, 200, 300, 400, 500],
        "victim": [1] * 5,
        "killer": [6] * 5,
        "is_enemy_kill": [True] * 5,
        "trade_delay_s": [None, 2.0, None, None, None],
    }
)
KILL = DEATH.select("tick", "victim").with_columns(
    pl.Series("victim_place", ["Ramp", "Ramp", "Ramp", "Ramp", "Outside"]),
    pl.lit("Outside").alias("attacker_place"),
    *(pl.lit(1.0).alias(f"{who}_{axis}") for who in ("victim", "attacker") for axis in "xyz"),
)


def dataset() -> Dataset:
    return Dataset.from_matches(
        [
            {
                "match": pl.DataFrame({"match_id": ["m"], "map": ["de_nuke"]}),
                "round_player": ROUND_PLAYER,
                "death": DEATH,
                "kill": KILL,
            }
        ]
    )


def test_death_zones_with_traded_share() -> None:
    zones = compute_table(dataset(), "pos.death_zones")
    assert zones.select("zone", "deaths", "traded_pct").rows() == [
        ("Ramp", 4, 25.0),
        ("Outside", 1, 0.0),
    ]


def test_kill_zones_belong_to_the_killer() -> None:
    zones = compute_table(dataset(), "pos.kill_zones")
    assert zones.select("steamid", "zone", "kills").rows() == [(6, "Outside", 5)]


def test_setup_zones_and_diversity() -> None:
    setups = compute_table(dataset(), "pos.setup_zone_t20").filter(pl.col("steamid") == 1)
    assert setups.select("zone", "rounds").rows() == [("Ramp", 6), ("Outside", 1)]
    diversity = dict(
        compute_table(dataset(), "pos.setup_diversity").select("steamid", "diversity").rows()
    )
    assert diversity[6] == 0.0  # always the same zone
    assert diversity[1] == pytest.approx(_normalized_entropy([6, 1]))


def test_normalized_entropy_bounds() -> None:
    assert _normalized_entropy([5]) == 0.0
    assert _normalized_entropy([3, 3, 3]) == pytest.approx(1.0)
    assert 0 < _normalized_entropy([9, 1]) < 1
    assert math.isclose(_normalized_entropy([1, 1]), 1.0)


def test_recurring_death_spot_needs_share_and_rounds() -> None:
    spots = compute_table(dataset(), "pos.recurring_death_spot")
    # 3 untraded deaths of 4 in Ramp (75 %) and 1 in Outside (25 %), over 8 rounds
    assert spots.select("zone", "untraded_deaths", "rounds").rows() == [
        ("Ramp", 3, 8),
        ("Outside", 1, 8),
    ]
    stricter = compute_table(
        dataset(), "pos.recurring_death_spot", params={"pos.recurring_death_share": 0.5}
    )
    assert stricter["zone"].to_list() == ["Ramp"]
    assert compute_table(
        dataset(), "pos.recurring_death_spot", params={"pos.recurring_min_rounds": 9}
    ).is_empty()


def test_heatmap_points_and_kinds_do_not_mix() -> None:
    points = compute_table(dataset(), "pos.heatmap_points")
    assert points.group_by("role").len().sort("role").rows() == [("death", 5), ("kill", 5)]
    with pytest.raises(ValueError, match="table metric"):
        compute(dataset(), ["pos.death_zones"])
    with pytest.raises(ValueError, match="value metric"):
        compute_table(dataset(), "base.kills")
