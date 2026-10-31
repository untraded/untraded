# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""`retry-failed` against PostgreSQL: a failed match goes back in the queue from its last dead
job, unless its raw demo is gone."""

from __future__ import annotations

import uuid
from typing import Any

import psycopg
import pytest

from untraded_worker import queue
from untraded_worker.retry import retry_failed

pytestmark = pytest.mark.db


@pytest.fixture
def db(conn: psycopg.Connection[Any]) -> psycopg.Connection[Any]:
    conn.execute("TRUNCATE match CASCADE")
    return conn


def _failed(db: psycopg.Connection[Any], kind: str, demo: str | None) -> tuple[uuid.UUID, int]:
    """A match whose `kind` job died."""
    row = db.execute(
        "INSERT INTO match (mode, played_at, status, demo_key, error) "
        "VALUES ('premier', now(), 'failed', %s, 'x') "
        "RETURNING id",
        (demo,),
    ).fetchone()
    assert row is not None
    match_id = uuid.UUID(str(row[0]))
    job = queue.enqueue(db, kind, {"match_id": str(match_id), "url": "https://x/a.dem.bz2"})
    db.execute(
        "UPDATE job SET status = 'dead', attempts = 5, finished_at = now() WHERE id = %s", (job,)
    )
    return match_id, job


def _state(db: psycopg.Connection[Any], match_id: uuid.UUID, job: int) -> tuple[Any, ...]:
    row = db.execute(
        "SELECT m.status::text, m.error, j.status::text, j.attempts FROM match m, job j "
        "WHERE m.id = %s AND j.id = %s",
        (match_id, job),
    ).fetchone()
    assert row is not None
    return tuple(row)


def test_failed_matches_go_back_in_the_queue(db: psycopg.Connection[Any]) -> None:
    parse = _failed(db, "parse", "demos/a.dem")
    download = _failed(db, "download", None)
    gone = _failed(db, "parse", "demos/b.dem")
    db.execute("UPDATE match SET demo_deleted_at = now() WHERE id = %s", (gone[0],))
    retried = retry_failed(db)
    assert (retried.queued, retried.without_demo) == (2, 1)
    assert _state(db, *parse) == ("parsing", None, "queued", 0)
    assert _state(db, *download) == ("downloading", None, "queued", 0)
    assert _state(db, *gone) == ("failed", "x", "dead", 5)
    assert retry_failed(db).queued == 0  # nothing failed any more
