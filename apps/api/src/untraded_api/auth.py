# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Steam sign-in, sign-out and the signed-in user.

Sign-in is by invitation during the beta: Steam proves who the user is, and the database opens
a session only for a Steam account that has a user (`open_auth_session`, migration 0002). The
session cookie holds a random token; the database stores its sha256.

A Steam account that is not invited may ask for an invitation (migration 0011): the callback
gives it a short-lived signed cookie naming the account Steam just proved, and
`POST /auth/invitation-request` records the request with it. Nothing is recorded unless the
visitor asks.
"""

# No `from __future__ import annotations`: FastAPI reads the dependencies from the annotations.

import datetime as dt
import hashlib
import hmac
import secrets
import time
import urllib.parse
import uuid

import httpx
from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from untraded_api import steam
from untraded_api.deps import (
    COOKIE,
    ConnDep,
    DatabaseDep,
    SettingsDep,
    UserDep,
    current_user,
    token_hash,
)
from untraded_api.settings import Settings

router = APIRouter()

REQUEST_COOKIE = "untraded_invitation_request"
REQUEST_SECONDS = 30 * 60
"""How long a visitor who is not invited has to ask for an invitation after signing in."""
_REQUEST_KEY = secrets.token_bytes(32)
"""Signs the request cookie; a new one at each start of the API ends the pending cookies."""


def request_token(steam_id: int, now: float | None = None) -> str:
    expires = int((now if now is not None else time.time()) + REQUEST_SECONDS)
    payload = f"{steam_id}.{expires}"
    return f"{payload}.{hmac.new(_REQUEST_KEY, payload.encode(), hashlib.sha256).hexdigest()}"


def requested_steam_id(token: str | None, now: float | None = None) -> int | None:
    """The Steam account a request cookie names, or None when it is missing, forged or old."""
    if not token or token.count(".") != 2:
        return None
    steam_id, expires, signature = token.split(".")
    expected = hmac.new(_REQUEST_KEY, f"{steam_id}.{expires}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected) or not (steam_id + expires).isdigit():
        return None
    if int(expires) < (now if now is not None else time.time()):
        return None
    return int(steam_id)


class Consent(BaseModel):
    text_version: str
    analysis: bool
    research_corpus: bool
    recorded_at: dt.datetime


class Source(BaseModel):
    enabled: bool
    last_success_at: dt.datetime | None
    last_error: str | None


class Me(BaseModel):
    id: uuid.UUID
    steam_id: str
    """A string: Steam ids do not fit in a JavaScript number."""
    display_name: str
    admin: bool
    consent: Consent | None
    """The player's current consent; null before they give it."""
    consent_version: str
    """The current consent text: a player whose consent names another version agrees again."""
    source: Source | None
    """How the collector follows their Valve matches; null before they give their codes."""
    can_add_source: bool
    """Whether this server can keep the codes (it has UNTRADED_SECRET_KEY)."""
    demo: bool = False
    """The public demo account (`/auth/demo`): anonymized matches, read-only."""


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
        refused = back_to_web(settings, "not_invited")
        refused.set_cookie(
            REQUEST_COOKIE,
            request_token(steam_id),
            max_age=REQUEST_SECONDS,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="lax",
            path="/",
        )
        return refused
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


@router.post("/auth/invitation-request")
def request_invitation(
    request: Request, db: DatabaseDep, settings: SettingsDep
) -> RedirectResponse:
    """A visitor who is not invited asks for an invitation (a form on the web's home page): the
    request names the Steam account the sign-in just proved. Back to the web with
    `?signin=requested`, or `?signin=request_expired` without a valid cookie."""
    steam_id = requested_steam_id(request.cookies.get(REQUEST_COOKIE))
    if steam_id is None:
        return back_to_web(settings, "request_expired")
    name = None
    if settings.steam_api_key:
        name = steam.persona_name(request.app.state.steam_client, settings.steam_api_key, steam_id)
    with db.transaction(None) as conn:
        conn.execute("SELECT request_invitation(%s, %s)", (steam_id, name))
    response = back_to_web(settings, "requested")
    response.delete_cookie(REQUEST_COOKIE, path="/", secure=settings.cookie_secure, httponly=True)
    return response


DEMO_SESSION = dt.timedelta(hours=2)
"""Short: the worker purges expired sessions, so the public demo cannot pile rows up."""


@router.get("/auth/demo")
def demo_sign_in(request: Request, db: DatabaseDep, settings: SettingsDep) -> RedirectResponse:
    """Opens a read-only session on the demo account (`UNTRADED_DEMO_STEAM_ID`), for anyone: no
    Steam sign-in. 404 when this server has no demo. A visitor already signed in (a player, or
    the demo) keeps their session: a link elsewhere cannot sign a player out."""
    if settings.demo_steam_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no demo here")
    if current_user(request, db) is not None:
        return back_to_web(settings)
    token = secrets.token_urlsafe(32)
    with db.transaction(None) as conn:
        row = conn.execute(
            "SELECT open_auth_session(%s, %s, %s)",
            (settings.demo_steam_id, token_hash(token), DEMO_SESSION),
        ).fetchone()
    if row is None or row[0] is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no demo here")
    response = back_to_web(settings)
    response.set_cookie(
        COOKIE,
        token,
        max_age=int(DEMO_SESSION.total_seconds()),
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
def me(conn: ConnDep, user: UserDep, settings: SettingsDep) -> Me:
    row = conn.execute(
        "SELECT id, steam_id, display_name FROM app_user WHERE id = %s", (user,)
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not signed in")
    consent = conn.execute(
        "SELECT text_version, analysis, research_corpus, recorded_at FROM consent_current "
        "WHERE user_id = %s",
        (user,),
    ).fetchone()
    source = conn.execute("SELECT enabled, last_success_at, last_error FROM my_source()").fetchone()
    return Me(
        id=row[0],
        steam_id=str(row[1]),
        display_name=row[2],
        admin=row[1] in settings.admins and row[1] != settings.demo_steam_id,
        demo=row[1] == settings.demo_steam_id,
        consent=Consent(
            text_version=consent[0],
            analysis=consent[1],
            research_corpus=consent[2],
            recorded_at=consent[3],
        )
        if consent
        else None,
        consent_version=settings.consent_version,
        source=Source(enabled=source[0], last_success_at=source[1], last_error=source[2])
        if source
        else None,
        can_add_source=settings.secret_key is not None,
    )
