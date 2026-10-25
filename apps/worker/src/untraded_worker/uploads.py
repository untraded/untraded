# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""`ingest_upload` (payload `{"match_id": "<uuid>", "file": "<name>"}`): a demo a player sent
from the site (`POST /uploads`), which the API wrote to the uploads directory.

The worker checks it is a CS2 demo that decompresses to a sensible size, recognises a demo from
Valve's servers (Premier whatever the player chose; `parse` then refuses Competitive and
Wingman), and moves it to the store under `demos/{sha256}{suffix}` before queueing its `parse`,
as `download` does. A file that is not a usable demo makes the match `unavailable`, and the
upload `rejected` with a code the site shows (`not_a_demo`, `corrupt`, `too_large`).

After the parse, an upload whose player is not in the match is rejected too (`not_a_player`,
in `jobs.ParseJob`): Untraded analyses the matches of its players only.
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg

from untraded.demofile import (
    CorruptDemoError,
    DemoTooLargeError,
    NotADemoError,
    demo_suffix,
    digest,
)
from untraded.parsing.header import read_header
from untraded_worker import queue
from untraded_worker.queue import Job
from untraded_worker.store import LocalStore

log = logging.getLogger("untraded.worker")

VALVE_SERVER = "Valve Counter-Strike"
"""How the header of a matchmaking demo names its server (`Valve Counter-Strike 2 eu_west
Server (...)`); FACEIT and ESEA servers say anything, often just `Counter-Strike 2`."""


def max_demo_bytes() -> int:
    """`UNTRADED_UPLOAD_MAX_DEMO_GB`: the largest decompressed demo accepted (a Premier or FACEIT
    match: about 1 GB)."""
    return int(float(os.environ.get("UNTRADED_UPLOAD_MAX_DEMO_GB", "1.5")) * 1e9)


def reject(conn: psycopg.Connection[Any], match_id: uuid.UUID, reason: str) -> None:
    """The upload is refused: the match stays, as the record of it, without a demo."""
    conn.execute(
        "UPDATE match SET status = 'unavailable', error = %s WHERE id = %s", (reason, match_id)
    )
    conn.execute(
        "UPDATE match_source SET rejected = %s WHERE match_id = %s AND kind = 'upload' "
        "AND rejected IS NULL",
        (reason, match_id),
    )


@dataclass(frozen=True)
class IngestUploadJob:
    store: LocalStore
    uploads: Path
    max_bytes: int = 1_500_000_000

    def file(self, job: Job) -> Path:
        name = str(job.payload["file"])
        if Path(name).name != name or name.startswith("."):
            raise ValueError(f"invalid upload file name: {name!r}")
        return self.uploads / name

    def __call__(self, conn: psycopg.Connection[Any], job: Job) -> None:
        match_id = uuid.UUID(str(job.payload["match_id"]))
        path = self.file(job)
        row = conn.execute(
            "SELECT demo_key FROM match WHERE id = %s FOR UPDATE", (match_id,)
        ).fetchone()
        if row is None or row[0] is not None:
            path.unlink(missing_ok=True)  # erased meanwhile, or already done
            return
        if not path.exists():
            raise FileNotFoundError(f"upload {path.name} is missing")
        suffix = demo_suffix(path)
        try:
            found = digest(path, max_size=self.max_bytes)
        except (NotADemoError, CorruptDemoError, DemoTooLargeError) as error:
            reason = {
                NotADemoError: "not_a_demo",
                CorruptDemoError: "corrupt",
                DemoTooLargeError: "too_large",
            }[type(error)]
            log.info("upload %s refused: %s", match_id, error)
            reject(conn, match_id, reason)
            path.unlink()
            return
        try:
            server = read_header(path).server_name
        except Exception:  # the parse will tell; the player's mode stands meanwhile
            log.exception("header of upload %s unreadable", match_id)
            server = ""
        if server.startswith(VALVE_SERVER):
            conn.execute("UPDATE match SET mode = 'premier' WHERE id = %s", (match_id,))
        key = f"demos/{found.sha256}{suffix}"
        if not self.store.exists(key):  # else the same demo is known: merged at parse
            self.store.put_file(key, path)  # a copy: the uploads are another volume
        conn.execute(
            "UPDATE match SET demo_key = %s, status = 'parsing', error = NULL WHERE id = %s",
            (key, match_id),
        )
        queue.enqueue(conn, "parse", {"match_id": str(match_id)})
        path.unlink()  # last: a file deletion is not transactional


@dataclass(frozen=True)
class UploadFailed:
    """When `ingest_upload` gives up: the match is failed, and the file goes."""

    uploads: Path

    def __call__(self, conn: psycopg.Connection[Any], job: Job, error: str) -> None:
        conn.execute(
            "UPDATE match SET status = 'failed', error = %s WHERE id = %s",
            (error[:4000], uuid.UUID(str(job.payload["match_id"]))),
        )
        name = Path(str(job.payload.get("file", ""))).name
        if name:
            (self.uploads / name).unlink(missing_ok=True)
