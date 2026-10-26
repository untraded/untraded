# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The `swing` table (`untraded.derive.swing_table`) of matches derived before it existed, or
again after a new win-probability model (`--force`): `untraded-worker swings`. The parse job
writes it with the other derived tables."""

from __future__ import annotations

import logging
from typing import Any

import psycopg

from untraded.derive import swing_table
from untraded_worker.store import LocalStore

log = logging.getLogger("untraded.worker")


def backfill(conn: psycopg.Connection[Any], store: LocalStore, *, force: bool = False) -> int:
    """Writes the `swing` table of the ready matches that have none (all of them with `force`);
    returns how many matches got one. A match that fails is logged and skipped."""
    done = 0
    rows = conn.execute(
        "SELECT id, parquet_prefix FROM match WHERE status = 'ready' "
        "AND parquet_prefix IS NOT NULL ORDER BY parsed_at"
    ).fetchall()
    for match_id, prefix in rows:
        if not force and store.exists(f"{prefix}/swing.parquet"):
            continue
        try:
            table = swing_table(store.read_tables(prefix))
        except Exception:  # one broken match must not stop the others
            log.exception("swings of match %s failed", match_id)
            continue
        store.write_tables(prefix, {"swing": table})
        log.info("match %s: %d swing credit(s)", match_id, table.height)
        done += 1
    return done
