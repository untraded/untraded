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
    totals), `session`, `reference`, `delta` (session - reference). `reference` and `delta`
    are null when the reference is not enough."""


def compare_to_self(
    matches: Sequence[MatchTables],
    player: int,
    session: Collection[str],
    *,
    window_days: int = WINDOW_DAYS,
    min_matches: int = MIN_MATCHES,
    min_rounds: int = MIN_ROUNDS,
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
        pl.lit(None, pl.Float64).alias("reference")
    )
    enough = False
    if reference:
        reference_values, reference_rounds = _values(reference, player, params)
        enough = len(reference) >= min_matches and reference_rounds >= min_rounds
        if enough:
            values = session_values.rename({"value": "session"}).join(
                reference_values.rename({"value": "reference"}),
                on=["metric", "version"],
                how="left",
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
        values=values.select("metric", "version", "basis", "session", "reference", "delta").sort(
            "metric"
        ),
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
