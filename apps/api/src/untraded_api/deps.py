# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Request dependencies: the database, the signed-in user, and a connection seen as that user
(row-level security applies)."""

# No `from __future__ import annotations`: FastAPI reads the dependencies from the annotations.

import hashlib
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated, Any

import psycopg
from fastapi import Depends, HTTPException, Request, status

from untraded_api.db import Database
from untraded_api.settings import Settings

COOKIE = "untraded_session"

CLEAR_CACHE = {"Clear-Site-Data": '"cache"'}
"""Sent when a session ends (sign-out, erasure): a browser that receives it drops what it cached of
the site, so the replays of one account do not outlive its session on a shared computer. The site
signs out from its server, so only a browser calling the API itself gets it; the replays are kept
a day at most for that reason."""


def token_hash(token: str) -> bytes:
    """What the database keeps of a session token."""
    return hashlib.sha256(token.encode("ascii")).digest()


def database(request: Request) -> Database:
    db: Database = request.app.state.db
    return db


def settings(request: Request) -> Settings:
    found: Settings = request.app.state.settings
    return found


DatabaseDep = Annotated[Database, Depends(database)]
SettingsDep = Annotated[Settings, Depends(settings)]


def current_user(request: Request, db: DatabaseDep) -> uuid.UUID | None:
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    with db.transaction(None) as conn:
        row = conn.execute("SELECT auth_session_user(%s)", (token_hash(token),)).fetchone()
    return row[0] if row else None


def signed_in(user: Annotated[uuid.UUID | None, Depends(current_user)]) -> uuid.UUID:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not signed in")
    return user


UserDep = Annotated[uuid.UUID, Depends(signed_in)]


def as_user(db: DatabaseDep, user: UserDep) -> Iterator[psycopg.Connection[Any]]:
    """A transaction seen as the signed-in user: row-level security decides what it sees."""
    with db.transaction(user) as conn:
        yield conn


ConnDep = Annotated[psycopg.Connection[Any], Depends(as_user)]


def admin(
    db: DatabaseDep, user: UserDep, settings: SettingsDep
) -> Iterator[psycopg.Connection[Any]]:
    """A transaction over every player, for an admin only (403 otherwise)."""
    with db.transaction(user) as conn:
        row = conn.execute("SELECT steam_id FROM app_user WHERE id = %s", (user,)).fetchone()
    if row is None or row[0] not in settings.admins or row[0] == settings.demo_steam_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admins only")
    with db.admin() as conn:
        yield conn


AdminDep = Annotated[psycopg.Connection[Any], Depends(admin)]

READS = frozenset({"GET", "HEAD", "OPTIONS"})
DEMO_MAY_POST = frozenset({"/auth/logout"})


def refuse_demo_writes(
    request: Request,
    db: DatabaseDep,
    settings: SettingsDep,
    user: Annotated[uuid.UUID | None, Depends(current_user)],
) -> None:
    """The demo account reads only: every other request of it is refused (403 `demo`), whatever
    the route, so a new write route cannot forget it. Applied to the whole app."""
    if settings.demo_steam_id is None or request.method in READS:
        return
    if request.url.path in DEMO_MAY_POST or user is None:
        return
    if is_demo(db, settings, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "demo")


def is_demo(db: Database, settings: Settings, user: uuid.UUID) -> bool:
    """Whether `user` is the public demo account."""
    if settings.demo_steam_id is None:
        return False
    with db.transaction(user) as conn:
        row = conn.execute("SELECT steam_id FROM app_user WHERE id = %s", (user,)).fetchone()
    return row is not None and row[0] == settings.demo_steam_id


REFUSAL = "UT001"
"""The SQLSTATE of the database's refusals (migration 0016): the message is a stable code."""
REFUSAL_STATUS = {
    "team_not_found": status.HTTP_404_NOT_FOUND,
    "invitation_invalid": status.HTTP_404_NOT_FOUND,
    "forbidden": status.HTTP_403_FORBIDDEN,
    "role_too_high": status.HTTP_403_FORBIDDEN,
    "consent_required": status.HTTP_403_FORBIDDEN,
    "last_owner": status.HTTP_409_CONFLICT,
    "not_a_member": status.HTTP_409_CONFLICT,
    "already_member": status.HTTP_409_CONFLICT,
    "slug_taken": status.HTTP_409_CONFLICT,
    "owner_must_hand_over": status.HTTP_409_CONFLICT,
    "slug_invalid": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "owner_unknown": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "max_uses_invalid": status.HTTP_422_UNPROCESSABLE_CONTENT,
}


@contextmanager
def refusals() -> Iterator[None]:
    """Turns a refusal raised by a database function into its HTTP error, with the code as the
    `detail`. The transaction is then aborted: the dependency rolls it back."""
    try:
        yield
    except psycopg.Error as error:
        code = error.diag.message_primary if error.sqlstate == REFUSAL else None
        if code is None or code not in REFUSAL_STATUS:
            raise
        raise HTTPException(REFUSAL_STATUS[code], code) from error
