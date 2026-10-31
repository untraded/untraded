# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Raw demo retention (ADR 0009): Parquet is the long-term record, raw demos may go.

`UNTRADED_DEMO_RETENTION_DAYS` sets how long a raw demo is kept after its match is parsed (or
failed): unset keeps them (self-hosting default), 0 deletes them at the next sweep after the
parse (the beta server), 30 is the hosted default. The worker sweeps when idle, every 10 minutes.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
from dataclasses import dataclass
from typing import Any

import psycopg

from untraded_worker.store import LocalStore

VARIABLE = "UNTRADED_DEMO_RETENTION_DAYS"
log = logging.getLogger("untraded.worker")


def configured() -> dt.timedelta | None:
    """The retention from the environment; None keeps raw demos."""
    days = os.environ.get(VARIABLE, "").strip()
    if not days:
        return None
    value = float(days)
    if value < 0:
        raise ValueError(f"{VARIABLE} must be >= 0, got {days}")
    return dt.timedelta(days=value)


def sweep(conn: psycopg.Connection[Any], store: LocalStore, keep: dt.timedelta) -> int:
    """Deletes the raw demos past `keep`; returns how many. A demo still needed by another
    match (not parsed yet, or kept longer) stays."""
    with conn.transaction():
        rows = conn.execute(
            """
            SELECT m.id, m.demo_key FROM match m
            WHERE m.demo_key IS NOT NULL AND m.demo_deleted_at IS NULL
              AND m.status IN ('ready', 'failed')
              AND coalesce(m.parsed_at, m.created_at) <= now() - %(keep)s
              AND NOT EXISTS (
                  SELECT 1 FROM match o
                  WHERE o.demo_key = m.demo_key AND o.id <> m.id AND o.demo_deleted_at IS NULL
                    AND (o.status NOT IN ('ready', 'failed')
                         OR coalesce(o.parsed_at, o.created_at) > now() - %(keep)s)
              )
            FOR UPDATE OF m SKIP LOCKED
            """,
            {"keep": keep},
        ).fetchall()
        for match_id, _ in rows:
            conn.execute("UPDATE match SET demo_deleted_at = now() WHERE id = %s", (match_id,))
    # After the commit: a file deletion cannot be rolled back. A missing file is fine.
    deleted = sum(store.delete(key) for key in {key for _, key in rows})
    if deleted:
        log.info("retention: %s raw demo(s) deleted", deleted)
    return deleted


def purge_sessions(conn: psycopg.Connection[Any]) -> int:
    """Deletes the expired sign-in sessions (the public demo opens one per visit): returns how
    many."""
    return conn.execute("DELETE FROM auth_session WHERE expires_at < now()").rowcount


@dataclass(frozen=True)
class Sweep:
    """`sweep` as a periodic task of the worker."""

    store: LocalStore
    keep: dt.timedelta

    def __call__(self, conn: psycopg.Connection[Any]) -> int:
        return sweep(conn, self.store, self.keep)
