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
`unavailable` and its demo is deleted. So does a demo a player sent without playing in it, when
nothing else brought it (`not_a_player`), and a demo sent for a team where fewer than 3 players
of its roster on the date of the match played on the same side (`not_enough_roster`).

`ingest_upload` (a demo a player or a team sent) is in `uploads`; `refresh_team_access` (who
sees a player's matches, after a team change) in `team_access`; `drop_team_matches` (the matches
a deleted team sent) in `erase`.
"""

from __future__ import annotations

import datetime as dt
import logging
import urllib.parse
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import psycopg

from untraded.demofile import CorruptDemoError, NotADemoError, demo_suffix, digest
from untraded.parsing import CanonicalMatch, UnsupportedModeError
from untraded_worker import erase, load, queue, replays, sessions, team_access, uploads
from untraded_worker.analysis import analyze
from untraded_worker.download import BlockedAddressError, DemoGone, fetch
from untraded_worker.isolated import IsolatedParse, ParseTimeoutError
from untraded_worker.queue import Job
from untraded_worker.runner import DeadHandler, Handler
from untraded_worker.store import LocalStore

Parse = Callable[..., CanonicalMatch]

log = logging.getLogger("untraded.worker")


VOUCHED = """
SELECT 1 FROM match_source vouched_ms
LEFT JOIN ingest_source vouched_s ON vouched_s.id = vouched_ms.source_id
WHERE vouched_ms.match_id = {match} AND vouched_ms.rejected IS NULL
  AND (vouched_ms.kind <> 'upload' OR vouched_s.user_id IS NOT NULL)"""
"""A live source of the match `match` other than a team's: the collector (or another kind), or a
player's own upload. An upload whose source is gone (a deleted team's, an erased player's) is
none."""

ROSTER_SHORT = f"""
SELECT ms.external_id
FROM match_source ms
JOIN ingest_source s ON s.id = ms.source_id AND s.workspace_id IS NOT NULL
JOIN match m ON m.id = ms.match_id
WHERE ms.match_id = %(match)s AND ms.kind = 'upload' AND ms.rejected IS NULL
  AND NOT EXISTS (
    SELECT 1 FROM roster r
    JOIN roster_member rm ON rm.roster_id = r.id
    JOIN unnest(%(steam_ids)s::bigint[], %(sides)s::text[]) AS p(steam_id, side)
      ON p.steam_id = rm.steam_id
    WHERE r.workspace_id = s.workspace_id AND r.active
      AND rm.valid_from <= coalesce(m.played_at::date, current_date)
      AND (rm.valid_to IS NULL OR rm.valid_to >= coalesce(m.played_at::date, current_date))
      AND {load.CONSENTS.format(steam_id="rm.steam_id")}
    GROUP BY p.side
    HAVING count(DISTINCT rm.steam_id) >= 3
  )
"""
"""The uploads of the match sent for a team (its workspace's source) that fail the roster rule:
fewer than 3 players of the team's roster on the date of the match (registered, consenting) on
the same side. `steam_ids` and `sides` are the demo's players, in the same order."""


class JobError(ValueError):
    """The job cannot succeed as it is (e.g. no demo): retrying will not help much."""


@dataclass(frozen=True)
class ParseJob:
    store: LocalStore
    parse: Parse = field(default_factory=IsolatedParse)
    """`untraded.parsing.parse_demo` in a child process, with a deadline; tests replace it."""

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
        except ParseTimeoutError as error:
            # Not retried: each attempt would hold the only worker as long again. Once the parser
            # is fixed, `untraded-worker retry-failed` brings it back.
            conn.execute(
                "UPDATE match SET status = 'failed', error = %s WHERE id = %s",
                (str(error), match_id),
            )
            log.warning("match %s: %s", match_id, error)
            return
        except UnsupportedModeError as error:
            conn.execute(
                "UPDATE match_source SET rejected = 'unsupported_mode' "
                "WHERE match_id = %s AND kind = 'upload' AND rejected IS NULL",
                (match_id,),
            )
            self._out_of_scope(conn, match_id, demo_key, str(error))
            return
        refused = self._refuse_senders(conn, match_id, canonical)
        if refused is not None:
            self._out_of_scope(conn, match_id, demo_key, refused)
            return

        known = conn.execute(
            "SELECT id, demo_key, demo_deleted_at IS NOT NULL FROM match "
            "WHERE sha256 = %s AND id <> %s FOR UPDATE",
            (canonical.match_id, match_id),
        ).fetchone()
        if known is not None:
            # A demo retention already took: this copy brought the file back under the same key.
            kept = None if known[2] else known[1]
            self._merge(conn, match_id, known[0], demo_key, kept)
            return

        analysis = analyze(canonical.tables())
        prefix = f"matches/{match_id}"
        self.store.write_tables(prefix, analysis.tables)
        try:
            replays.write_replays(self.store, prefix, analysis.tables)
        except Exception:  # the viewer's files are derived: the analysis stands without them
            log.exception("replays of match %s failed; `untraded-worker replays` retries", match_id)
        load.load_match(conn, match_id, analysis)
        conn.execute(
            "UPDATE match SET status = 'ready', parquet_prefix = %s, parsed_at = now(), "
            "error = NULL WHERE id = %s",
            (prefix, match_id),
        )
        load.refresh_access(conn, match_id)
        sessions.queue_sessions(conn, match_id)

    def _refuse_senders(
        self, conn: psycopg.Connection[Any], match_id: uuid.UUID, canonical: CanonicalMatch
    ) -> str | None:
        """Rejects the uploads the match does not admit: a player's when they are not in it
        (`not_a_player`), a team's when fewer than 3 players of its roster on the date of the
        match played on the same side (`not_enough_roster`). Returns the reason when nothing else
        brought the match (it is not analysed), None otherwise."""
        players = canonical.player.select("steamid", "team")
        steam_ids = [int(s) for s in players["steamid"].to_list()]
        sides = [str(t) for t in players["team"].to_list()]
        sent = conn.execute(
            "SELECT ms.external_id, u.steam_id FROM match_source ms "
            "JOIN ingest_source s ON s.id = ms.source_id JOIN app_user u ON u.id = s.user_id "
            "WHERE ms.match_id = %s AND ms.kind = 'upload' AND ms.rejected IS NULL",
            (match_id,),
        ).fetchall()
        present = set(steam_ids)
        outsiders = [external for external, steam_id in sent if steam_id not in present]
        short = [
            row[0]
            for row in conn.execute(
                ROSTER_SHORT, {"match": match_id, "steam_ids": steam_ids, "sides": sides}
            ).fetchall()
        ]
        reason = None
        for rejected, ids in (("not_a_player", outsiders), ("not_enough_roster", short)):
            if ids:
                conn.execute(
                    "UPDATE match_source SET rejected = %s "
                    "WHERE kind = 'upload' AND external_id = ANY(%s)",
                    (rejected, ids),
                )
                reason = reason or rejected
        if reason is None:
            return None
        others = conn.execute(
            "SELECT 1 FROM match_source WHERE match_id = %s AND rejected IS NULL", (match_id,)
        ).fetchone()
        return None if others is not None else reason

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
        conn.execute("DELETE FROM workspace_match WHERE match_id = %s", (match_id,))
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
        """The demo is a match we already have: its sources move to it, the duplicate goes.

        A team chooses the date and mode of what it sends, and they bind only the team: when the
        match came from teams alone and a player's own source (or the collector) brings it too,
        the match takes that source's date and mode. Its players' sessions and the other teams'
        roster rule then rest on them, not on a team's choice."""
        conn.execute(
            f"""
            UPDATE match k
            SET played_at = coalesce(d.played_at, k.played_at), mode = d.mode,
                ended_at = coalesce(d.played_at, k.played_at) + (k.ended_at - k.played_at)
            FROM match d
            WHERE k.id = %(known)s AND d.id = %(duplicate)s
              AND EXISTS (
                SELECT 1 FROM match_source ms JOIN ingest_source s ON s.id = ms.source_id
                WHERE ms.match_id = k.id AND ms.rejected IS NULL AND s.workspace_id IS NOT NULL)
              AND NOT EXISTS ({VOUCHED.format(match="k.id")})
              AND EXISTS ({VOUCHED.format(match="d.id")})
            """,
            {"known": known, "duplicate": duplicate},
        )
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
        except BlockedAddressError as blocked:
            raise JobError(f"{url}: {blocked}") from blocked
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


def handlers(store: LocalStore, uploads_dir: Path) -> dict[str, Handler]:
    return {
        "download": DownloadJob(store),
        "ingest_upload": uploads.IngestUploadJob(store, uploads_dir, uploads.max_demo_bytes()),
        "parse": ParseJob(store),
        "session": sessions.SessionJob(store),
        "erase_player": erase.ErasePlayerJob(store),
        "drop_team_matches": erase.DropTeamMatchesJob(store),
        "refresh_team_access": team_access.refresh_team_access,
    }


ON_DEAD: dict[str, DeadHandler] = {"download": match_failed, "parse": match_failed}


def dead_handlers(uploads_dir: Path) -> dict[str, DeadHandler]:
    return {**ON_DEAD, "ingest_upload": uploads.UploadFailed(uploads_dir)}
