# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Team metrics (metrics-v1 § 6b) on hand-made tables."""

from __future__ import annotations

from typing import Any

import polars as pl
import pytest

from untraded.metrics import REGISTRY, Dataset, compute, compute_table, compute_team

# Team A (players 1 and 2) against B (6 and 7). A is CT in rounds 1 and 2, T in 3 to 5.
# Round 4 has no known winner (cut by the end of the demo): it never counts.
ROUND = pl.DataFrame(
    {
        "round": [1, 2, 3, 4, 5],
        "winner_team": ["B", "A", "B", None, "A"],
        "ct_team": ["A", "A", "B", "B", "B"],
        "t_team": ["B", "B", "A", "A", "A"],
        # Round 2: the bomb is planted after the last T died (the round's end): no plant.
        "bomb_planted_tick": [500, 1200, 800, 150, 100],
        "bomb_site": ["A", "B", "B", "A", None],  # round 5: a plant on no named site
        "end_tick": [900, 1100, 1000, 400, 300],
        "bomb_defused_tick": [None, None, 950, None, None],
    }
)
ROUND_PLAYER = pl.DataFrame(
    {
        "round": [r for r in range(1, 6) for _ in range(4)],
        "steamid": [1, 2, 6, 7] * 5,
        "team": ["A", "A", "B", "B"] * 5,
        "side": ["CT", "CT", "T", "T"] * 2 + ["T", "T", "CT", "CT"] * 3,
    }
)
DEATH = pl.DataFrame(
    {
        "round": [1, 1, 1, 3, 4, 5],
        "tick": [300, 350, 400, 800, 100, 50],
        # 99 is a bot: present in no round, its death is nobody's.
        "victim": [1, 99, 6, 6, 2, 7],
        "trade_delay_s": [2.0, None, None, 6.0, 1.0, 0.5],
        # Round 5: a bot of the team trades 7's death, which links no player.
        "trader": [2, None, None, 7, 1, 99],
    },
    schema_overrides={"victim": pl.UInt64, "trader": pl.UInt64},
)
TEAM_ROUND = pl.DataFrame(
    {
        "round": [r for r in range(1, 6) for _ in range(2)],
        "team": ["A", "B"] * 5,
        "buy_type": [
            *("pistol", "pistol", "eco", "full", "full", "force"),
            *("full", "full", "force", "full"),
        ],
    }
)


def dataset() -> Dataset:
    return Dataset.from_matches(
        [
            {
                "match": pl.DataFrame({"match_id": ["m"], "map": ["de_nuke"]}),
                "round": ROUND,
                "round_player": ROUND_PLAYER.with_columns(pl.col("steamid").cast(pl.UInt64)),
                "death": DEATH,
                "team_round": TEAM_ROUND,
            }
        ]
    )


def rows(metric: str, **params: Any) -> list[tuple[str, str, str, int, int]]:
    out = compute_team(dataset(), [metric], params=params or None)
    assert set(out["match_id"]) == {"m"}
    assert (out["hits"] <= out["cases"]).all()
    return [
        (r["team"], r["key"], r["sub_key"], r["cases"], r["hits"])
        for r in out.iter_rows(named=True)
    ]


def test_t_rounds_by_site_of_the_plant() -> None:
    assert rows("team.site_t") == [
        ("A", "B", "", 1, 0),
        ("A", "unknown", "", 1, 1),
        ("B", "A", "", 1, 1),
        ("B", "none", "", 1, 0),
    ]


def test_post_plants_by_site_and_players_alive_at_the_plant() -> None:
    # Round 1: 1 and 6 died before the plant (1v1). Round 3: 6 died on the plant's tick, which
    # counts as before it. Round 5: 7 died before it. The bot's death changes nobody's count.
    assert rows("team.post_plant") == [
        ("A", "B", "2v1", 1, 0),
        ("A", "unknown", "2v1", 1, 1),
        ("B", "A", "1v1", 1, 1),
    ]


def test_retakes_are_the_ct_side_of_the_same_rounds() -> None:
    assert rows("team.retake") == [
        ("A", "A", "1v1", 1, 0),
        ("B", "B", "1v2", 1, 1),
        ("B", "unknown", "1v2", 1, 0),
    ]


def test_rounds_by_buy_type_against_the_enemys() -> None:
    assert rows("team.buy") == [
        ("A", "eco", "full", 1, 1),
        ("A", "force", "full", 1, 1),
        ("A", "full", "force", 1, 0),
        ("A", "pistol", "pistol", 1, 0),
        ("B", "force", "full", 1, 1),
        ("B", "full", "eco", 1, 0),
        ("B", "full", "force", 1, 0),
        ("B", "pistol", "pistol", 1, 1),
    ]


def test_trade_network_counts_who_traded_whose_death() -> None:
    assert rows("team.trades") == [
        ("A", "1", "", 1, 1),
        ("A", "1", "2", 1, 1),
        ("B", "6", "", 2, 0),  # 6.0 s is outside the 5 s window
        ("B", "7", "", 1, 1),  # traded by a bot: in the total, linked to nobody
    ]
    wider = rows("team.trades", **{"trade.window_s": 7.0})
    assert ("B", "6", "", 2, 1) in wider
    assert ("B", "6", "7", 2, 1) in wider


def test_team_metrics_are_counts_apart_from_the_player_metrics() -> None:
    team = [m for m in REGISTRY.values() if m.kind == "team"]
    assert sorted(m.id for m in team) == [
        "team.buy",
        "team.post_plant",
        "team.retake",
        "team.site_t",
        "team.trades",
    ]
    assert all(m.unit == "table" and m.better == "higher" and not m.cases for m in team)
    # The player metrics never include them, and each kind has its own function.
    assert not compute(dataset(), []).height
    with pytest.raises(ValueError, match="not a team metric"):
        compute_team(dataset(), ["base.kills"])
    with pytest.raises(ValueError, match="team metric: use compute_team"):
        compute_table(dataset(), "team.buy")
    out = compute_team(dataset())
    assert set(out["metric"]) == {m.id for m in team}
    assert out.filter(pl.col("metric") == "team.trades")["params"].unique().to_list() == [
        '{"trade.window_s": 5.0}'
    ]
