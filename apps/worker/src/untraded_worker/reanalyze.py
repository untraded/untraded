# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Analyses the matches parsed before again, from their Parquet tables: `untraded-worker
reanalyze`. After an update that adds metrics or new versions of them (the Untraded Rating), the
matches parsed before hold none of them; this recomputes the derived tables, the metrics and the
round replays, reloads the SQL rows, and queues the players' sessions again. The demo is not
needed: the canonical tables are the long-term record (ADR 0009). Each match queues the sessions
of its players, so a session of N matches is recomputed N times: the result is the same."""

from __future__ import annotations

import logging
import uuid
from typing import Any

import psycopg

from untraded.metrics import REGISTRY
from untraded.parsing.schema import TABLES as CANONICAL
from untraded_worker import load, replays, sessions
from untraded_worker.analysis import analyze
from untraded_worker.store import LocalStore

log = logging.getLogger("untraded.worker")

MARKER = "rating.untraded"
"""A match without the current version of this metric is analysed again (all with `force`)."""


def reanalyze(conn: psycopg.Connection[Any], store: LocalStore, match_id: uuid.UUID) -> bool:
    """One match, in one transaction holding its row: its tables, metrics, replays and sessions.
    The lock keeps an erasure or a merge from running in between (an erased match's files must
    not come back). Returns False when the match is no longer ready."""
    with conn.transaction():
        row = conn.execute(
            "SELECT parquet_prefix FROM match WHERE id = %s AND status = 'ready' FOR UPDATE",
            (match_id,),
        ).fetchone()
        if row is None or row[0] is None:
            return False
        prefix = str(row[0])
        stored = store.read_tables(prefix)
        analysis = analyze({name: stored[name] for name in CANONICAL})
        store.write_tables(prefix, analysis.tables)
        load.load_match(conn, match_id, analysis)
        load.refresh_access(conn, match_id)
        sessions.queue_sessions(conn, match_id)
        try:
            replays.write_replays(store, prefix, analysis.tables)
        except Exception:  # the viewer's files are derived: the analysis stands without them
            log.exception("replays of match %s failed; `untraded-worker replays` retries", match_id)
    return True


def backfill(conn: psycopg.Connection[Any], store: LocalStore, *, force: bool = False) -> int:
    """Analyses again the ready matches that miss the current version of `MARKER` (all of them
    with `force`); returns how many. A match that fails is logged and skipped."""
    done = 0
    rows = conn.execute(
        """
        SELECT m.id FROM match m
        WHERE m.status = 'ready' AND m.parquet_prefix IS NOT NULL
          AND (%(force)s OR NOT EXISTS (
              SELECT 1 FROM metric_value v
              WHERE v.match_id = m.id AND v.metric_id = %(marker)s AND v.version = %(version)s))
        ORDER BY m.parsed_at
        """,
        {"force": force, "marker": MARKER, "version": REGISTRY[MARKER].version},
    ).fetchall()
    for (match_id,) in rows:
        try:
            if not reanalyze(conn, store, match_id):
                continue
        except Exception:  # one broken match must not stop the others
            log.exception("analysis of match %s failed", match_id)
            continue
        log.info("match %s analysed again", match_id)
        done += 1
    return done
