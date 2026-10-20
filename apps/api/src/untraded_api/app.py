# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The HTTP API: Steam sign-in and the signed-in user.

Sign-in is by invitation during the beta: Steam proves who the user is, and the database opens
a session only for a Steam account that has a user (`open_auth_session`, migration 0002). The
session cookie holds a random token; the database stores its sha256.
"""

# No `from __future__ import annotations` here: FastAPI resolves the dependencies from the
# annotations, and string annotations cannot see the dependencies defined in `create_app`.

import hashlib
import secrets
import urllib.parse
import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

import httpx
import psycopg
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from untraded_api import steam
from untraded_api.db import Database
from untraded_api.settings import Settings

COOKIE = "untraded_session"


class Me(BaseModel):
    id: uuid.UUID
    steam_id: str
    """A string: Steam ids do not fit in a JavaScript number."""
    display_name: str


def token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode("ascii")).digest()


def create_app(settings: Settings, *, steam_client: httpx.Client | None = None) -> FastAPI:
    db = Database(settings.database_url)
    client = steam_client or httpx.Client()
    callback = f"{settings.public_url}/auth/steam/callback"
    parts = urllib.parse.urlsplit(settings.public_url)
    realm = f"{parts.scheme}://{parts.netloc}/"

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        db.open()
        try:
            yield
        finally:
            db.close()
            client.close()

    app = FastAPI(title="Untraded API", version="0.0.0", lifespan=lifespan)

    def current_user(request: Request) -> uuid.UUID | None:
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

    def as_user(
        user: Annotated[uuid.UUID, Depends(signed_in)],
    ) -> Iterator[psycopg.Connection[Any]]:
        with db.transaction(user) as conn:
            yield conn

    def back_to_web(outcome: str | None = None) -> RedirectResponse:
        query = f"?signin={outcome}" if outcome else ""
        return RedirectResponse(f"{settings.web_url}/{query}", status.HTTP_303_SEE_OTHER)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/auth/steam")
    def sign_in() -> RedirectResponse:
        return RedirectResponse(steam.login_url(callback, realm), status.HTTP_303_SEE_OTHER)

    @app.get("/auth/steam/callback")
    def sign_in_callback(request: Request) -> RedirectResponse:
        try:
            steam_id = steam.verify(dict(request.query_params), callback, client)
        except steam.SteamSignInError:
            return back_to_web("failed")
        token = secrets.token_urlsafe(32)
        with db.transaction(None) as conn:
            row = conn.execute(
                "SELECT open_auth_session(%s, %s, %s)",
                (steam_id, token_hash(token), settings.session_ttl),
            ).fetchone()
        if row is None or row[0] is None:
            return back_to_web("not_invited")
        response = back_to_web()
        response.set_cookie(
            COOKIE,
            token,
            max_age=int(settings.session_ttl.total_seconds()),
            httponly=True,
            secure=settings.cookie_secure,
            samesite="lax",
            path="/",
        )
        return response

    @app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
    def sign_out(request: Request, response: Response) -> None:
        token = request.cookies.get(COOKIE)
        if token:
            with db.transaction(None) as conn:
                conn.execute("SELECT close_auth_session(%s)", (token_hash(token),))
        response.delete_cookie(COOKIE, path="/", secure=settings.cookie_secure, httponly=True)

    @app.get("/me")
    def me(
        conn: Annotated[psycopg.Connection[Any], Depends(as_user)],
        user: Annotated[uuid.UUID, Depends(signed_in)],
    ) -> Me:
        row = conn.execute(
            "SELECT id, steam_id::text, display_name FROM app_user WHERE id = %s", (user,)
        ).fetchone()
        if row is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not signed in")
        return Me(id=row[0], steam_id=row[1], display_name=row[2])

    return app
