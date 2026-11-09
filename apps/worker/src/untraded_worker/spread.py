# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Fills the spread of the references of the sessions written before it existed:
`untraded-worker backfill-spread` (migration 0015).

It writes `play_session_metric.reference_p10` and `reference_p90` and nothing else: no session is
recomputed, so no session changes its id (a `reanalyze --force` would, and an old report link
would lead to the 404 page), and the report, the priorities and the votes stay as they are. It
can be run again: it only visits the metric rows that have a reference and no spread yet, and it
never overwrites a spread.

- A session against **the player's own days** gets the percentiles of the player's per-match
  values over the matches of its stored reference window (`reference_from` to `reference_to`, the
  session excluded), computed from the Parquet tables with the same function the session job
  uses (`untraded.reference.spread`). Fewer than `min_spread_matches` matches: nothing.
- A session against **a level** gets the `p10` and `p90` of the player's band in `level_reference`
  as published now; the level references are recomputed first, since the rows written before the
  migration have none. The band is the player's rating in the session's most recent rated match,
  as in the session job. The `reference` of the session stays the value it had then: a level
  reference moves every hour, so the band may not be centred on it to the decimal.

A metric row whose version is no longer the current one stays without a spread: its reference
was computed by a formula that is not the one now.
"""

from __future__ import annotations

import logging
import math
import uuid
from typing import Any

import polars as pl
import psycopg

from untraded import reference
from untraded_worker import levels
from untraded_worker.sessions import PlayedMatch, SessionJob, session_rank
from untraded_worker.store import LocalStore

log = logging.getLogger("untraded.worker")

TODO = """
SELECT s.id, s.steam_id, s.reference_kind, s.reference_from, s.reference_to
FROM play_session s
JOIN app_user u ON u.steam_id = s.steam_id AND u.deleted_at IS NULL
WHERE s.reference_kind IN ('self', 'level')
  AND (s.reference_kind = 'level' OR s.reference_matches >= %(min_matches)s)
  AND EXISTS (
      SELECT 1 FROM play_session_metric m
      WHERE m.session_id = s.id AND m.reference IS NOT NULL AND m.reference_p10 IS NULL
  )
ORDER BY s.steam_id, s.started_at
"""

UPDATE_SELF = """
UPDATE play_session_metric SET reference_p10 = %s, reference_p90 = %s
WHERE session_id = %s AND metric_id = %s AND version = %s
  AND reference IS NOT NULL AND reference_p10 IS NULL AND reference_p90 IS NULL
"""

UPDATE_LEVEL = """
UPDATE play_session_metric SET reference_p10 = %s, reference_p90 = %s
WHERE session_id = %s AND metric_id = %s AND basis = %s
  AND reference IS NOT NULL AND reference_p10 IS NULL AND reference_p90 IS NULL
"""


def _finite(value: Any) -> float | None:
    return None if value is None or not math.isfinite(value) else float(value)


def backfill(
    conn: psycopg.Connection[Any],
    store: LocalStore,
    *,
    min_spread_matches: int = reference.MIN_SPREAD_MATCHES,
    refresh_levels: bool = True,
) -> int:
    """Returns how many sessions got at least one spread. `refresh_levels` recomputes the level
    references first, when a session is against a level."""
    sessions = conn.execute(TODO, {"min_matches": min_spread_matches}).fetchall()
    if refresh_levels and any(kind == "level" for _, _, kind, _, _ in sessions):
        levels.compute_levels(conn)
    job = SessionJob(store)
    played: dict[int, list[PlayedMatch]] = {}
    per_match: dict[tuple[int, uuid.UUID], pl.DataFrame | None] = {}
    filled = 0
    for session_id, steam_id, kind, first, last in sessions:
        members = [
            row[0]
            for row in conn.execute(
                "SELECT match_id FROM play_session_match WHERE session_id = %s", (session_id,)
            ).fetchall()
        ]
        with conn.transaction():
            if kind == "self":
                if steam_id not in played:
                    played[steam_id] = job._played(conn, steam_id)
                window = [
                    m
                    for m in played[steam_id]
                    if m.id not in members and first <= m.started_at.date() <= last
                ]
                for m in window:
                    if (steam_id, m.id) not in per_match:
                        per_match[(steam_id, m.id)] = reference.match_values(
                            job._tables(m), steam_id
                        )
                found = reference.spread(
                    [v for m in window if (v := per_match[(steam_id, m.id)]) is not None],
                    min_matches=min_spread_matches,
                ).drop_nulls(["reference_p10", "reference_p90"])
                params = [
                    (_finite(p10), _finite(p90), session_id, metric, version)
                    for metric, version, p10, p90 in found.iter_rows()
                ]
                sql = UPDATE_SELF
            else:
                level = levels.level_reference(conn, session_rank(conn, steam_id, members))
                params = [
                    (_finite(p10), _finite(p90), session_id, metric, basis)
                    for metric, basis, p10, p90 in level.select(
                        "metric_id", "basis", "p10", "p90"
                    ).iter_rows()
                    if p10 is not None and p90 is not None
                ]
                sql = UPDATE_LEVEL
            changed = 0
            with conn.cursor() as cursor:
                for row in params:
                    cursor.execute(sql, row)
                    changed += cursor.rowcount
            filled += changed > 0
    log.info("spread filled for %s of %s session(s)", filled, len(sessions))
    return filled
