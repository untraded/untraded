# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Request dependencies: the database, the signed-in user, and a connection seen as that user
(row-level security applies)."""

# No `from __future__ import annotations`: FastAPI reads the dependencies from the annotations.

import hashlib
import uuid
from collections.abc import Iterator
from typing import Annotated, Any

import psycopg
from fastapi import Depends, HTTPException, Request, status

from untraded_api.db import Database
from untraded_api.settings import Settings

COOKIE = "untraded_session"


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
