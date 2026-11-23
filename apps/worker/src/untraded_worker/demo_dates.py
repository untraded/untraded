# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The demo keeps its age: its dates move forward so that its last match is always yesterday.

The demo's matches are dated once, when `untraded demo build` makes them. The site reads time
relative to today (a team's record and statistics over 30 days, the uploads of the last 30
days...), so a demo left alone empties itself after a month. When the worker is idle, at most
every `EVERY`, `shift` moves every date of the demo by the same whole number of days: the
matches (start, end), their sources (when received), the demo accounts' sessions (start, end,
reference window) and their findings' span, and the demo teams' review (comments, tags,
playlists). Everything moves together, so nothing else changes: the same sessions hold the same
matches against the same reference, a team match stays the day before its solo match, and no id
changes (no link breaks). The Parquet tables keep the dates they were built with: the database's
are the ones read (the session job takes a match's date from `match.played_at`), and the
difference tells an import how far the demo moved already (`current_offset`).

What is the demo's, and only that:
- a match is the demo's when one of its sources is: the demo's own import (an `upload` with a
  `demo:` id, which only `untraded-worker import-demo` writes), a team whose every member is a
  demo account (fake SteamIDs, `untraded.demo`), or an upload of a demo account;
- the shift stops, moving nothing, if one of these matches has a source that is not the demo's,
  names a player who is not a demo account (0, a bot, aside), or is seen by a workspace with a
  member who is not one: a real player's data never moves;
- it waits while a demo import runs (`demo_lock`, an advisory lock) or a demo account's session
  is being computed, and while one of the demo's matches is not ready.

Times written when a row was made (`created_at` of a membership, a session's `computed_at`) stay:
they are when the demo was loaded. A time the shift would push past now is set to now."""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg

from untraded.demo import FAKE_STEAM_BASE, REAL_LOWEST
from untraded_worker.store import LocalStore

log = logging.getLogger("untraded.worker")

EVERY = dt.timedelta(hours=1)
"""How often the worker checks; it moves something once a day at most (whole days)."""
LOCK = 0x756E7472_00000002
"""Advisory lock: one shift or one demo import at a time."""


def fake(steam_id: str) -> str:
    """A SQL condition: the SteamID (a SQL expression) is a demo account's."""
    return f"({steam_id} > {FAKE_STEAM_BASE} AND {steam_id} < {REAL_LOWEST})"


DEMO_TEAMS = f"""
SELECT dt_w.id FROM workspace dt_w
WHERE dt_w.kind = 'team'
  AND EXISTS (SELECT 1 FROM membership dt_m WHERE dt_m.workspace_id = dt_w.id)
  AND NOT EXISTS (
      SELECT 1 FROM membership dt_m JOIN app_user dt_u ON dt_u.id = dt_m.user_id
      WHERE dt_m.workspace_id = dt_w.id AND NOT {fake("dt_u.steam_id")})"""
"""The teams whose every member is a demo account."""


def demo_source(teams: str) -> str:
    """A SQL condition on a source `ms` (`match_source`) and its `s` (`ingest_source`,
    left-joined): it is the demo's, with `teams` the demo teams (a query of their `id`). Never
    null (EXISTS, not IN: a source has a user or a workspace, never both), so its negation holds
    for every source that is not the demo's."""
    return f"""(
    (ms.kind = 'upload' AND starts_with(ms.external_id, 'demo:'))
    OR EXISTS (SELECT 1 FROM ({teams}) ds_t WHERE ds_t.id = s.workspace_id)
    OR EXISTS (SELECT 1 FROM app_user ds_u
               WHERE ds_u.id = s.user_id AND {fake("ds_u.steam_id")}))"""


def demo_matches(teams: str) -> str:
    """The demo's matches (a `match_id` column)."""
    return f"""
SELECT DISTINCT ms.match_id FROM match_source ms
LEFT JOIN ingest_source s ON s.id = ms.source_id
WHERE {demo_source(teams)}"""


TEAMS = "SELECT id FROM demo_shift_team"
SHIFTED = "(SELECT match_id FROM demo_shift)"
SESSIONS = "(SELECT id FROM demo_shift_session)"


@contextmanager
def demo_lock(conn: psycopg.Connection[Any]) -> Iterator[None]:
    """Held by a demo import from start to end: no shift moves half of it."""
    conn.execute("SELECT pg_advisory_lock(%s)", (LOCK,))
    try:
        yield
    finally:
        conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK,))


def current_offset(conn: psycopg.Connection[Any], store: LocalStore) -> dt.timedelta:
    """How far the demo's dates moved since it was built (whole days; zero before any shift): an
    import adds it to the dates of the matches it brings, so they join the others."""
    row = conn.execute(
        f"""
        SELECT m.played_at, m.parquet_prefix FROM match m
        WHERE m.id IN ({demo_matches(DEMO_TEAMS)}) AND m.status = 'ready'
          AND m.parquet_prefix IS NOT NULL AND m.played_at IS NOT NULL
        ORDER BY m.played_at DESC LIMIT 1
        """
    ).fetchone()
    if row is None:
        return dt.timedelta(0)
    built = store.read_table(str(row[1]), "match")["played_at"][0]
    if built is None:
        return dt.timedelta(0)
    played: dt.datetime = row[0]
    return dt.timedelta(days=(played.astimezone(dt.UTC).date() - built).days)


def _refusal(conn: psycopg.Connection[Any]) -> str | None:
    """Why the demo's matches must not move now (None when they may)."""
    checks = (
        (
            "a source of a demo match is not the demo's",
            f"""SELECT 1 FROM match_source ms LEFT JOIN ingest_source s ON s.id = ms.source_id
                WHERE ms.match_id IN {SHIFTED} AND NOT {demo_source(TEAMS)}""",
        ),
        (
            "a demo team has a member who is not a demo account",
            f"""SELECT 1 FROM membership m JOIN app_user u ON u.id = m.user_id
                WHERE m.workspace_id IN ({TEAMS}) AND NOT {fake("u.steam_id")}""",
        ),
        (
            "a demo match names a player who is not a demo account",
            f"""SELECT 1 FROM match_player mp
                WHERE mp.match_id IN {SHIFTED}
                  AND mp.steam_id <> 0 AND NOT {fake("mp.steam_id")}""",
        ),
        (
            "a demo match is seen by a workspace with a member who is not a demo account",
            f"""SELECT 1 FROM workspace_match wm
                JOIN membership m ON m.workspace_id = wm.workspace_id
                JOIN app_user u ON u.id = m.user_id
                WHERE wm.match_id IN {SHIFTED} AND NOT {fake("u.steam_id")}""",
        ),
    )
    for reason, query in checks:
        if conn.execute(f"SELECT EXISTS ({query})").fetchone() == (True,):
            return reason
    return None


def _busy(conn: psycopg.Connection[Any]) -> str | None:
    """Why the shift waits (None when it may run)."""
    if conn.execute(
        f"SELECT EXISTS (SELECT 1 FROM match WHERE id IN {SHIFTED} AND status <> 'ready')"
    ).fetchone() == (True,):
        return "a demo match is not ready"
    if conn.execute(
        f"""SELECT EXISTS (SELECT 1 FROM job WHERE kind = 'session'
            AND status IN ('queued', 'running')
            AND {fake("(payload->>'steam_id')::bigint")})"""
    ).fetchone() == (True,):
        return "a demo account's session is being computed"
    return None


def shift(conn: psycopg.Connection[Any], today: dt.date | None = None) -> int:
    """Moves the demo's dates so that its last match is the day before `today` (UTC; default
    the current day), in one transaction; returns by how many days (0: nothing moved)."""
    target = (today or dt.datetime.now(dt.UTC).date()) - dt.timedelta(days=1)
    with conn.transaction():
        got = conn.execute("SELECT pg_try_advisory_xact_lock(%s)", (LOCK,)).fetchone()
        if got != (True,):
            return 0  # a demo import is running: the next run will do it
        conn.execute("SET LOCAL TimeZone = 'UTC'")
        # The demo teams, locked (as the team functions lock a team before changing its
        # members; in id order, as they lock several), then frozen: every statement below sees
        # the same ones, and a refusal below checks their members again.
        conn.execute(
            f"SELECT 1 FROM workspace WHERE id IN ({DEMO_TEAMS}) ORDER BY id FOR NO KEY UPDATE"
        )
        conn.execute(f"CREATE TEMP TABLE demo_shift_team ON COMMIT DROP AS {DEMO_TEAMS}")
        conn.execute(f"CREATE TEMP TABLE demo_shift ON COMMIT DROP AS {demo_matches(TEAMS)}")
        conn.execute(f"SELECT 1 FROM match WHERE id IN {SHIFTED} FOR UPDATE")
        last = conn.execute(
            f"SELECT max(played_at)::date FROM match WHERE id IN {SHIFTED}"
        ).fetchone()
        if last is None or last[0] is None:
            return 0
        days = int((target - last[0]).days)
        if days <= 0:
            return 0
        refused = _refusal(conn)
        if refused is not None:
            log.error("demo dates not moved: %s", refused)
            return 0
        waiting = _busy(conn)
        if waiting is not None:
            log.info("demo dates not moved yet: %s", waiting)
            return 0
        # The demo accounts' sessions, made of the demo's matches only.
        conn.execute(
            f"""CREATE TEMP TABLE demo_shift_session ON COMMIT DROP AS
            SELECT ps.id FROM play_session ps WHERE {fake("ps.steam_id")}
              AND NOT EXISTS (SELECT 1 FROM play_session_match psm
                              WHERE psm.session_id = ps.id AND psm.match_id NOT IN {SHIFTED})"""
        )
        _move(conn, days)
    log.info("demo dates moved %s day(s) forward", days)
    return days


def _move(conn: psycopg.Connection[Any], days: int) -> None:
    p = {"days": days}
    by = "%(days)s * interval '1 day'"
    # Never past now; a null time (a comment never edited) stays null.
    capped = f"CASE WHEN {{c}} IS NULL THEN NULL ELSE least({{c}} + {by}, now()) END"
    conn.execute(
        f"UPDATE match SET played_at = played_at + {by}, ended_at = ended_at + {by} "
        f"WHERE id IN {SHIFTED}",
        p,
    )
    conn.execute(
        f"UPDATE match_source SET received_at = {capped.format(c='received_at')} "
        f"WHERE match_id IN {SHIFTED}",
        p,
    )
    # A session's start is unique per player: moved far first, then back, no two meet midway.
    for step in (f"+ {by} + interval '1000 years'", "- interval '1000 years'"):
        conn.execute(
            f"UPDATE play_session SET started_at = started_at {step}, "
            f"ended_at = ended_at {step} WHERE id IN {SESSIONS}",
            p,
        )
    conn.execute(
        "UPDATE play_session SET reference_from = reference_from + %(days)s, "
        f"reference_to = reference_to + %(days)s WHERE id IN {SESSIONS}",
        p,
    )
    conn.execute(
        f"UPDATE advice SET session_from = session_from + {by}, session_to = session_to + {by} "
        f"WHERE session_id IN {SESSIONS}",
        p,
    )
    teams = f"workspace_id IN ({TEAMS})"
    conn.execute(
        f"UPDATE review_comment SET created_at = {capped.format(c='created_at')}, "
        f"edited_at = {capped.format(c='edited_at')} WHERE {teams}",
        p,
    )
    conn.execute(
        f"UPDATE review_tag SET created_at = {capped.format(c='created_at')} WHERE {teams}", p
    )
    conn.execute(
        f"UPDATE review_playlist SET created_at = {capped.format(c='created_at')}, "
        f"updated_at = {capped.format(c='updated_at')} WHERE {teams}",
        p,
    )
    conn.execute(
        f"UPDATE review_playlist_round SET added_at = {capped.format(c='added_at')} WHERE {teams}",
        p,
    )
