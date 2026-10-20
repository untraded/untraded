# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The job handlers, by kind. `session` (play sessions and their report) is in `sessions`.

`download` (payload `{"match_id": "<uuid>", "url": "<demo URL>"}`): fetches the match's demo
(Valve serves `.dem.bz2`), checks it is a CS2 demo, stores it as received under
`demos/{sha256}{suffix}` (sha256 of the decompressed demo, ADR 0009), and queues its `parse`.
A demo the server no longer has (404, 410) makes the match `unavailable`.

`parse` (payload `{"match_id": "<uuid>"}`): the match's raw demo is in the store (`demo_key`).
The worker parses it, derives the round model, computes the metrics, writes the Parquet tables
under `matches/{id}/`, loads the SQL tables, refreshes who sees the match, and marks it `ready`.
A demo already known by its sha256 (the same match brought by two players, ADR 0009) is not
stored twice: the new match row is merged into the existing one. A demo of a mode we do not
analyse (a Competitive or Wingman match in Valve's share-code chain) makes the match
`unavailable` and its demo is deleted.
"""

from __future__ import annotations

import datetime as dt
import urllib.parse
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import psycopg

from untraded.demofile import CorruptDemoError, NotADemoError, demo_suffix, digest
from untraded.parsing import CanonicalMatch, UnsupportedModeError, parse_demo
from untraded_worker import load, queue, sessions
from untraded_worker.analysis import analyze
from untraded_worker.download import DemoGone, fetch
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
        try:
            canonical = self.parse(
                self.store.path(demo_key),
                source=source[0] if source else "upload",
                mode=mode,
                played_at=played_at.date() if isinstance(played_at, dt.datetime) else None,
            )
        except UnsupportedModeError as error:
            self._out_of_scope(conn, match_id, demo_key, str(error))
            return

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
        sessions.queue_sessions(conn, match_id)

    def _out_of_scope(
        self, conn: psycopg.Connection[Any], match_id: uuid.UUID, demo_key: str, reason: str
    ) -> None:
        """A mode we do not analyse (e.g. a Competitive match in Valve's share-code chain): the
        match stays, so the collector does not bring it again, but its demo goes."""
        conn.execute(
            "UPDATE match SET status = 'unavailable', error = %s, demo_deleted_at = now() "
            "WHERE id = %s",
            (reason, match_id),
        )
        shared = conn.execute(
            "SELECT 1 FROM match WHERE demo_key = %s AND id <> %s AND demo_deleted_at IS NULL",
            (demo_key, match_id),
        ).fetchone()
        if shared is None:
            self.store.delete(demo_key)  # last: not transactional

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
        sessions.queue_sessions(conn, known)
        if duplicate_demo != known_demo:
            # Last: a file deletion is not transactional, and nothing after it can fail but
            # the commit.
            self.store.delete(duplicate_demo)


@dataclass(frozen=True)
class DownloadJob:
    store: LocalStore
    fetch: Callable[[str, Path], object] = field(default=fetch)
    """`download.fetch`; tests replace it."""

    def __call__(self, conn: psycopg.Connection[Any], job: Job) -> None:
        # No row lock here: a download can take 20 minutes on Valve's throttled servers.
        match_id = uuid.UUID(str(job.payload["match_id"]))
        url = str(job.payload["url"])
        row = conn.execute("SELECT demo_key FROM match WHERE id = %s", (match_id,)).fetchone()
        if row is None or row[0] is not None:
            return  # deleted meanwhile, or already downloaded
        name = Path(urllib.parse.urlsplit(url).path).name
        try:
            suffix = demo_suffix(Path(name))
        except NotADemoError as error:
            raise JobError(f"{url}: {error}") from error
        incoming = self.store.path(f"incoming/{match_id}{suffix}")
        try:
            self.fetch(url, incoming)
        except DemoGone as gone:
            conn.execute(
                "UPDATE match SET status = 'unavailable', error = %s WHERE id = %s",
                (f"demo gone from the server ({gone})", match_id),
            )
            return
        try:
            found = digest(incoming)
        except (NotADemoError, CorruptDemoError):
            incoming.unlink()  # download it again next time
            raise
        key = f"demos/{found.sha256}{suffix}"
        if self.store.exists(key):
            incoming.unlink()  # the same demo, brought by another match: merged at parse
        else:
            self.store.move_in(key, incoming)
        conn.execute(
            "UPDATE match SET demo_key = %s, status = 'parsing', error = NULL WHERE id = %s",
            (key, match_id),
        )
        queue.enqueue(conn, "parse", {"match_id": str(match_id)})


def match_failed(conn: psycopg.Connection[Any], job: Job, error: str) -> None:
    conn.execute(
        "UPDATE match SET status = 'failed', error = %s WHERE id = %s",
        (error[:4000], uuid.UUID(str(job.payload["match_id"]))),
    )


def handlers(store: LocalStore) -> dict[str, Handler]:
    return {
        "download": DownloadJob(store),
        "parse": ParseJob(store),
        "session": sessions.SessionJob(store),
    }


ON_DEAD: dict[str, DeadHandler] = {"download": match_failed, "parse": match_failed}
