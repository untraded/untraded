# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from typing import Any

import psycopg
import pytest

from untraded_worker import queue
from untraded_worker.queue import Job
from untraded_worker.runner import Worker


class Panic(BaseException):
    """Like a demoparser2 PanicException: not an Exception."""


def _record(conn: psycopg.Connection[Any], job: Job) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS worker_test (job bigint)")
    conn.execute("INSERT INTO worker_test VALUES (%s)", (job.id,))
    if job.payload.get("panic"):
        raise Panic("parser panicked")


@pytest.fixture
def worker(conn: psycopg.Connection[Any], conninfo: str) -> Worker:
    conn.execute("DROP TABLE IF EXISTS worker_test")
    return Worker(conninfo, {"parse": _record}, name="test", poll_seconds=0.1)


def _recorded(conn: psycopg.Connection[Any]) -> list[int]:
    exists = conn.execute("SELECT to_regclass('worker_test') IS NOT NULL").fetchone()
    if not exists or not exists[0]:
        return []
    return [row[0] for row in conn.execute("SELECT job FROM worker_test ORDER BY job")]


@pytest.mark.db
def test_step_commits_the_handler_writes_with_the_completion(
    conn: psycopg.Connection[Any], worker: Worker
) -> None:
    job_id = queue.enqueue(conn, "parse")
    assert worker.step(conn)
    assert _recorded(conn) == [job_id]
    row = conn.execute("SELECT status::text FROM job WHERE id = %s", (job_id,)).fetchone()
    assert row == ("done",)
    assert not worker.step(conn)


@pytest.mark.db
def test_a_panicking_handler_is_rolled_back_and_recorded(
    conn: psycopg.Connection[Any], worker: Worker
) -> None:
    job_id = queue.enqueue(conn, "parse", {"panic": True})
    assert worker.step(conn)
    assert _recorded(conn) == []
    row = conn.execute(
        "SELECT status::text, attempts, last_error FROM job WHERE id = %s", (job_id,)
    ).fetchone()
    assert row is not None
    assert row[:2] == ("queued", 1)
    assert row[2].startswith("Panic: parser panicked")


@pytest.mark.db
def test_run_once_drains_the_queue(conn: psycopg.Connection[Any], worker: Worker) -> None:
    ids = [queue.enqueue(conn, "parse") for _ in range(3)]
    queue.enqueue(conn, "download")  # no handler here: left alone
    assert worker.run(once=True) == 3
    assert _recorded(conn) == ids
    left = conn.execute("SELECT kind, status::text FROM job WHERE kind = 'download'").fetchall()
    assert left == [("download", "queued")]
