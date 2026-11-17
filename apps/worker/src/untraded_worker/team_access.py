# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Which teams see a player's matches, again (`refresh_team_access` job, payload
`{"steam_id": "<steam id>"}`).

`workspace_match` is computed when a match is analysed (`load.refresh_access`). A team's roster,
its members, a player's sharing choice or consent can change afterwards: the database functions
behind those changes (migration 0016) queue this job for the player concerned, and it recomputes
every match of theirs. An erasure does the same within its own transaction (`erase`).

Matches are locked in the order of their ids, as one statement, before any is recomputed: the
analysis holds a match's row while it writes, so two jobs never wait on each other in a circle.
`untraded-worker refresh-access` recomputes every match, one transaction each.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from typing import Any

import psycopg

from untraded_worker import load
from untraded_worker.queue import Job

log = logging.getLogger("untraded.worker")


def refresh_matches(conn: psycopg.Connection[Any], match_ids: Sequence[uuid.UUID]) -> int:
    """Locks the matches in a stable order, then recomputes who sees each; returns how many
    still exist. Runs in the caller's transaction."""
    locked = conn.execute(
        "SELECT id FROM match WHERE id = ANY(%s) ORDER BY id FOR UPDATE", (list(match_ids),)
    ).fetchall()
    for (match_id,) in locked:
        load.refresh_access(conn, match_id)
    return len(locked)


def player_matches(conn: psycopg.Connection[Any], steam_id: int) -> list[uuid.UUID]:
    rows = conn.execute(
        "SELECT match_id FROM match_player WHERE steam_id = %s ORDER BY match_id", (steam_id,)
    ).fetchall()
    return [row[0] for row in rows]


def refresh_player(conn: psycopg.Connection[Any], steam_id: int) -> int:
    """Recomputes who sees each match of the player; returns how many."""
    return refresh_matches(conn, player_matches(conn, steam_id))


def refresh_team_access(conn: psycopg.Connection[Any], job: Job) -> None:
    done = refresh_player(conn, int(job.payload["steam_id"]))
    log.info("access to %s match(es) recomputed", done)


def refresh_all(conn: psycopg.Connection[Any]) -> int:
    """Every match, one transaction each (`conn` in autocommit); returns how many."""
    done = 0
    for (match_id,) in conn.execute("SELECT id FROM match ORDER BY id").fetchall():
        with conn.transaction():
            done += refresh_matches(conn, [match_id])
    return done
