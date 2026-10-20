# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""References by level (`level_reference`, migration 0004): what players of a rating band do.

They pool **every player of the collected matches**, not only the users: each match brings ten
players. Players who opted out (`player.benchmark_opt_out`) are left out, and a band is only
published with at least `MIN_PLAYERS` distinct players, so no one can be singled out.

For each Premier rating band of `BAND` points, the (player, match) rows of that band are pooled,
widening the band one step on each side until there are `MIN_PLAYER_MATCHES` rows and
`MIN_PLAYERS` players. Then, per metric:
- totals (kills, damage...) are compared per round: sum of the totals ÷ sum of the rounds;
- the others (rates, ratios, medians) take the median of the per-match values.

Rows of matches the player played for fewer than `MIN_ROUNDS` rounds (a quick abandon) are left
out. The worker recomputes everything when idle, every `EVERY`.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

import polars as pl
import psycopg

from untraded.reference import is_total

BAND = 2500
MIN_PLAYER_MATCHES = 300
MIN_PLAYERS = 20
MIN_ROUNDS = 10
EVERY = dt.timedelta(hours=1)

log = logging.getLogger("untraded.worker")

ROWS = """
SELECT mp.rank, mp.steam_id, v.match_id::text, mp.rounds_on_team, v.metric_id, v.version, v.value
FROM metric_value v
JOIN metric_current c USING (metric_id, version)
JOIN match m ON m.id = v.match_id AND m.status = 'ready' AND m.mode = %(mode)s
JOIN match_player mp ON mp.match_id = v.match_id AND mp.steam_id = v.steam_id
JOIN player p ON p.steam_id = v.steam_id AND NOT p.benchmark_opt_out
WHERE v.scope = 'match' AND v.params_hash = 'default'
  AND mp.rank > 0 AND mp.rounds_on_team >= %(min_rounds)s
"""


def band_of(rank: int) -> int:
    return rank // BAND * BAND


def aggregate(rows: pl.DataFrame) -> pl.DataFrame:
    """One reference value per metric over `rows` (`steam_id`, `match_id`, `rounds`, `metric_id`,
    `version`, `value`)."""
    totals = {m: is_total(m) for m in rows["metric_id"].unique().to_list()}
    return (
        rows.group_by("metric_id", "version")
        .agg(
            pl.col("value").sum().alias("sum"),
            pl.col("rounds").sum().alias("rounds"),
            pl.col("value").drop_nulls().median().alias("median"),
        )
        .with_columns(pl.col("metric_id").replace_strict(totals).alias("total"))
        .select(
            "metric_id",
            "version",
            pl.when(pl.col("total"))
            .then(pl.lit("per_round"))
            .otherwise(pl.lit("value"))
            .alias("basis"),
            pl.when(pl.col("total"))
            .then(pl.col("sum") / pl.col("rounds"))
            .otherwise(pl.col("median"))
            .alias("value"),
        )
    )


def levels(rows: pl.DataFrame) -> pl.DataFrame:
    """Every band's reference, widened as needed (columns of `level_reference`)."""
    if rows.is_empty():
        return pl.DataFrame()
    samples = rows.select("rank", "steam_id", "match_id", "rounds").unique(["steam_id", "match_id"])
    lowest = band_of(int(samples["rank"].min()))  # type: ignore[arg-type]
    highest = band_of(int(samples["rank"].max()))  # type: ignore[arg-type]
    out = []
    for band in range(lowest, highest + BAND, BAND):
        for step in range(0, (highest - lowest) // BAND + 1):
            low, high = band - step * BAND, band + BAND + step * BAND
            pool = samples.filter((pl.col("rank") >= low) & (pl.col("rank") < high))
            if pool.height >= MIN_PLAYER_MATCHES and pool["steam_id"].n_unique() >= MIN_PLAYERS:
                break
        else:
            continue
        picked = rows.join(pool.select("steam_id", "match_id"), on=["steam_id", "match_id"])
        out.append(
            aggregate(picked).with_columns(
                pl.lit(band).alias("band_low"),
                pl.lit(band + BAND).alias("band_high"),
                pl.lit(max(low, lowest)).alias("used_low"),
                pl.lit(min(high, highest + BAND)).alias("used_high"),
                pl.lit(pool.height).alias("player_matches"),
                pl.lit(pool["steam_id"].n_unique()).alias("players"),
                pl.lit(int(pool["rounds"].sum())).alias("rounds"),
            )
        )
    return pl.concat(out) if out else pl.DataFrame()


def compute_levels(conn: psycopg.Connection[Any], mode: str = "premier") -> int:
    """Recomputes the level references of `mode`; returns how many bands are published."""
    cursor = conn.execute(ROWS, {"mode": mode, "min_rounds": MIN_ROUNDS})
    rows = pl.DataFrame(
        cursor.fetchall(),
        schema=["rank", "steam_id", "match_id", "rounds", "metric_id", "version", "value"],
        orient="row",
    )
    found = levels(rows)
    with conn.transaction():
        conn.execute("DELETE FROM level_reference WHERE mode = %s", (mode,))
        if not found.is_empty():
            columns = [
                "band_low", "band_high", "used_low", "used_high", "metric_id", "version",
                "basis", "value", "player_matches", "players", "rounds",
            ]  # fmt: skip
            with conn.cursor().copy(
                "COPY level_reference (mode, " + ", ".join(columns) + ") FROM STDIN"
            ) as copy:
                for row in found.select(columns).iter_rows():
                    copy.write_row((mode, *row))
    bands = 0 if found.is_empty() else found["band_low"].n_unique()
    log.info("level references: %s band(s) of %s", bands, mode)
    return bands


def level_reference(
    conn: psycopg.Connection[Any], rank: int | None, mode: str = "premier"
) -> pl.DataFrame:
    """The reference of the band of `rank` (empty when none is published)."""
    columns = ["metric_id", "basis", "value", "used_low", "used_high", "player_matches", "rounds"]
    if rank is None or rank <= 0:
        return pl.DataFrame(schema=columns)
    rows = conn.execute(
        f"SELECT {', '.join(columns)} FROM level_reference WHERE mode = %s AND band_low = %s",
        (mode, band_of(rank)),
    ).fetchall()
    return pl.DataFrame(rows, schema=columns, orient="row")
