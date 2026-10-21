# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The admin's routes: invite players, follow how the collector reads their matches, and check
the server's health. Admins are the SteamID64s of `UNTRADED_ADMIN_STEAM_IDS`; every route here
answers 403 to anyone else.

These routes see every player, so they run outside row-level security (`deps.admin`). They
never return an authentication code.
"""

# No `from __future__ import annotations`: FastAPI reads the dependencies from the annotations.

import datetime as dt
import json
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from untraded_api.deps import AdminDep, SettingsDep, UserDep

router = APIRouter(prefix="/admin", tags=["admin"])

STEAM_ID = re.compile(r"^7656119\d{10}$")


class AdminConsent(BaseModel):
    text_version: str
    analysis: bool
    research_corpus: bool
    recorded_at: dt.datetime


class AdminSource(BaseModel):
    id: uuid.UUID
    enabled: bool
    last_success_at: dt.datetime | None
    last_error: str | None
    """`403`: the player changed their authentication code; `412`: the known share code is
    more than a month old. The player fixes both by giving their codes again."""


class Player(BaseModel):
    steam_id: str
    display_name: str
    state: str
    """`invited` (not signed in yet), `joined` (signed in, nothing given yet), `consented` (no
    codes yet), `followed` (the collector reads their matches), `paused` or `withdrawn`."""
    invited_at: dt.datetime | None
    joined_at: dt.datetime | None
    last_seen_at: dt.datetime | None
    consent: AdminConsent | None
    source: AdminSource | None
    matches: int
    """Their analysed matches."""
    last_match_at: dt.datetime | None


class PlayerList(BaseModel):
    items: list[Player]


class InvitationIn(BaseModel):
    steam_id: str
    display_name: str


PLAYERS = """
WITH people AS (
    SELECT coalesce(u.steam_id, i.steam_id) AS steam_id,
           coalesce(u.display_name, i.display_name) AS display_name,
           u.id AS user_id, u.created_at AS joined_at, i.created_at AS invited_at
    FROM app_user u
    FULL JOIN invitation i ON i.steam_id = u.steam_id
    WHERE u.id IS NULL AND i.accepted_at IS NULL OR u.id IS NOT NULL AND u.deleted_at IS NULL
)
SELECT p.steam_id::text, p.display_name, p.user_id, p.joined_at, p.invited_at,
       (SELECT max(a.last_seen_at) FROM auth_session a WHERE a.user_id = p.user_id),
       c.text_version, c.analysis, c.research_corpus, c.recorded_at,
       s.id, s.enabled, s.last_success_at, s.last_error,
       (SELECT count(*) FROM match_player mp JOIN match m ON m.id = mp.match_id
        WHERE mp.steam_id = p.steam_id AND m.status = 'ready'),
       (SELECT max(m.played_at) FROM match_player mp JOIN match m ON m.id = mp.match_id
        WHERE mp.steam_id = p.steam_id AND m.status = 'ready')
FROM people p
LEFT JOIN consent_current c ON c.user_id = p.user_id
LEFT JOIN LATERAL (
    SELECT id, enabled, last_success_at, last_error FROM ingest_source
    WHERE user_id = p.user_id AND kind = 'valve_bot' ORDER BY created_at LIMIT 1
) s ON true
ORDER BY coalesce(p.joined_at, p.invited_at) DESC
"""


def _state(row: tuple[Any, ...]) -> str:
    user, analysis, source, enabled = row[2], row[7], row[10], row[11]
    if user is None:
        return "invited"
    if analysis is False:
        return "withdrawn"
    if source is not None:
        return "followed" if enabled else "paused"
    return "consented" if analysis else "joined"


def _player(row: tuple[Any, ...]) -> Player:
    return Player(
        steam_id=row[0],
        display_name=row[1],
        state=_state(row),
        joined_at=row[3],
        invited_at=row[4],
        last_seen_at=row[5],
        consent=AdminConsent(
            text_version=row[6], analysis=row[7], research_corpus=row[8], recorded_at=row[9]
        )
        if row[6] is not None
        else None,
        source=AdminSource(id=row[10], enabled=row[11], last_success_at=row[12], last_error=row[13])
        if row[10] is not None
        else None,
        matches=row[14],
        last_match_at=row[15],
    )


@router.get("/players")
def players(conn: AdminDep) -> PlayerList:
    """Every player: invited, joined, or followed, newest first."""
    return PlayerList(items=[_player(row) for row in conn.execute(PLAYERS)])


@router.post("/invitations", status_code=status.HTTP_201_CREATED)
def invite(body: InvitationIn, conn: AdminDep, user: UserDep) -> Player:
    """Invites a Steam account: its first sign-in creates the user."""
    steam_id = body.steam_id.strip()
    name = body.display_name.strip()
    if not STEAM_ID.match(steam_id):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {"field": "steam_id"})
    if not name or len(name) > 64:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {"field": "display_name"})
    known = conn.execute(
        "SELECT 1 FROM app_user WHERE steam_id = %s UNION ALL "
        "SELECT 1 FROM invitation WHERE steam_id = %s AND accepted_at IS NULL",
        (int(steam_id), int(steam_id)),
    ).fetchone()
    if known:
        raise HTTPException(status.HTTP_409_CONFLICT, "already invited or a user")
    conn.execute(
        "INSERT INTO invitation (steam_id, display_name, invited_by) VALUES (%s, %s, %s) "
        "ON CONFLICT (steam_id) DO UPDATE SET display_name = EXCLUDED.display_name, "
        "invited_by = EXCLUDED.invited_by, created_at = now(), accepted_at = NULL",
        (int(steam_id), name, user),
    )
    row = next(r for r in conn.execute(PLAYERS) if r[0] == steam_id)
    return _player(row)


@router.delete("/invitations/{steam_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke(steam_id: str, conn: AdminDep) -> None:
    """Withdraws an invitation not used yet."""
    if not STEAM_ID.match(steam_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such invitation")
    deleted = conn.execute(
        "DELETE FROM invitation WHERE steam_id = %s AND accepted_at IS NULL", (int(steam_id),)
    )
    if deleted.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such invitation")


@router.delete("/players/{steam_id}", status_code=status.HTTP_202_ACCEPTED)
def erase(steam_id: str, conn: AdminDep, user: UserDep) -> None:
    """Erases a player: their account closes at once, and the worker deletes their data, with
    the matches no other user played in (`erase_player`). Not undone."""
    if not STEAM_ID.match(steam_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such player")
    me = conn.execute("SELECT steam_id FROM app_user WHERE id = %s", (user,)).fetchone()
    if me is not None and str(me[0]) == steam_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "erase your own account from your settings")
    known = conn.execute(
        "SELECT 1 FROM app_user WHERE steam_id = %(s)s AND deleted_at IS NULL "
        "UNION ALL SELECT 1 FROM invitation WHERE steam_id = %(s)s AND accepted_at IS NULL",
        {"s": int(steam_id)},
    ).fetchone()
    if known is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such player")
    conn.execute("SELECT request_erasure(%s)", (int(steam_id),))


def _source(conn: AdminDep, source_id: uuid.UUID, sql: str) -> None:
    done = conn.execute(sql, (source_id,))
    if done.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such source")


@router.post("/sources/{source_id}/pause", status_code=status.HTTP_204_NO_CONTENT)
def pause(source_id: uuid.UUID, conn: AdminDep) -> None:
    _source(conn, source_id, "UPDATE ingest_source SET enabled = false WHERE id = %s")


@router.post("/sources/{source_id}/resume", status_code=status.HTTP_204_NO_CONTENT)
def resume(source_id: uuid.UUID, conn: AdminDep) -> None:
    _source(conn, source_id, "UPDATE ingest_source SET enabled = true WHERE id = %s")


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove(source_id: uuid.UUID, conn: AdminDep) -> None:
    """Stops following the player and deletes their encrypted code. Their matches, their
    account and their access to the site stay."""
    _source(conn, source_id, "DELETE FROM ingest_source WHERE id = %s")


class Dump(BaseModel):
    name: str
    at: dt.datetime
    bytes: int


class Backups(BaseModel):
    last: Dump | None
    """The newest daily dump; null when there is none, or no backups directory."""
    daily: int
    weekly: int
    offsite: dict[str, Any] | None
    """`offsite.json` in the backups directory, written by the off-site copy, if any."""


class Disk(BaseModel):
    total: int
    free: int


class Health(BaseModel):
    database_bytes: int
    jobs: dict[str, int]
    """Jobs by status (`queued`, `running`, `failed`...)."""
    failed_jobs: list[dict[str, Any]]
    """The last failed jobs: kind, attempts, error, when."""
    matches_7_days: dict[str, int]
    """Matches collected in the last 7 days, by status."""
    sources: dict[str, int]
    """`total`, `paused`, and `erroring`."""
    backups: Backups
    disk: Disk | None
    """The disk the backups are on (on one server, the disk of every volume)."""


def _backups(directory: str | None) -> tuple[Backups, Disk | None]:
    if directory is None or not Path(directory).is_dir():
        return Backups(last=None, daily=0, weekly=0, offsite=None), None
    root = Path(directory)
    daily = sorted((root / "daily").glob("*.dump"))
    weekly = list((root / "weekly").glob("*.dump"))
    last = None
    if daily:
        stat = daily[-1].stat()
        last = Dump(
            name=daily[-1].name,
            at=dt.datetime.fromtimestamp(stat.st_mtime, dt.UTC),
            bytes=stat.st_size,
        )
    offsite = None
    status_file = root / "offsite.json"
    if status_file.is_file():
        try:
            offsite = json.loads(status_file.read_text(encoding="utf-8"))
        except ValueError:
            offsite = {"error": "offsite.json is not JSON"}
    usage = shutil.disk_usage(root)
    return (
        Backups(last=last, daily=len(daily), weekly=len(weekly), offsite=offsite),
        Disk(total=usage.total, free=usage.free),
    )


@router.get("/health")
def health(conn: AdminDep, settings: SettingsDep) -> Health:
    size = conn.execute("SELECT pg_database_size(current_database())").fetchone()
    jobs = dict(conn.execute("SELECT status::text, count(*) FROM job GROUP BY status").fetchall())
    failed = [
        {"kind": r[0], "attempts": r[1], "error": r[2], "at": r[3]}
        for r in conn.execute(
            "SELECT kind, attempts, left(last_error, 300), coalesce(finished_at, created_at) "
            "FROM job WHERE status = 'failed' ORDER BY id DESC LIMIT 10"
        )
    ]
    matches = dict(
        conn.execute(
            "SELECT status::text, count(*) FROM match "
            "WHERE created_at > now() - interval '7 days' GROUP BY status"
        ).fetchall()
    )
    sources = conn.execute(
        "SELECT count(*), count(*) FILTER (WHERE NOT enabled), "
        "count(*) FILTER (WHERE enabled AND last_error IS NOT NULL) "
        "FROM ingest_source WHERE kind = 'valve_bot'"
    ).fetchone()
    backups, disk = _backups(settings.backups_dir)
    return Health(
        database_bytes=size[0] if size else 0,
        jobs=jobs,
        failed_jobs=failed,
        matches_7_days=matches,
        sources={
            "total": sources[0] if sources else 0,
            "paused": sources[1] if sources else 0,
            "erroring": sources[2] if sources else 0,
        },
        backups=backups,
        disk=disk,
    )
