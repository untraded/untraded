# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The `ingest_upload` job against PostgreSQL: small demos written as the API writes them."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Any

import psycopg
import pytest
from compression import zstd

from untraded.demofile import DEMO_MAGIC
from untraded.parsing.header import DemoHeader
from untraded_worker import queue, uploads
from untraded_worker.jobs import dead_handlers
from untraded_worker.runner import Worker
from untraded_worker.store import LocalStore
from untraded_worker.uploads import IngestUploadJob

pytestmark = pytest.mark.db
PLAIN = DEMO_MAGIC + b"a FACEIT match" * 1000
SHA = hashlib.sha256(PLAIN).hexdigest()


@pytest.fixture
def db(conn: psycopg.Connection[Any]) -> psycopg.Connection[Any]:
    conn.execute("TRUNCATE match, app_user, player CASCADE")
    return conn


def _upload(db: psycopg.Connection[Any], folder: Path, content: bytes) -> queue.Job:
    """What `add_my_upload` records, and the file the API wrote."""
    user = db.execute(
        "INSERT INTO app_user (steam_id, display_name) VALUES (1, 'u') "
        "ON CONFLICT (steam_id) DO UPDATE SET display_name = 'u' RETURNING id"
    ).fetchone()
    assert user is not None
    source = db.execute(
        "INSERT INTO ingest_source (user_id, kind) VALUES (%s, 'upload') RETURNING id", (user[0],)
    ).fetchone()
    assert source is not None
    match_id = uuid.uuid4()
    db.execute("INSERT INTO match (id, mode) VALUES (%s, 'faceit')", (match_id,))
    db.execute(
        "INSERT INTO match_source (match_id, kind, external_id, source_id) "
        "VALUES (%s, 'upload', %s, %s)",
        (match_id, str(match_id), source[0]),
    )
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{match_id}.dem.zst").write_bytes(content)
    return queue.Job(
        1, "ingest_upload", {"match_id": str(match_id), "file": f"{match_id}.dem.zst"}, 1, 3
    )


def _state(db: psycopg.Connection[Any], job: queue.Job) -> tuple[Any, ...]:
    row = db.execute(
        "SELECT m.mode::text, m.status::text, m.demo_key, ms.rejected FROM match m "
        "JOIN match_source ms ON ms.match_id = m.id WHERE m.id = %s",
        (job.payload["match_id"],),
    ).fetchone()
    assert row is not None
    return tuple(row)


def test_a_demo_goes_to_the_store_and_is_parsed_next(
    db: psycopg.Connection[Any], tmp_path: Path
) -> None:
    store, folder = LocalStore(tmp_path / "store"), tmp_path / "uploads"
    job = _upload(db, folder, zstd.compress(PLAIN))
    IngestUploadJob(store, folder)(db, job)
    key = f"demos/{SHA}.dem.zst"
    assert _state(db, job) == ("faceit", "parsing", key, None)
    assert zstd.decompress(store.path(key).read_bytes()) == PLAIN
    assert list(folder.iterdir()) == []
    parse = queue.claim(db, ["parse"], "test")
    assert parse is not None
    assert parse.payload == {"match_id": job.payload["match_id"]}


def test_a_demo_from_valve_servers_is_premier(
    db: psycopg.Connection[Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    valve = DemoHeader("de_mirage", "14190", "Valve Counter-Strike 2 eu_west Server (srcds1)")
    monkeypatch.setattr(uploads, "read_header", lambda _: valve)
    job = _upload(db, tmp_path / "uploads", zstd.compress(PLAIN))
    IngestUploadJob(LocalStore(tmp_path / "store"), tmp_path / "uploads")(db, job)
    assert _state(db, job)[:2] == ("premier", "parsing")


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        (zstd.compress(b"<html>" * 100), "not_a_demo"),
        (zstd.compress(PLAIN)[:100], "corrupt"),
        (zstd.compress(PLAIN * 3), "too_large"),
    ],
)
def test_a_file_that_is_not_a_usable_demo_is_refused(
    db: psycopg.Connection[Any], tmp_path: Path, content: bytes, reason: str
) -> None:
    store, folder = LocalStore(tmp_path / "store"), tmp_path / "uploads"
    job = _upload(db, folder, content)
    IngestUploadJob(store, folder, max_bytes=len(PLAIN) * 2)(db, job)
    assert _state(db, job) == ("faceit", "unavailable", None, reason)
    assert list(folder.iterdir()) == []
    assert queue.claim(db, ["parse"], "test") is None


def test_a_dead_upload_fails_its_match_and_its_file_goes(
    db: psycopg.Connection[Any], tmp_path: Path
) -> None:
    folder = tmp_path / "uploads"
    job = _upload(db, folder, zstd.compress(PLAIN))
    queue.enqueue(db, "ingest_upload", job.payload, max_attempts=1)

    def broken(conn: psycopg.Connection[Any], job: queue.Job) -> None:
        raise OSError("disk error")

    worker = Worker("", {"ingest_upload": broken}, on_dead=dead_handlers(folder))
    assert worker.step(db)
    assert _state(db, job)[1] == "failed"
    assert list(folder.iterdir()) == []


def test_a_file_name_cannot_leave_the_uploads(db: psycopg.Connection[Any], tmp_path: Path) -> None:
    job = _upload(db, tmp_path / "uploads", zstd.compress(PLAIN))
    escape = queue.Job(1, "ingest_upload", {**job.payload, "file": "../store/x.dem"}, 1, 3)
    with pytest.raises(ValueError, match="invalid upload file name"):
        IngestUploadJob(LocalStore(tmp_path / "store"), tmp_path / "uploads")(db, escape)
