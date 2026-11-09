# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""References by level (`level_reference`, migration 0004): what players of a rating band do.

They pool **every player of the collected matches**, not only the users: each match brings ten
players. Collected means served by Valve (`valve_bot`): a demo someone sent can be edited, ranks
included, and these references are compared with everyone else's sessions, so it counts for its
sender alone (`credit`) and stays out of them, until the collector brings the same demo. Players
who opted out (`player.benchmark_opt_out`) are left out, and a band is only
published with at least `MIN_PLAYERS` distinct players, so no one can be singled out.

For each Premier rating band of `BAND` points, the (player, match) rows of that band are pooled,
widening the band one step on each side until there are `MIN_PLAYER_MATCHES` rows and
`MIN_PLAYERS` players. Then, per metric:
- totals (kills, damage...) are compared per round: sum of the totals ÷ sum of the rounds;
- the others (rates, ratios, medians) take the median of the per-match values;
- the spread (`p10`, `p90`) is the 10th and 90th percentile of the per-match values (totals per
  round), linear interpolation (numpy's default). It is published only for a metric with at
  least `MIN_PLAYER_MATCHES` values from at least `MIN_PLAYERS` players, an effective
  number of players (`MIN_EFFECTIVE_PLAYERS`) and none holding more than `MAX_PLAYER_SHARE` of
  them: no more precise than the rest of the band, and never one player's own percentiles.
  Infinite values are left out. A (player, match) row weighs as one, as for the median.

Rows of matches the player played for fewer than `MIN_ROUNDS` rounds (a quick abandon) are left
out. The worker recomputes everything when idle, every `EVERY`.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

import polars as pl
import psycopg

from untraded.reference import SPREAD_HIGH, SPREAD_LOW, is_total

BAND = 2500
MIN_PLAYER_MATCHES = 300
MIN_PLAYERS = 20
MIN_ROUNDS = 10
MAX_PLAYER_SHARE = 0.10
"""No player holds more than this share of the values a spread rests on: one heavy contributor
among 20 players would have their own percentiles published. It also means at least 10 players."""
MIN_EFFECTIVE_PLAYERS = 15
"""The effective number of players behind a spread, (sum of the values)² ÷ (sum of each player's
values squared), is at least this: 20 players with equal shares are 20, five players with most
of the rows and fifteen with one each are about 5, ten heavy ones and ten with a few about 12.
A head count alone would not tell, and a share of the values relative to the pool would stop
publishing as the pool grows (most players of a band appear once)."""
EVERY = dt.timedelta(hours=1)
LOCK = 0x756E7472_00000001
"""Advisory lock key held while `level_reference` is rewritten."""

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
  AND EXISTS (
      SELECT 1 FROM match_source ms
      WHERE ms.match_id = m.id AND ms.kind = 'valve_bot' AND ms.rejected IS NULL
  )
"""


def band_of(rank: int) -> int:
    return rank // BAND * BAND


def aggregate(rows: pl.DataFrame) -> pl.DataFrame:
    """One reference value per metric over `rows` (`steam_id`, `match_id`, `rounds`, `metric_id`,
    `version`, `value`), and its spread (`p10`, `p90`)."""
    totals = {m: is_total(m) for m in rows["metric_id"].unique().to_list()}
    rows = (
        rows.with_columns(pl.col("metric_id").replace_strict(totals).alias("total"))
        .with_columns(
            pl.when(pl.col("total"))
            .then(pl.col("value") / pl.col("rounds"))
            .otherwise(pl.col("value"))
            .alias("per_match")
        )
        .with_columns(
            # Missing, NaN and infinite: no value.
            pl.when(pl.col("per_match").is_finite()).then(pl.col("per_match")).alias("per_match")
        )
    )
    rows = rows.with_columns(
        pl.col("per_match").count().over("metric_id", "version", "steam_id").alias("player_values")
    )
    values = pl.col("per_match").count()
    known = pl.col("steam_id").filter(pl.col("per_match").is_not_null())
    # Each player's row carries that player's number of values: summed over the rows with a
    # value, it is the sum over players of their values squared.
    squares = pl.col("player_values").filter(pl.col("per_match").is_not_null()).sum()
    publishable = (
        (values >= MIN_PLAYER_MATCHES)
        & (known.n_unique() >= MIN_PLAYERS)
        & (values * values >= MIN_EFFECTIVE_PLAYERS * squares)
        & (pl.col("player_values").max() <= MAX_PLAYER_SHARE * values)
    )
    return (
        rows.group_by("metric_id", "version", "total")
        .agg(
            pl.col("value").sum().alias("sum"),
            pl.col("rounds").sum().alias("rounds"),
            pl.col("value").drop_nulls().median().alias("median"),
            pl.when(publishable)
            .then(pl.col("per_match").quantile(SPREAD_LOW, "linear"))
            .alias("p10"),
            pl.when(publishable)
            .then(pl.col("per_match").quantile(SPREAD_HIGH, "linear"))
            .alias("p90"),
        )
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
            "p10",
            "p90",
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
    """Recomputes the level references of `mode`; returns how many bands are published. Two
    recomputations (the worker's, and `backfill-spread`) wait for each other: they would both
    write the same primary keys."""
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK,))
        cursor = conn.execute(ROWS, {"mode": mode, "min_rounds": MIN_ROUNDS})
        rows = pl.DataFrame(
            cursor.fetchall(),
            schema=["rank", "steam_id", "match_id", "rounds", "metric_id", "version", "value"],
            orient="row",
        )
        found = levels(rows)
        conn.execute("DELETE FROM level_reference WHERE mode = %s", (mode,))
        if not found.is_empty():
            columns = [
                "band_low", "band_high", "used_low", "used_high", "metric_id", "version",
                "basis", "value", "p10", "p90", "player_matches", "players", "rounds",
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
    columns = [
        "metric_id", "version", "basis", "value", "p10", "p90", "used_low", "used_high",
        "player_matches", "rounds",
    ]  # fmt: skip
    if rank is None or rank <= 0:
        return pl.DataFrame(schema=columns)
    rows = conn.execute(
        f"SELECT {', '.join(columns)} FROM level_reference WHERE mode = %s AND band_low = %s",
        (mode, band_of(rank)),
    ).fetchall()
    return pl.DataFrame(rows, schema=columns, orient="row")
