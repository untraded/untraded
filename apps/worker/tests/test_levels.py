# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from typing import Any

import polars as pl
import psycopg
import pytest

from untraded_worker import levels

KILLS, KAST = "base.kills", "base.kast"  # a total (per round) and a rate (median)


def rows(
    players: int, matches: int, rank: int, *, kills: float = 20.0, kast: float = 70.0
) -> pl.DataFrame:
    """`players` players of rating `rank`, `matches` matches each, 20 rounds a match."""
    data: list[tuple[Any, ...]] = []
    for p in range(players):
        steam = rank * 1000 + p
        for m in range(matches):
            match = f"{steam}-{m}"
            data.append((rank, steam, match, 20, KILLS, "1.0.0", kills))
            data.append((rank, steam, match, 20, KAST, "1.1.0", kast + p))
    return pl.DataFrame(
        data,
        schema=["rank", "steam_id", "match_id", "rounds", "metric_id", "version", "value"],
        orient="row",
    )


def test_a_full_band_stands_alone() -> None:
    found = levels.levels(rows(25, 15, 18_000, kills=20, kast=70))  # 375 rows, 25 players
    band = found.filter(pl.col("band_low") == 17_500)
    values = dict(zip(band["metric_id"], band["value"], strict=True))
    assert values[KILLS] == pytest.approx(1.0)  # 20 kills in 20 rounds
    assert values[KAST] == pytest.approx(70 + 12)  # median of 70..94
    first = band.row(0, named=True)
    assert (first["used_low"], first["used_high"]) == (17_500, 20_000)
    assert (first["player_matches"], first["players"], first["rounds"]) == (375, 25, 7_500)
    assert set(band["basis"]) == {"per_round", "value"}


def test_a_thin_band_borrows_from_its_neighbours() -> None:
    data = pl.concat([rows(5, 10, 13_000), rows(25, 15, 18_000), rows(25, 15, 22_000)])
    found = levels.levels(data)
    thin = found.filter(pl.col("band_low") == 12_500).row(0, named=True)
    # 50 rows and 5 players alone: widened until the 17,500 band joins in.
    assert (thin["used_low"], thin["used_high"]) == (12_500, 20_000)
    assert thin["players"] == 30
    # Empty bands in between still get a reference, from their widened neighbourhood.
    assert set(found["band_low"]) == {12_500, 15_000, 17_500, 20_000}


def test_too_few_players_publish_nothing() -> None:
    assert levels.levels(rows(10, 100, 18_000)).is_empty()  # 1,000 rows but only 10 players
    assert levels.levels(pl.DataFrame()).is_empty()


def test_bands() -> None:
    assert levels.band_of(17_499) == 15_000
    assert levels.band_of(17_500) == 17_500


@pytest.mark.db
def test_level_references_are_computed_from_the_database(conn: psycopg.Connection[Any]) -> None:
    conn.execute("TRUNCATE match, player, app_user, metric_definition CASCADE")
    conn.execute(
        "INSERT INTO metric_definition (metric_id, version, name, unit, kind, params, doc) "
        "VALUES ('base.kills', '1.0.0', 'Kills', 'count', 'value', '{}', '')"
    )
    conn.execute("INSERT INTO metric_current VALUES ('base.kills', '1.0.0')")
    for _ in range(16):
        match = conn.execute(
            "INSERT INTO match (mode, status) VALUES ('premier', 'ready') RETURNING id"
        ).fetchone()
        assert match is not None
        for p in range(21):
            steam = 76561198000000000 + p
            conn.execute(
                "INSERT INTO player (steam_id, last_name, benchmark_opt_out) VALUES (%s, 'p', %s) "
                "ON CONFLICT DO NOTHING",
                (steam, p == 20),  # the last one opted out
            )
            conn.execute(
                "INSERT INTO match_player (match_id, steam_id, team, name, rounds_on_team, rank) "
                "VALUES (%s, %s, 'A', 'p', 20, 18000)",
                (match[0], steam),
            )
            conn.execute(
                "INSERT INTO metric_value (match_id, steam_id, scope, metric_id, version, "
                "params_hash, value) "
                "VALUES (%s, %s, 'match', 'base.kills', '1.0.0', 'default', %s)",
                (match[0], steam, 40 if p == 20 else 20),
            )
    assert levels.compute_levels(conn) == 1
    ref = levels.level_reference(conn, 19_000)
    assert ref.row(0, named=True)["value"] == pytest.approx(1.0)  # the opted-out 40s are left out
    assert ref.row(0, named=True)["player_matches"] == 16 * 20
    assert levels.level_reference(conn, 3_000).is_empty()
    assert levels.level_reference(conn, None).is_empty()
