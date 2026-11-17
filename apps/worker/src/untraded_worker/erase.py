# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Erases a player who asked for it, or whom an admin removed (`erase_player` job).

Afterwards the player is what any non-registered player of a match is:
- their account goes with everything tied to it: sources and their encrypted codes, consents,
  sign-in sessions, votes, invitation (or request for one) and personal workspace;
- their play sessions, advice and aggregates go too;
- they leave every team: memberships, roster rows (history included) and followed-player rows go,
  and the teams' access to the matches that stay is recomputed. An owner must hand their teams
  over first: `request_erasure` refuses them before closing the account, and this job too;
- the matches that count for no other user (`credit`) are deleted whole: rows, Parquet and raw
  demo, and so are the matches their sources brought that were never parsed (waiting, or failed).
  A demo they sent goes even if it names other users: it was never on those users' accounts;
- a match a team sent for itself stays too (`TEAM_SENT`): it is the team's, whoever played it,
  and counts for nobody's account. If the player sent it, the team's history no longer names them
  (`upload_sender` goes with the account);
- the matches that count for other users stay, since they are those users' matches too. The player
  remains one of the ten players there, never shown outside the match, and is left out of the
  level references from now on (`benchmark_opt_out`);
- with no match left, only their Steam ID stays, with no name or statistics, as that refusal: a
  match parsed later for someone else may name them, and must not bring them back into the
  references. No such row is created for someone who only had an invitation;
- the jobs naming them or their deleted matches go: their payloads hold the Steam ID, or a demo's
  address. A job running elsewhere stays; a `session` job then removes itself.

The research corpus follows at its next copy: without their consent, their demos leave it,
unless another consenting player is in the match. Database dumps keep them until they expire
(4 weeks at most).

The API marks the account deleted when the erasure is asked: they can no longer sign in, and
the collector stops following them, before this job runs. A `session` job still queued then writes
nothing for them.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

import psycopg

from untraded_worker import team_access
from untraded_worker.credit import credited
from untraded_worker.queue import Job
from untraded_worker.store import LocalStore

log = logging.getLogger("untraded.worker")

TEAM_SENT = """EXISTS (
    SELECT 1 FROM match_source team_ms
    JOIN ingest_source team_s ON team_s.id = team_ms.source_id AND team_s.workspace_id IS NOT NULL
    WHERE team_ms.match_id = m.id AND team_ms.rejected IS NULL)"""
"""A SQL condition: a team sent the match `m` for itself, and its upload was not refused."""

OWN_MATCHES = f"""
SELECT m.id, m.demo_key, m.parquet_prefix
FROM match m
JOIN match_player mp ON mp.match_id = m.id AND mp.steam_id = %(steam)s
WHERE NOT {TEAM_SENT} AND NOT EXISTS (
    SELECT 1 FROM match_player o
    JOIN app_user u ON u.steam_id = o.steam_id AND u.deleted_at IS NULL
    WHERE o.match_id = m.id AND o.steam_id <> %(steam)s
      AND {credited("o.match_id", "o.steam_id")}
)
UNION
SELECT m.id, m.demo_key, m.parquet_prefix
FROM match m
WHERE NOT EXISTS (SELECT 1 FROM match_player mp WHERE mp.match_id = m.id)
  AND NOT {TEAM_SENT}
  AND EXISTS (
    SELECT 1 FROM match_source ms
    JOIN ingest_source s ON s.id = ms.source_id
    JOIN app_user u ON u.id = s.user_id
    WHERE ms.match_id = m.id AND u.steam_id = %(steam)s
  )
  AND NOT EXISTS (
    SELECT 1 FROM match_source ms
    JOIN ingest_source s ON s.id = ms.source_id
    JOIN app_user u ON u.id = s.user_id AND u.deleted_at IS NULL
    WHERE ms.match_id = m.id AND u.steam_id <> %(steam)s
  )
"""
"""The player's matches that count for no other (live) user, and the matches their sources
brought that were never parsed (pending, failed: no players known yet) and no other live
user's source brought too; never a match a team sent for itself."""

ORPHANS = f"""
SELECT m.id, m.demo_key, m.parquet_prefix
FROM match m
WHERE m.id = ANY(%(matches)s)
  AND NOT EXISTS (
    SELECT 1 FROM match_player o
    JOIN app_user u ON u.steam_id = o.steam_id AND u.deleted_at IS NULL
    WHERE o.match_id = m.id AND {credited("o.match_id", "o.steam_id")}
  )
  AND NOT EXISTS (
    SELECT 1 FROM match_source ms
    JOIN ingest_source s ON s.id = ms.source_id
    LEFT JOIN app_user u ON u.id = s.user_id
    WHERE ms.match_id = m.id AND ms.rejected IS NULL
      AND (s.workspace_id IS NOT NULL OR u.deleted_at IS NULL)
  )
"""
"""Of `matches`, those nothing keeps any more: they count for no live user (`credit`), and no
live source brought them (a team's, or a live user's: a match not parsed yet has no players)."""


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
        # Locked first: a `session` job holding the account finishes, and everything it wrote is
        # seen below; a job starting now waits, then finds no account.
        user = conn.execute(
            "SELECT id FROM app_user WHERE steam_id = %s FOR UPDATE", (steam_id,)
        ).fetchone()
        if user is not None:
            # `request_erasure` refuses an owner before closing the account; this guards an
            # erasure queued before that check existed, or a hand-over that raced it.
            owner = conn.execute(
                """
                SELECT 1 FROM membership m
                JOIN workspace w ON w.id = m.workspace_id AND w.kind = 'team'
                JOIN workspace_role r ON r.id = m.role_id
                WHERE m.user_id = %s AND '*' = ANY (r.permissions)
                """,
                (user[0],),
            ).fetchone()
            if owner is not None:
                raise EraseError("the player owns a team: hand it over first")
        own = conn.execute(OWN_MATCHES, {"steam": steam_id}).fetchall()
        if own:
            # Locked in id order, then read again: a team's copy of the same demo may have merged
            # into one of them meanwhile (`jobs.ParseJob`), and that match is the team's now.
            conn.execute(
                "SELECT 1 FROM match WHERE id = ANY(%s) ORDER BY id FOR UPDATE",
                ([row[0] for row in own],),
            )
            still = {row[0] for row in conn.execute(OWN_MATCHES, {"steam": steam_id}).fetchall()}
            own = [row for row in own if row[0] in still]
        conn.execute("DELETE FROM play_session WHERE steam_id = %s", (steam_id,))
        conn.execute("DELETE FROM advice WHERE steam_id = %s", (steam_id,))
        conn.execute("DELETE FROM metric_aggregate WHERE steam_id = %s", (steam_id,))
        # Off every roster, history included, and no longer followed by any team: an erased
        # Steam ID must not keep opening matches to a team. Their memberships go with the account.
        conn.execute("DELETE FROM roster_member WHERE steam_id = %s", (steam_id,))
        conn.execute("DELETE FROM workspace_player WHERE steam_id = %s", (steam_id,))
        if own:
            conn.execute("DELETE FROM match WHERE id = ANY(%s)", ([row[0] for row in own],))
        if user is not None:
            conn.execute(
                "DELETE FROM workspace WHERE created_by = %s AND kind = 'personal'", (user[0],)
            )
            conn.execute("DELETE FROM app_user WHERE id = %s", (user[0],))
        conn.execute("DELETE FROM invitation WHERE steam_id = %s", (steam_id,))
        conn.execute("DELETE FROM invitation_request WHERE steam_id = %s", (steam_id,))
        # Out of the level references from now on, in the matches that stay and in any later one.
        # The name goes: `match_player` holds the one shown in a match.
        if user is not None:
            conn.execute(
                """
                INSERT INTO player (steam_id, last_name, benchmark_opt_out) VALUES (%s, '', true)
                ON CONFLICT (steam_id) DO UPDATE
                SET last_name = '', first_seen_at = now(), benchmark_opt_out = true
                """,
                (steam_id,),
            )
        else:
            conn.execute(
                "UPDATE player SET last_name = '', first_seen_at = now(), benchmark_opt_out = true "
                "WHERE steam_id = %s",
                (steam_id,),
            )
        # The matches that stay: their teams' access without this player (and their own space).
        team_access.refresh_player(conn, steam_id)
        # A running job is not ours to delete; this job's own row goes with `ErasePlayerJob`.
        conn.execute(
            "DELETE FROM job WHERE kind IN ('session', 'erase_player', 'refresh_team_access') "
            "AND payload->>'steam_id' = %s AND status <> 'running'",
            (str(steam_id),),
        )
        conn.execute(
            "DELETE FROM job WHERE payload->>'match_id' = ANY(%s) AND status <> 'running'",
            ([str(row[0]) for row in own],),
        )
        unused = _unused_demos(conn, own)
    files = _delete_files(store, own, unused)
    log.info("erased player %s: %d match(es), %d file(s)", steam_id, len(own), files)
    return Erased(matches=len(own), files=files)


Row = tuple[Any, str | None, str | None]
"""A deleted match: its id, raw demo key and Parquet prefix."""


def _unused_demos(conn: psycopg.Connection[Any], deleted: list[Row]) -> list[str]:
    """The raw demos of the deleted matches that no remaining match uses (two can share one)."""
    demos = sorted({row[1] for row in deleted if row[1]})
    used = {
        row[0]
        for row in conn.execute(
            "SELECT demo_key FROM match WHERE demo_key = ANY(%s)", (demos,)
        ).fetchall()
    }
    return [key for key in demos if key not in used]


def _delete_files(store: LocalStore, deleted: list[Row], demos: list[str]) -> int:
    """After the commit: a file deletion is not transactional."""
    files = 0
    for _, _, prefix in deleted:
        if prefix and store.delete_prefix(prefix):
            files += 1
    for key in demos:
        if store.delete(key):
            files += 1
    return files


def drop_team_matches(
    conn: psycopg.Connection[Any], store: LocalStore, match_ids: list[uuid.UUID]
) -> Erased:
    """A deleted team's matches (`delete_team`, migration 0018): those it sent for itself go,
    rows, Parquet and raw demo, unless they count for a registered user or another live source
    brought them too (another team, a player's own upload, the collector). Checked here, under
    the matches' locks, not when the team was deleted: a player may have sent the same demo
    since. Running it again is harmless."""
    with conn.transaction():
        # Locked first, then read in another statement: a statement that waits on a lock reads
        # the rows it was waiting for with its own snapshot, and would miss a player's copy of
        # the demo merged meanwhile (`jobs.ParseJob`).
        conn.execute("SELECT 1 FROM match WHERE id = ANY(%s) ORDER BY id FOR UPDATE", (match_ids,))
        dropped: list[Row] = conn.execute(ORPHANS, {"matches": match_ids}).fetchall()
        if dropped:
            conn.execute("DELETE FROM match WHERE id = ANY(%s)", ([row[0] for row in dropped],))
        unused = _unused_demos(conn, dropped)
    files = _delete_files(store, dropped, unused)
    log.info("deleted team's matches: %d of %d, %d file(s)", len(dropped), len(match_ids), files)
    return Erased(matches=len(dropped), files=files)


@dataclass(frozen=True)
class DropTeamMatchesJob:
    """`drop_team_matches` (payload `{"match_ids": ["<uuid>", ...]}`)."""

    store: LocalStore

    def __call__(self, conn: psycopg.Connection[Any], job: Job) -> None:
        ids = [uuid.UUID(str(i)) for i in job.payload["match_ids"]]
        drop_team_matches(conn, self.store, ids)


@dataclass(frozen=True)
class ErasePlayerJob:
    store: LocalStore

    def __call__(self, conn: psycopg.Connection[Any], job: Job) -> None:
        erase_player(conn, self.store, int(job.payload["steam_id"]))
        # In the job's transaction: if anything fails, the row comes back and the job retries.
        conn.execute("DELETE FROM job WHERE id = %s", (job.id,))
