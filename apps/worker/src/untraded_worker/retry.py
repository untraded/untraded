# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""`untraded-worker retry-failed`: puts the failed matches back in the queue, after a fix.

A match is `failed` when its download or its parse died (no attempt left). Once the cause is
fixed and deployed, its last dead job goes back in the queue with its attempts reset, and the
match back to `downloading` or `parsing`. A parse needs its raw demo: once the retention has
deleted it (`UNTRADED_DEMO_RETENTION_DAYS`), the match stays failed, and the player sends the
demo again. An upload that died before its parse has no demo either (its file goes with it).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import psycopg

log = logging.getLogger("untraded.worker")

RETRIED = {"download": "downloading", "parse": "parsing"}
"""The job kinds a failed match can be retried from, and the match's status meanwhile."""


@dataclass(frozen=True)
class Retried:
    queued: int
    """Matches put back in the queue."""
    without_demo: int
    """Failed matches whose raw demo is gone: they stay failed."""


def retry_failed(conn: psycopg.Connection[Any]) -> Retried:
    """Retries every failed match from its last dead download or parse job."""
    queued = without_demo = 0
    with conn.transaction():
        rows = conn.execute(
            """
            SELECT j.id, j.kind, m.id,
                   m.demo_key IS NOT NULL AND m.demo_deleted_at IS NULL
            FROM match m
            JOIN LATERAL (
                SELECT id, kind, status FROM job
                WHERE kind = ANY(%s) AND payload ->> 'match_id' = m.id::text
                ORDER BY id DESC LIMIT 1
            ) j ON true
            WHERE m.status = 'failed' AND j.status = 'dead'
            FOR UPDATE OF m
            """,
            (list(RETRIED),),
        ).fetchall()
        for job_id, kind, match_id, has_demo in rows:
            if kind == "parse" and not has_demo:
                without_demo += 1
                continue
            conn.execute(
                "UPDATE job SET status = 'queued', attempts = 0, run_at = now(), "
                "finished_at = NULL, locked_by = NULL WHERE id = %s",
                (job_id,),
            )
            conn.execute(
                "UPDATE match SET status = %s, error = NULL WHERE id = %s",
                (RETRIED[kind], match_id),
            )
            queued += 1
    if without_demo:
        log.warning("%s failed match(es) have no raw demo left: they stay failed", without_demo)
    return Retried(queued, without_demo)
