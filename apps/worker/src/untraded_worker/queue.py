# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The job queue of ADR 0004, in the `job` table.

A worker claims the next ready job with `FOR UPDATE SKIP LOCKED`, so several workers never take
the same one. A failed job comes back later, with an exponential backoff, until it reaches its
`max_attempts`: then it is `dead` and stays visible with its last error. A job left `running` by
a worker that died is put back in the queue after `STALE_AFTER`.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

BACKOFF_BASE = dt.timedelta(seconds=30)
BACKOFF_MAX = dt.timedelta(hours=1)
STALE_AFTER = dt.timedelta(minutes=30)
"""A running job not finished after this long is considered abandoned (a parse takes < 1 min)."""
STALE_AFTER_BY_KIND: Mapping[str, dt.timedelta] = {"download": dt.timedelta(hours=3)}
"""Slower kinds: a Valve download can take 20 minutes or more (throttled servers)."""
STALE_EVERY = dt.timedelta(minutes=5)
"""How often a running worker looks for jobs abandoned by another one (a container replaced by
a deployment has a new name: its jobs are only found this way)."""


@dataclass(frozen=True)
class Job:
    id: int
    kind: str
    payload: dict[str, Any]
    attempts: int
    """Including the current one."""
    max_attempts: int


def backoff(attempts: int) -> dt.timedelta:
    """Delay before the next try after `attempts` failed tries: 30 s, 1 min, 2 min... up to 1 h."""
    return min(BACKOFF_BASE * (1 << min(max(attempts - 1, 0), 16)), BACKOFF_MAX)


def enqueue(
    conn: psycopg.Connection[Any],
    kind: str,
    payload: Mapping[str, Any] | None = None,
    *,
    priority: int = 0,
    max_attempts: int = 5,
) -> int:
    row = conn.execute(
        "INSERT INTO job (kind, payload, priority, max_attempts) VALUES (%s, %s, %s, %s) "
        "RETURNING id",
        (kind, Jsonb(dict(payload or {})), priority, max_attempts),
    ).fetchone()
    assert row is not None
    return int(row[0])


def claim(conn: psycopg.Connection[Any], kinds: Sequence[str], worker: str) -> Job | None:
    """Takes the next ready job of one of `kinds`, or None."""
    row = conn.execute(
        """
        UPDATE job SET status = 'running', attempts = attempts + 1,
                       locked_by = %(worker)s, locked_at = now()
        WHERE id = (
            SELECT id FROM job
            WHERE status = 'queued' AND run_at <= now() AND kind = ANY(%(kinds)s)
            ORDER BY priority DESC, run_at
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        )
        RETURNING id, kind, payload, attempts, max_attempts
        """,
        {"worker": worker, "kinds": list(kinds)},
    ).fetchone()
    if row is None:
        return None
    return Job(id=row[0], kind=row[1], payload=row[2], attempts=row[3], max_attempts=row[4])


def complete(conn: psycopg.Connection[Any], job: Job) -> None:
    conn.execute(
        "UPDATE job SET status = 'done', finished_at = now(), locked_by = NULL, "
        "last_error = NULL WHERE id = %s",
        (job.id,),
    )


def fail(conn: psycopg.Connection[Any], job: Job, error: str) -> bool:
    """Records the failure; returns True when the job is dead (no attempt left)."""
    dead = job.attempts >= job.max_attempts
    conn.execute(
        """
        UPDATE job SET status = %(status)s, last_error = %(error)s, locked_by = NULL,
                       run_at = now() + %(delay)s,
                       finished_at = CASE WHEN %(dead)s THEN now() END
        WHERE id = %(id)s
        """,
        {
            "status": "dead" if dead else "queued",
            "error": error[:4000],
            "delay": backoff(job.attempts),
            "dead": dead,
            "id": job.id,
        },
    )
    return dead


def abandoned(
    conn: psycopg.Connection[Any],
    *,
    worker: str | None = None,
    older_than: dt.timedelta = STALE_AFTER,
    by_kind: Mapping[str, dt.timedelta] = STALE_AFTER_BY_KIND,
) -> list[Job]:
    """The running jobs nobody runs any more, locked: those of `worker` (it runs none, as it
    starts), or else those running for too long (their worker is gone). The caller records each
    as a failed attempt (`fail`), so a job that kills its worker every time ends `dead` after
    its attempts, with a backoff in between, instead of a restart loop."""
    mine = worker is not None
    rows = conn.execute(
        """
        SELECT id, kind, payload, attempts, max_attempts FROM job
        WHERE status = 'running'
          AND CASE WHEN %(mine)s THEN locked_by = %(worker)s
                   ELSE locked_at < now() - coalesce(
                       (%(by_kind)s::jsonb ->> kind)::double precision * interval '1 second',
                       %(default)s)
              END
        ORDER BY id
        FOR UPDATE SKIP LOCKED
        """,
        {
            "mine": mine,
            "worker": worker,
            "by_kind": Jsonb({k: v.total_seconds() for k, v in by_kind.items()}),
            "default": older_than,
        },
    ).fetchall()
    return [Job(id=r[0], kind=r[1], payload=r[2], attempts=r[3], max_attempts=r[4]) for r in rows]
