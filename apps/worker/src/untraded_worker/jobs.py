# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The job handlers, by kind. `download` arrives in the next pull request.

`parse` (payload `{"match_id": "<uuid>"}`): the match's raw demo is in the store (`demo_key`).
The worker parses it, derives the round model, computes the metrics, writes the Parquet tables
under `matches/{id}/`, loads the SQL tables, refreshes who sees the match, and marks it `ready`.
A demo already known by its sha256 (the same match brought by two players, ADR 0009) is not
stored twice: the new match row is merged into the existing one.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import psycopg

from untraded.parsing import CanonicalMatch, parse_demo
from untraded_worker import load
from untraded_worker.analysis import analyze
from untraded_worker.queue import Job
from untraded_worker.runner import DeadHandler, Handler
from untraded_worker.store import LocalStore

Parse = Callable[..., CanonicalMatch]


class JobError(ValueError):
    """The job cannot succeed as it is (e.g. no demo): retrying will not help much."""


@dataclass(frozen=True)
class ParseJob:
    store: LocalStore
    parse: Parse = field(default=parse_demo)
    """`untraded.parsing.parse_demo`; tests replace it."""

    def __call__(self, conn: psycopg.Connection[Any], job: Job) -> None:
        match_id = uuid.UUID(str(job.payload["match_id"]))
        row = conn.execute(
            "SELECT mode::text, played_at, demo_key FROM match WHERE id = %s FOR UPDATE",
            (match_id,),
        ).fetchone()
        if row is None:
            return  # deleted meanwhile: nothing to do
        mode, played_at, demo_key = row
        if demo_key is None:
            raise JobError(f"match {match_id} has no demo in the store")
        source = conn.execute(
            "SELECT kind::text FROM match_source WHERE match_id = %s ORDER BY received_at LIMIT 1",
            (match_id,),
        ).fetchone()
        canonical = self.parse(
            self.store.path(demo_key),
            source=source[0] if source else "upload",
            mode=mode,
            played_at=played_at.date() if isinstance(played_at, dt.datetime) else None,
        )

        known = conn.execute(
            "SELECT id, demo_key FROM match WHERE sha256 = %s AND id <> %s FOR UPDATE",
            (canonical.match_id, match_id),
        ).fetchone()
        if known is not None:
            self._merge(conn, match_id, known[0], demo_key, known[1])
            return

        analysis = analyze(canonical.tables())
        prefix = f"matches/{match_id}"
        self.store.write_tables(prefix, analysis.tables)
        load.load_match(conn, match_id, analysis)
        conn.execute(
            "UPDATE match SET status = 'ready', parquet_prefix = %s, parsed_at = now(), "
            "error = NULL WHERE id = %s",
            (prefix, match_id),
        )
        load.refresh_access(conn, match_id)

    def _merge(
        self,
        conn: psycopg.Connection[Any],
        duplicate: uuid.UUID,
        known: uuid.UUID,
        duplicate_demo: str,
        known_demo: str | None,
    ) -> None:
        """The demo is a match we already have: its sources move to it, the duplicate goes."""
        conn.execute(
            "UPDATE match_source SET match_id = %s WHERE match_id = %s", (known, duplicate)
        )
        conn.execute("DELETE FROM match WHERE id = %s", (duplicate,))
        load.refresh_access(conn, known)
        if duplicate_demo != known_demo:
            # Last: a file deletion is not transactional, and nothing after it can fail but
            # the commit.
            self.store.delete(duplicate_demo)


def match_failed(conn: psycopg.Connection[Any], job: Job, error: str) -> None:
    conn.execute(
        "UPDATE match SET status = 'failed', error = %s WHERE id = %s",
        (error[:4000], uuid.UUID(str(job.payload["match_id"]))),
    )


def handlers(store: LocalStore) -> dict[str, Handler]:
    return {"parse": ParseJob(store)}


ON_DEAD: dict[str, DeadHandler] = {"parse": match_failed}
