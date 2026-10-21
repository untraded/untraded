# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Erases a player who asked for it, or whom an admin removed (`erase_player` job).

Afterwards the player is what any non-registered player of a match is:
- their account goes with everything tied to it: sources and their encrypted codes, consents,
  sign-in sessions, votes, invitation and personal workspace;
- their play sessions, advice and aggregates go too;
- the matches no other user played in are deleted whole: rows, Parquet and raw demo;
- the matches other users played in stay, since they are those users' matches too. The player
  remains one of the ten players there, never shown outside the match, and is left out of the
  level references from now on (`benchmark_opt_out`).

The research corpus follows at its next copy: without their consent, their demos leave it,
unless another consenting player is in the match. Database dumps keep them until they expire
(4 weeks at most).

The API marks the account deleted when the erasure is asked: they can no longer sign in, and
the collector stops following them, before this job runs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import psycopg

from untraded_worker.queue import Job
from untraded_worker.store import LocalStore

log = logging.getLogger("untraded.worker")

OWN_MATCHES = """
SELECT m.id, m.demo_key, m.parquet_prefix
FROM match m
JOIN match_player mp ON mp.match_id = m.id AND mp.steam_id = %(steam)s
WHERE NOT EXISTS (
    SELECT 1 FROM match_player o
    JOIN app_user u ON u.steam_id = o.steam_id AND u.deleted_at IS NULL
    WHERE o.match_id = m.id AND o.steam_id <> %(steam)s
)
"""
"""The player's matches that no other (live) user played in."""


class EraseError(ValueError):
    """The player cannot be erased as is."""


@dataclass(frozen=True)
class Erased:
    matches: int
    """Matches deleted whole."""
    files: int
    """Parquet directories and raw demos deleted."""


def erase_player(conn: psycopg.Connection[Any], store: LocalStore, steam_id: int) -> Erased:
    """Erases the player in one transaction, then their files. Running it again is harmless."""
    with conn.transaction():
        user = conn.execute("SELECT id FROM app_user WHERE steam_id = %s", (steam_id,)).fetchone()
        if user is not None:
            others = conn.execute(
                "SELECT count(*) FROM workspace WHERE created_by = %s AND kind <> 'personal'",
                (user[0],),
            ).fetchone()
            if others and others[0]:
                raise EraseError("the player created a team workspace: hand it over first")
        own = conn.execute(OWN_MATCHES, {"steam": steam_id}).fetchall()
        conn.execute("DELETE FROM play_session WHERE steam_id = %s", (steam_id,))
        conn.execute("DELETE FROM advice WHERE steam_id = %s", (steam_id,))
        conn.execute("DELETE FROM metric_aggregate WHERE steam_id = %s", (steam_id,))
        if own:
            conn.execute("DELETE FROM match WHERE id = ANY(%s)", ([row[0] for row in own],))
        if user is not None:
            conn.execute(
                "DELETE FROM workspace WHERE created_by = %s AND kind = 'personal'", (user[0],)
            )
            conn.execute("DELETE FROM app_user WHERE id = %s", (user[0],))
        conn.execute("DELETE FROM invitation WHERE steam_id = %s", (steam_id,))
        # In the matches that stay, they are one of the players, out of the level references.
        still = conn.execute(
            "SELECT 1 FROM match_player WHERE steam_id = %s LIMIT 1", (steam_id,)
        ).fetchone()
        if still:
            conn.execute(
                "UPDATE player SET benchmark_opt_out = true WHERE steam_id = %s", (steam_id,)
            )
        else:
            conn.execute("DELETE FROM player WHERE steam_id = %s", (steam_id,))
        # A raw demo goes only when no remaining match uses it (two matches can share one).
        demos = sorted({row[1] for row in own if row[1]})
        used = {
            row[0]
            for row in conn.execute(
                "SELECT demo_key FROM match WHERE demo_key = ANY(%s)", (demos,)
            ).fetchall()
        }
    files = 0
    for _, _, prefix in own:
        if prefix and store.delete_prefix(prefix):
            files += 1
    for key in demos:
        if key not in used and store.delete(key):
            files += 1
    log.info("erased player %s: %d match(es), %d file(s)", steam_id, len(own), files)
    return Erased(matches=len(own), files=files)


@dataclass(frozen=True)
class ErasePlayerJob:
    store: LocalStore

    def __call__(self, conn: psycopg.Connection[Any], job: Job) -> None:
        erase_player(conn, self.store, int(job.payload["steam_id"]))
