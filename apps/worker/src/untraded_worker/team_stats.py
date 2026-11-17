# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The team metrics of the matches parsed before they existed: `untraded-worker
backfill-team-stats` (migration 0020).

It writes `team_metric_value` and nothing else: the player metrics, sessions and their ids, the
advice and the votes stay as they are (a `reanalyze --force` would give every session a new id).
The numbers come from the match's canonical Parquet tables, derived again as the parse job does.
It can be run again: it only visits the ready matches without a row of the current version of
`MARKER`, or with a team row of a version that is no longer current (after a new formula), and
replaces a visited match's team rows whole. A match with no round whose winner is
known has no team rows and is visited again each time, at no cost but its reading.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import psycopg

from untraded.derive import derive
from untraded.metrics import REGISTRY, Dataset
from untraded.parsing.schema import TABLES as CANONICAL
from untraded_worker import load
from untraded_worker.analysis import team_values
from untraded_worker.store import LocalStore

log = logging.getLogger("untraded.worker")

MARKER = "team.buy"
"""Every round has a buy type: a match without a row of this metric's current version has no team
rows of the current versions."""

TODO = """
SELECT m.id FROM match m
WHERE m.status = 'ready' AND m.parquet_prefix IS NOT NULL
  AND (NOT EXISTS (
          SELECT 1 FROM team_metric_value v
          WHERE v.match_id = m.id AND v.metric_id = %(marker)s AND v.version = %(version)s)
       -- A team metric of a version that is no longer the current one (a new formula).
       OR EXISTS (
          SELECT 1 FROM team_metric_value v
          JOIN metric_current c ON c.metric_id = v.metric_id AND c.version <> v.version
          WHERE v.match_id = m.id))
ORDER BY m.parsed_at
"""


def fill(conn: psycopg.Connection[Any], store: LocalStore, match_id: uuid.UUID) -> bool:
    """One match, in one transaction holding its row (an erasure or a reanalysis waits), its team
    rows replaced. Returns False when the match is no longer ready."""
    with conn.transaction():
        row = conn.execute(
            "SELECT parquet_prefix FROM match WHERE id = %s AND status = 'ready' FOR UPDATE",
            (match_id,),
        ).fetchone()
        if row is None or row[0] is None:
            return False
        stored = store.read_tables(str(row[0]))
        canonical = {name: stored[name] for name in CANONICAL}
        dataset = Dataset.from_matches([{**canonical, **derive(canonical).tables()}])
        values = team_values(dataset)
        load.register_metrics(conn)
        conn.execute("DELETE FROM team_metric_value WHERE match_id = %s", (match_id,))
        load.copy_team_values(conn, match_id, values)
    return True


def backfill(conn: psycopg.Connection[Any], store: LocalStore) -> int:
    """Fills the team metrics of the ready matches that miss them; returns how many matches were
    filled. A match that fails is logged and skipped."""
    done = 0
    rows = conn.execute(TODO, {"marker": MARKER, "version": REGISTRY[MARKER].version}).fetchall()
    for (match_id,) in rows:
        try:
            if not fill(conn, store, match_id):
                continue
        except Exception:  # one broken match must not stop the others
            log.exception("team metrics of match %s failed", match_id)
            continue
        log.info("match %s: team metrics written", match_id)
        done += 1
    return done
