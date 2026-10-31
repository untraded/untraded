# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import datetime as dt
from typing import Any

import psycopg
import pytest

from untraded_worker import queue


def test_backoff_doubles_up_to_one_hour() -> None:
    delays = [queue.backoff(n) for n in range(1, 10)]
    assert delays[:4] == [dt.timedelta(seconds=s) for s in (30, 60, 120, 240)]
    assert delays[-1] == dt.timedelta(hours=1)
    assert delays == sorted(delays)
    assert queue.backoff(1000) == dt.timedelta(hours=1)  # no overflow


def _status(conn: psycopg.Connection[Any], job_id: int) -> tuple[Any, ...]:
    row = conn.execute(
        "SELECT status::text, attempts, locked_by, last_error, run_at > now(), finished_at "
        "FROM job WHERE id = %s",
        (job_id,),
    ).fetchone()
    assert row is not None
    return tuple(row)


@pytest.mark.db
def test_claim_takes_the_highest_priority_ready_job(conn: psycopg.Connection[Any]) -> None:
    low = queue.enqueue(conn, "parse", {"match": 1})
    high = queue.enqueue(conn, "parse", {"match": 2}, priority=5)
    queue.enqueue(conn, "download")
    job = queue.claim(conn, ["parse"], "w1")
    assert job is not None
    assert (job.id, job.kind, job.payload, job.attempts) == (high, "parse", {"match": 2}, 1)
    assert _status(conn, high)[:3] == ("running", 1, "w1")
    second = queue.claim(conn, ["parse"], "w1")
    assert second is not None
    assert second.id == low
    assert queue.claim(conn, ["parse"], "w1") is None


@pytest.mark.db
def test_a_locked_job_is_skipped_by_another_worker(
    conn: psycopg.Connection[Any], conninfo: str
) -> None:
    first = queue.enqueue(conn, "parse")
    second = queue.enqueue(conn, "parse")
    with psycopg.connect(conninfo) as other:  # an open transaction keeps its row lock
        taken = queue.claim(other, ["parse"], "w1")
        assert taken is not None
        assert taken.id == first
        mine = queue.claim(conn, ["parse"], "w2")
        assert mine is not None
        assert mine.id == second
        assert queue.claim(conn, ["parse"], "w2") is None
        other.rollback()


@pytest.mark.db
def test_complete(conn: psycopg.Connection[Any]) -> None:
    queue.enqueue(conn, "parse")
    job = queue.claim(conn, ["parse"], "w1")
    assert job is not None
    queue.complete(conn, job)
    status, _, locked_by, error, _, finished = _status(conn, job.id)
    assert (status, locked_by, error) == ("done", None, None)
    assert finished is not None


@pytest.mark.db
def test_a_failed_job_comes_back_later_then_dies(conn: psycopg.Connection[Any]) -> None:
    job_id = queue.enqueue(conn, "parse", max_attempts=2)
    job = queue.claim(conn, ["parse"], "w1")
    assert job is not None
    assert not queue.fail(conn, job, "boom")
    assert _status(conn, job_id) == ("queued", 1, None, "boom", True, None)
    assert queue.claim(conn, ["parse"], "w1") is None  # not before its backoff

    conn.execute("UPDATE job SET run_at = now() WHERE id = %s", (job_id,))
    job = queue.claim(conn, ["parse"], "w1")
    assert job is not None
    assert job.attempts == 2
    assert queue.fail(conn, job, "boom again")
    status, attempts, _, error, _, finished = _status(conn, job_id)
    assert (status, attempts, error) == ("dead", 2, "boom again")
    assert finished is not None


@pytest.mark.db
def test_abandoned_jobs_are_found(conn: psycopg.Connection[Any]) -> None:
    old = queue.enqueue(conn, "parse")
    recent = queue.enqueue(conn, "parse")
    for _ in range(2):
        assert queue.claim(conn, ["parse"], "w1") is not None
    conn.execute("UPDATE job SET locked_at = now() - interval '1 hour' WHERE id = %s", (old,))
    with conn.transaction():
        assert [j.id for j in queue.abandoned(conn)] == [old]  # gone for 30 minutes
        assert [j.id for j in queue.abandoned(conn, worker="w1")] == [old, recent]
        assert queue.abandoned(conn, worker="w2") == []
