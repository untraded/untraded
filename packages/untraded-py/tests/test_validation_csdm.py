# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Matching our stats with a CS Demo Manager export (E8)."""

from __future__ import annotations

from typing import Any

import polars as pl

from untraded.validation import csdm


def player(steamid: int, **fields: float) -> dict[str, Any]:
    stats = {f.csdm: 0.0 for f in csdm.FIELDS}
    return {"steamId": steamid, "name": f"p{steamid}", **stats, **fields}


EXPORT = {
    "players": {
        "1": player(1, killCount=20, averageDamagePerRound=80.0, oneVsOneCount=7),
        "2": player(2, killCount=10, averageDamagePerRound=50.0),
    },
    "clutches": [
        {"clutcherSteamId": 1, "opponentCount": 2, "hasWon": True},
        {"clutcherSteamId": 1, "opponentCount": 2, "hasWon": False},
    ],
}


def ours(**changes: dict[int, float]) -> pl.DataFrame:
    values = csdm.csdm_values(EXPORT).drop("name")
    for column, by_player in changes.items():
        values = values.with_columns(
            pl.col("steamid").replace_strict(by_player, default=pl.col(column)).alias(column)
        )
    return values


def gaps(comparison: pl.DataFrame) -> list[tuple[int, str]]:
    rows = comparison.filter(pl.col("gap")).select("steamid", "field").rows()
    return sorted((int(steamid), str(field)) for steamid, field in rows)


def test_clutches_come_from_the_clutch_list_not_the_player_counters() -> None:
    values = csdm.csdm_values(EXPORT).row(0, named=True)
    assert values["clutch_attempts_1v2"] == 2.0
    assert values["clutch_wins_1v2"] == 1.0
    assert values["clutch_attempts_1v1"] == 0.0


def test_identical_stats_have_no_gap() -> None:
    assert gaps(csdm.compare(ours(), csdm.csdm_values(EXPORT))) == []


def test_counts_must_be_equal_and_ratios_within_one_percent() -> None:
    changed = ours(kills={1: 21.0}, adr={1: 80.7, 2: 50.6})
    # 80.7 is within 1 % of 80; 50.6 is not within 1 % of 50
    assert gaps(csdm.compare(changed, csdm.csdm_values(EXPORT))) == [(1, "kills"), (2, "adr")]


def test_a_player_missing_on_one_side_is_a_gap() -> None:
    comparison = csdm.compare(ours().filter(pl.col("steamid") == 1), csdm.csdm_values(EXPORT))
    assert {field for steamid, field in gaps(comparison) if steamid == 2} == {
        f.ours for f in (*csdm.FIELDS, *csdm.CLUTCH_FIELDS)
    }


def test_summary_counts_gaps_per_field() -> None:
    comparison = csdm.compare(ours(kills={1: 21.0, 2: 12.0}), csdm.csdm_values(EXPORT))
    kills = csdm.summary(comparison).filter(pl.col("field") == "kills").row(0, named=True)
    assert (kills["players"], kills["gaps"], kills["max_abs_diff"]) == (2, 2, 2.0)
