# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The player's own reference (workstream E9, ADR 0010): a session against the 30 days before.

The reference is computed over **all the rounds** of the player's matches in the window, never
averaged from per-match values (metrics-v1 § 0). It excludes the session itself, so a very good
or very bad evening does not pull its own reference towards it. Below a minimum of matches and
rounds, the reference is not reliable enough to be shown.

Totals (kills, opening kills, HE damage, blind time dealt...) are compared **per round**: the
session and the reference do not have the same number of rounds. Rates, ratios and medians are
compared as they are.

The report also gives the **spread** of the reference, `reference_p10` and `reference_p90`: the
10th and 90th percentiles (linear interpolation, numpy's default) of the player's **per-match**
values over the same matches, so that a session can be placed against the range of an ordinary
match. Per-match values are not the pooled values above, which stay the reference itself (the
median of a match is not the pooled value): the spread is the width of a band, not a second
estimate. A session of about two matches is less dispersed than a single match, so a session
inside the band says little: read the position with care. The spread needs
`reference.min_spread_matches` matches (and as many values per metric), and is null below that.

Dates come from `match.played_at` (a date, no time): a match played earlier on the session's
first day is neither in the session nor in the reference. Matches without a date are left out
of the reference.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

import polars as pl

from untraded.metrics import REGISTRY, Dataset, compute
from untraded.metrics.dataset import MatchTables
from untraded.metrics.registry import ParamValue

WINDOW_DAYS = 30
"""⚙ `reference.window_days`: the reference covers this many days before the session."""
MIN_MATCHES = 5
"""⚙ `reference.min_matches`: fewer matches in the window, and the reference is not shown."""
MIN_ROUNDS = 100
"""⚙ `reference.min_rounds`: fewer rounds played in the window, and it is not shown either."""
MIN_SPREAD_MATCHES = 10
"""⚙ `reference.min_spread_matches`: fewer matches (with a value for the metric), and the spread
(`reference_p10`, `reference_p90`) is not shown. A percentile of a handful of values is the
extreme of a handful of values."""
SPREAD_LOW, SPREAD_HIGH = 0.10, 0.90
"""The percentiles of the spread (linear interpolation between the order statistics)."""
MIN_SPREAD_ROUNDS = 10
"""A match the player played for fewer rounds (a quick abandon) is left out of the spread: its
per-round totals mean nothing (the same rule as the level references)."""


TOTAL_UNITS = frozenset({"count", "hp"})
TOTAL_METRICS = frozenset({"util.enemy_blind_time", "util.team_blind_time"})
"""Totals in seconds (other metrics in seconds are averages, such as `util.blind_per_flash`)."""


def is_total(metric_id: str) -> bool:
    """Whether the metric adds up over matches, and is so compared per round."""
    return REGISTRY[metric_id].unit in TOTAL_UNITS or metric_id in TOTAL_METRICS


class ReferenceError(ValueError):
    """The session cannot be placed in time, or the player is not in it."""


@dataclass(frozen=True)
class SelfComparison:
    player: int
    session_matches: int
    session_rounds: int
    reference_from: dt.date
    reference_to: dt.date
    """Inclusive: the day before the session's first day."""
    reference_matches: int
    reference_rounds: int
    enough: bool
    """The reference has at least `min_matches` matches and `min_rounds` rounds."""
    values: pl.DataFrame
    """One row per value metric: `metric`, `version`, `basis` (`value`, or `per_round` for
    totals), `session`, `reference`, `delta` (session - reference), `reference_p10`,
    `reference_p90` (the spread of the per-match values, in the same unit and basis as
    `reference`). `reference` and `delta` are null when the reference is not enough; the spread
    is also null when there are fewer than `min_spread_matches` matches."""


def compare_to_self(
    matches: Sequence[MatchTables],
    player: int,
    session: Collection[str],
    *,
    window_days: int = WINDOW_DAYS,
    min_matches: int = MIN_MATCHES,
    min_rounds: int = MIN_ROUNDS,
    min_spread_matches: int = MIN_SPREAD_MATCHES,
    params: Mapping[str, ParamValue] | None = None,
) -> SelfComparison:
    """Compares the `session` matches (match ids) of `player` with the reference built from the
    other `matches` played in the `window_days` days before the session's first day.

    `matches` holds the canonical and derived tables of each match, as for
    `Dataset.from_matches`; matches the player did not play are ignored.
    """
    played = [m for m in matches if _played_by(m, player)]
    in_session = [m for m in played if _match_id(m) in session]
    missing = set(session) - {_match_id(m) for m in in_session}
    if missing:
        raise ReferenceError(f"{len(missing)} session match(es) without this player: {missing}")
    dates = [_played_at(m) for m in in_session]
    if not in_session or any(d is None for d in dates):
        raise ReferenceError("every session match needs a played_at date")
    start = min(d for d in dates if d is not None)
    first, last = start - dt.timedelta(days=window_days), start - dt.timedelta(days=1)
    reference = [
        m
        for m in played
        if _match_id(m) not in session
        and (day := _played_at(m)) is not None
        and first <= day <= last
    ]

    session_values, session_rounds = _values(in_session, player, params)
    reference_rounds = 0
    values = session_values.rename({"value": "session"}).with_columns(
        pl.lit(None, pl.Float64).alias("reference"),
        pl.lit(None, pl.Float64).alias("reference_p10"),
        pl.lit(None, pl.Float64).alias("reference_p90"),
    )
    enough = False
    if reference:
        reference_values, reference_rounds = _values(reference, player, params)
        enough = len(reference) >= min_matches and reference_rounds >= min_rounds
        if enough:
            per_match = [match_values(m, player, params) for m in reference]
            values = (
                session_values.rename({"value": "session"})
                .join(
                    reference_values.rename({"value": "reference"}),
                    on=["metric", "version"],
                    how="left",
                )
                .join(
                    spread([v for v in per_match if v is not None], min_matches=min_spread_matches),
                    on=["metric", "version"],
                    how="left",
                )
            )
    values = values.with_columns((pl.col("session") - pl.col("reference")).alias("delta"))
    basis = pl.DataFrame(
        {
            "metric": list(REGISTRY),
            "basis": ["per_round" if is_total(m.id) else "value" for m in REGISTRY.values()],
        }
    )
    values = values.join(basis, on="metric", how="left")
    return SelfComparison(
        player=player,
        session_matches=len(in_session),
        session_rounds=session_rounds,
        reference_from=first,
        reference_to=last,
        reference_matches=len(reference),
        reference_rounds=reference_rounds,
        enough=enough,
        values=values.select(
            "metric",
            "version",
            "basis",
            "session",
            "reference",
            "delta",
            "reference_p10",
            "reference_p90",
        ).sort("metric"),
    )


def match_values(
    match: MatchTables, player: int, params: Mapping[str, ParamValue] | None = None
) -> pl.DataFrame | None:
    """The player's value metrics over one match, as the reference compares them (`metric`,
    `version`, `value`; totals per round). None when the player played fewer than
    `MIN_SPREAD_ROUNDS` rounds of it."""
    values, rounds = _values([match], player, params)
    return values if rounds >= MIN_SPREAD_ROUNDS else None


def spread(
    per_match: Sequence[pl.DataFrame], *, min_matches: int = MIN_SPREAD_MATCHES
) -> pl.DataFrame:
    """The 10th and 90th percentiles of each metric over matches' values (`match_values`):
    `metric`, `version`, `reference_p10`, `reference_p90`.

    Linear interpolation between the order statistics (numpy's default, `method="linear"`).
    Missing and NaN values are left out; a metric with fewer than `min_matches` values has no
    spread (null), as does everything when there are fewer than `min_matches` matches."""
    schema = {"metric": pl.String, "version": pl.String} | {
        "reference_p10": pl.Float64,
        "reference_p90": pl.Float64,
    }
    if len(per_match) < min_matches or not per_match:
        return pl.DataFrame(schema=schema)
    values = pl.concat(per_match).with_columns(pl.col("value").fill_nan(None))
    return (
        values.drop_nulls("value")
        .group_by("metric", "version")
        .agg(
            pl.col("value").len().alias("n"),
            pl.col("value").quantile(SPREAD_LOW, "linear").alias("reference_p10"),
            pl.col("value").quantile(SPREAD_HIGH, "linear").alias("reference_p90"),
        )
        .with_columns(
            *(
                pl.when(pl.col("n") >= min_matches).then(pl.col(c)).alias(c)
                for c in ("reference_p10", "reference_p90")
            )
        )
        .select(*schema)
    )


def _values(
    matches: Sequence[MatchTables], player: int, params: Mapping[str, ParamValue] | None
) -> tuple[pl.DataFrame, int]:
    """The player's value metrics over all the rounds of `matches`, and the rounds played."""
    ds = Dataset.from_matches(matches)
    rounds = int(ds.rounds_played().filter(pl.col("steamid") == player)["rounds"].sum())
    counts = [m.id for m in REGISTRY.values() if is_total(m.id)]
    values = compute(ds, params=params).filter(pl.col("steamid") == player)
    per_round = (
        pl.when(pl.col("metric").is_in(counts))
        .then(pl.col("value") / rounds if rounds else None)
        .otherwise(pl.col("value"))
    )
    return values.select("metric", "version", per_round.alias("value")), rounds


def _match_id(tables: MatchTables) -> str:
    return str(tables["match"]["match_id"][0])


def _played_at(tables: MatchTables) -> dt.date | None:
    value = tables["match"]["played_at"][0]
    return value if isinstance(value, dt.date) else None


def _played_by(tables: MatchTables, player: int) -> bool:
    return bool((tables["round_player"]["steamid"] == player).any())
