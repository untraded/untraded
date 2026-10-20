# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The `download` job and raw demo retention, against PostgreSQL (no network: `fetch` writes
a small bz2 demo)."""

from __future__ import annotations

import bz2
import datetime as dt
import hashlib
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import psycopg
import pytest

from untraded.demofile import DEMO_MAGIC, CorruptDemoError, NotADemoError
from untraded_worker import queue, retention
from untraded_worker.download import DemoGone
from untraded_worker.jobs import DownloadJob
from untraded_worker.store import LocalStore

pytestmark = pytest.mark.db
URL = "http://replay123.valve.net/730/003712345678901234567_0123456789.dem.bz2"
PLAIN = DEMO_MAGIC + b"a match"
SHA = hashlib.sha256(PLAIN).hexdigest()


@dataclass
class FakeFetch:
    content: bytes | None = bz2.compress(PLAIN)
    """None: the server says the demo is gone."""
    calls: list[str] = field(default_factory=list)

    def __call__(self, url: str, target: Path) -> object:
        self.calls.append(url)
        if self.content is None:
            raise DemoGone(404)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.content)
        return None


@pytest.fixture
def db(conn: psycopg.Connection[Any]) -> psycopg.Connection[Any]:
    conn.execute("TRUNCATE match CASCADE")
    return conn


def _match(db: psycopg.Connection[Any]) -> uuid.UUID:
    row = db.execute("INSERT INTO match (mode) VALUES ('premier') RETURNING id").fetchone()
    assert row is not None
    return uuid.UUID(str(row[0]))


def _job(match_id: uuid.UUID, url: str = URL) -> queue.Job:
    return queue.Job(1, "download", {"match_id": str(match_id), "url": url}, 1, 5)


def _row(db: psycopg.Connection[Any], match_id: uuid.UUID) -> tuple[Any, ...]:
    row = db.execute(
        "SELECT status::text, demo_key, error FROM match WHERE id = %s", (match_id,)
    ).fetchone()
    assert row is not None
    return tuple(row)


def test_the_demo_is_stored_by_its_sha256_and_parsed_next(
    db: psycopg.Connection[Any], tmp_path: Path
) -> None:
    store = LocalStore(tmp_path)
    match_id = _match(db)
    DownloadJob(store, FakeFetch())(db, _job(match_id))
    key = f"demos/{SHA}.dem.bz2"
    assert _row(db, match_id) == ("parsing", key, None)
    assert bz2.decompress(store.path(key).read_bytes()) == PLAIN
    assert not list((tmp_path / "incoming").iterdir())
    job = queue.claim(db, ["parse"], "test")
    assert job is not None
    assert job.payload == {"match_id": str(match_id)}


def test_the_same_demo_twice_is_stored_once(db: psycopg.Connection[Any], tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    job = DownloadJob(store, FakeFetch())
    first, second = _match(db), _match(db)
    job(db, _job(first))
    job(db, _job(second))
    assert _row(db, first)[1] == _row(db, second)[1]
    assert len(list((tmp_path / "demos").iterdir())) == 1


def test_a_downloaded_match_is_not_fetched_again(
    db: psycopg.Connection[Any], tmp_path: Path
) -> None:
    fetch = FakeFetch()
    job = DownloadJob(LocalStore(tmp_path), fetch)
    match_id = _match(db)
    job(db, _job(match_id))
    job(db, _job(match_id))
    assert len(fetch.calls) == 1


def test_a_gone_demo_makes_the_match_unavailable(
    db: psycopg.Connection[Any], tmp_path: Path
) -> None:
    match_id = _match(db)
    DownloadJob(LocalStore(tmp_path), FakeFetch(content=None))(db, _job(match_id))
    status, key, error = _row(db, match_id)
    assert (status, key) == ("unavailable", None)
    assert "404" in error


def test_a_file_that_is_not_a_demo_is_dropped(db: psycopg.Connection[Any], tmp_path: Path) -> None:
    match_id = _match(db)
    for content in (b"<html>", bz2.compress(b"<html>")):  # not bz2 at all; bz2, not a demo
        with pytest.raises((CorruptDemoError, NotADemoError)):
            DownloadJob(LocalStore(tmp_path), FakeFetch(content=content))(db, _job(match_id))
        assert not list((tmp_path / "incoming").iterdir())


def _parsed(db: psycopg.Connection[Any], store: LocalStore, key: str, days_ago: float) -> uuid.UUID:
    match_id = _match(db)
    store.path(key).parent.mkdir(parents=True, exist_ok=True)
    store.path(key).write_bytes(b"demo")
    db.execute(
        "UPDATE match SET status = 'ready', demo_key = %s, parsed_at = now() - %s WHERE id = %s",
        (key, dt.timedelta(days=days_ago), match_id),
    )
    return match_id


def test_retention_deletes_old_raw_demos_only(db: psycopg.Connection[Any], tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    old = _parsed(db, store, "demos/old.dem.bz2", 40)
    recent = _parsed(db, store, "demos/recent.dem.bz2", 2)
    assert retention.sweep(db, store, dt.timedelta(days=30)) == 1
    assert not store.exists("demos/old.dem.bz2")
    assert store.exists("demos/recent.dem.bz2")
    deleted = dict(db.execute("SELECT id, demo_deleted_at IS NOT NULL FROM match").fetchall())
    assert deleted == {old: True, recent: False}
    assert retention.sweep(db, store, dt.timedelta(days=30)) == 0


def test_retention_keeps_a_demo_another_match_still_needs(
    db: psycopg.Connection[Any], tmp_path: Path
) -> None:
    store = LocalStore(tmp_path)
    _parsed(db, store, "demos/shared.dem.bz2", 40)
    waiting = _match(db)
    db.execute(
        "UPDATE match SET status = 'parsing', demo_key = 'demos/shared.dem.bz2' WHERE id = %s",
        (waiting,),
    )
    assert retention.sweep(db, store, dt.timedelta(0)) == 0
    assert store.exists("demos/shared.dem.bz2")


def test_slow_kinds_are_not_requeued_early(conn: psycopg.Connection[Any]) -> None:
    download = queue.enqueue(conn, "download")
    parse = queue.enqueue(conn, "parse")
    for _ in range(2):
        assert queue.claim(conn, ["download", "parse"], "w1") is not None
    conn.execute("UPDATE job SET locked_at = now() - interval '1 hour'")
    assert queue.requeue_stale(conn) == 1
    status = dict(conn.execute("SELECT id, status::text FROM job").fetchall())
    assert status == {download: "running", parse: "queued"}
