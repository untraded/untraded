# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Capped damage (metrics-v1 § 0) from the chain of hits on each victim."""

from __future__ import annotations

import polars as pl

from untraded.parsing.combat import capped_damage


def hurts(*rows: tuple[int, int, int, int, int, int]) -> pl.DataFrame:
    """Rows of (tick, round, attacker, victim, dmg_health, health_after); sides from steamids."""
    return pl.DataFrame(
        {
            "order": list(range(len(rows))),
            "tick": [r[0] for r in rows],
            "round": [r[1] for r in rows],
            "attacker": [r[2] for r in rows],
            "victim": [r[3] for r in rows],
            "dmg_health": [r[4] for r in rows],
            "health_after": [r[5] for r in rows],
            # players 1-5 on CT, 6-10 on T
            "attacker_side": ["CT" if r[2] <= 5 else "T" for r in rows],
            "victim_side": ["CT" if r[3] <= 5 else "T" for r in rows],
        }
    )


def test_overkill_is_capped_by_the_health_left() -> None:
    out = capped_damage(hurts((10, 1, 1, 6, 30, 70), (20, 1, 2, 6, 120, 0)))
    assert out["damage"].to_list() == [30, 70]


def test_rounded_down_damage_is_never_exceeded() -> None:
    # dmg_health is rounded down: health drops by 15 for a reported 14
    out = capped_damage(hurts((10, 1, 1, 6, 14, 85), (20, 1, 1, 6, 14, 70)))
    assert out["damage"].to_list() == [14, 14]


def test_hits_on_the_same_tick_chain_in_event_order() -> None:
    out = capped_damage(hurts((10, 1, 1, 6, 60, 40), (10, 1, 2, 6, 60, 0)))
    assert out["damage"].to_list() == [60, 40]


def test_health_is_full_again_in_the_next_round() -> None:
    out = capped_damage(hurts((10, 1, 1, 6, 90, 10), (500, 2, 1, 6, 120, 0)))
    assert out["damage"].to_list() == [90, 100]


def test_team_damage_and_self_damage() -> None:
    out = capped_damage(hurts((10, 1, 1, 2, 20, 80), (20, 1, 3, 3, 5, 95), (30, 1, 1, 7, 20, 80)))
    assert out["is_team_damage"].to_list() == [True, False, False]
