# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Play sessions and their report (`play_session`, migration 0002).

A player's matches form one session as long as there is at most `GAP` between the end of one
and the start of the next. The report compares the session with the player's own 30 days before
it (`untraded.reference.compare_to_self`), recomputed from the matches' Parquet tables, never
averaged from per-match values (metrics-v1 § 0).

The `session` job (payload `{"steam_id": "...", "match_id": "<uuid>"}`) runs after each parse,
for every invited player of the match: it recomputes the session holding that match. A match
that joins two sessions merges them; the sessions it replaces are deleted.
"""

from __future__ import annotations

import datetime as dt
import math
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import polars as pl
import psycopg
from psycopg.types.json import Jsonb

from untraded import reference
from untraded_worker import queue
from untraded_worker.queue import Job
from untraded_worker.store import LocalStore

GAP = dt.timedelta(hours=1)
"""More than this between the end of a match and the start of the next: a new session."""


@dataclass(frozen=True)
class PlayedMatch:
    id: uuid.UUID
    sha256: str
    started_at: dt.datetime
    ended_at: dt.datetime
    prefix: str


def session_of(matches: Sequence[PlayedMatch], match_id: uuid.UUID) -> list[PlayedMatch]:
    """The session holding `match_id`, among a player's matches sorted by start."""
    sessions: list[list[PlayedMatch]] = []
    for match in matches:
        if sessions and match.started_at - max(m.ended_at for m in sessions[-1]) <= GAP:
            sessions[-1].append(match)
        else:
            sessions.append([match])
    return next((s for s in sessions if any(m.id == match_id for m in s)), [])


def queue_sessions(conn: psycopg.Connection[Any], match_id: uuid.UUID) -> int:
    """Queues a `session` job for each invited player of the match; returns how many."""
    players = conn.execute(
        """
        SELECT mp.steam_id FROM match_player mp
        JOIN app_user u ON u.steam_id = mp.steam_id AND u.deleted_at IS NULL
        WHERE mp.match_id = %s
        """,
        (match_id,),
    ).fetchall()
    for (steam_id,) in players:
        queue.enqueue(conn, "session", {"steam_id": str(steam_id), "match_id": str(match_id)})
    return len(players)


@dataclass(frozen=True)
class SessionJob:
    store: LocalStore
    window_days: int = reference.WINDOW_DAYS
    min_matches: int = reference.MIN_MATCHES
    min_rounds: int = reference.MIN_ROUNDS

    def __call__(self, conn: psycopg.Connection[Any], job: Job) -> None:
        steam_id = int(job.payload["steam_id"])
        match_id = uuid.UUID(str(job.payload["match_id"]))
        played = self._played(conn, steam_id)
        session = session_of(played, match_id)
        if not session:
            return  # the match is gone, not ready, or undated
        start = session[0].started_at
        first_day = start.date() - dt.timedelta(days=self.window_days)
        window = [m for m in played if first_day <= m.started_at.date() < start.date()]
        tables = [self._tables(m) for m in [*session, *window]]
        comparison = reference.compare_to_self(
            tables,
            steam_id,
            {m.sha256 for m in session},
            window_days=self.window_days,
            min_matches=self.min_matches,
            min_rounds=self.min_rounds,
        )
        self._save(conn, steam_id, session, comparison)

    def _played(self, conn: psycopg.Connection[Any], steam_id: int) -> list[PlayedMatch]:
        rows = conn.execute(
            """
            SELECT m.id, m.sha256, m.played_at, coalesce(m.ended_at, m.played_at),
                   m.parquet_prefix
            FROM match m JOIN match_player mp ON mp.match_id = m.id AND mp.steam_id = %s
            WHERE m.status = 'ready' AND m.played_at IS NOT NULL AND m.parquet_prefix IS NOT NULL
            ORDER BY m.played_at, m.id
            """,
            (steam_id,),
        ).fetchall()
        return [PlayedMatch(r[0], r[1].strip(), r[2], r[3], r[4]) for r in rows]

    def _tables(self, match: PlayedMatch) -> dict[str, pl.DataFrame]:
        tables = self.store.read_tables(match.prefix)
        # The reference places matches by day: the Parquet holds the day the match was parsed
        # with, the database the current one.
        tables["match"] = tables["match"].with_columns(
            pl.lit(match.started_at.date()).alias("played_at")
        )
        return tables

    def _save(
        self,
        conn: psycopg.Connection[Any],
        steam_id: int,
        session: Sequence[PlayedMatch],
        comparison: reference.SelfComparison,
    ) -> None:
        ids = [m.id for m in session]
        # Sessions this one replaces: any holding one of its matches (two sessions joined by a
        # match played between them, or the same session recomputed).
        conn.execute(
            """
            DELETE FROM play_session s WHERE s.steam_id = %s AND EXISTS (
                SELECT 1 FROM play_session_match sm
                WHERE sm.session_id = s.id AND sm.match_id = ANY(%s)
            )
            """,
            (steam_id, ids),
        )
        row = conn.execute(
            """
            INSERT INTO play_session (steam_id, started_at, ended_at, matches, rounds,
                                      reference_from, reference_to, reference_matches,
                                      reference_rounds, enough, params)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (
                steam_id,
                session[0].started_at,
                max(m.ended_at for m in session),
                comparison.session_matches,
                comparison.session_rounds,
                comparison.reference_from,
                comparison.reference_to,
                comparison.reference_matches,
                comparison.reference_rounds,
                comparison.enough,
                Jsonb(
                    {
                        "window_days": self.window_days,
                        "min_matches": self.min_matches,
                        "min_rounds": self.min_rounds,
                        "gap_minutes": GAP.total_seconds() / 60,
                    }
                ),
            ),
        ).fetchone()
        assert row is not None
        session_id = row[0]
        conn.cursor().executemany(
            "INSERT INTO play_session_match (session_id, match_id) VALUES (%s, %s)",
            [(session_id, match_id) for match_id in ids],
        )
        values = comparison.values.select(
            "metric", "version", "basis", "session", "reference", "delta"
        )
        conn.cursor().executemany(
            "INSERT INTO play_session_metric (session_id, metric_id, version, basis, session, "
            "reference, delta) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            [(session_id, *(_finite(v) for v in row)) for row in values.iter_rows()],
        )


def _finite(value: Any) -> Any:
    return None if isinstance(value, float) and not math.isfinite(value) else value
