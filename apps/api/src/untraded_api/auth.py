# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Steam sign-in, sign-out and the signed-in user.

Sign-in is by invitation during the beta: Steam proves who the user is, and the database opens
a session only for a Steam account that has a user (`open_auth_session`, migration 0002). The
session cookie holds a random token; the database stores its sha256.
"""

# No `from __future__ import annotations`: FastAPI reads the dependencies from the annotations.

import secrets
import urllib.parse
import uuid

import httpx
from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from untraded_api import steam
from untraded_api.deps import COOKIE, ConnDep, DatabaseDep, SettingsDep, UserDep, token_hash
from untraded_api.settings import Settings

router = APIRouter()


class Me(BaseModel):
    id: uuid.UUID
    steam_id: str
    """A string: Steam ids do not fit in a JavaScript number."""
    display_name: str


def callback_url(settings: Settings) -> str:
    return f"{settings.public_url}/auth/steam/callback"


def back_to_web(settings: Settings, outcome: str | None = None) -> RedirectResponse:
    query = f"?signin={outcome}" if outcome else ""
    return RedirectResponse(f"{settings.web_url}/{query}", status.HTTP_303_SEE_OTHER)


@router.get("/auth/steam")
def sign_in(settings: SettingsDep) -> RedirectResponse:
    parts = urllib.parse.urlsplit(settings.public_url)
    realm = f"{parts.scheme}://{parts.netloc}/"
    url = steam.login_url(callback_url(settings), realm)
    return RedirectResponse(url, status.HTTP_303_SEE_OTHER)


@router.get("/auth/steam/callback")
def sign_in_callback(request: Request, db: DatabaseDep, settings: SettingsDep) -> RedirectResponse:
    client: httpx.Client = request.app.state.steam_client
    try:
        steam_id = steam.verify(dict(request.query_params), callback_url(settings), client)
    except steam.SteamSignInError:
        return back_to_web(settings, "failed")
    token = secrets.token_urlsafe(32)
    with db.transaction(None) as conn:
        row = conn.execute(
            "SELECT open_auth_session(%s, %s, %s)",
            (steam_id, token_hash(token), settings.session_ttl),
        ).fetchone()
    if row is None or row[0] is None:
        return back_to_web(settings, "not_invited")
    response = back_to_web(settings)
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


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def sign_out(request: Request, response: Response, db: DatabaseDep, settings: SettingsDep) -> None:
    token = request.cookies.get(COOKIE)
    if token:
        with db.transaction(None) as conn:
            conn.execute("SELECT close_auth_session(%s)", (token_hash(token),))
    response.delete_cookie(COOKIE, path="/", secure=settings.cookie_secure, httponly=True)


@router.get("/me")
def me(conn: ConnDep, user: UserDep) -> Me:
    row = conn.execute(
        "SELECT id, steam_id::text, display_name FROM app_user WHERE id = %s", (user,)
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not signed in")
    return Me(id=row[0], steam_id=row[1], display_name=row[2])
