# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""What an invited player does on the site after their first sign-in: give their consent, then
the two codes that let the collector follow their Valve matches.

Both run as the player (row-level security: their own rows only). The codes are checked with
Steam before they are kept, and the authentication code is stored encrypted, as the collector's
`add-source` does.
"""

# No `from __future__ import annotations`: FastAPI reads the dependencies from the annotations.

import re
import uuid

import httpx
from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from untraded_api import steam
from untraded_api.deps import COOKIE, ConnDep, SettingsDep, UserDep
from untraded_api.secrets_box import encrypt

router = APIRouter(prefix="/me", tags=["onboarding"])

AUTH_CODE = re.compile(r"^[A-Z0-9]{4}-[A-Z0-9]{5}-[A-Z0-9]{4}$")
SHARE_CODE = re.compile(r"^CSGO(-[A-Za-z0-9]{5}){5}$")


class ConsentIn(BaseModel):
    text_version: str
    """The version of the text the player read: it must be the current one to agree."""
    analysis: bool
    """Box 1. False withdraws the consent, and stops following the player's matches."""
    research_corpus: bool
    """Box 2 (optional): keep their raw demos in the research corpus."""


class SourceIn(BaseModel):
    auth_code: str
    """The match history authentication code, e.g. `AAAA-BBBBB-CCCC`."""
    share_code: str
    """The share code of one of their recent matches: following starts after it."""


@router.post("/consent", status_code=status.HTTP_204_NO_CONTENT)
def give_consent(body: ConsentIn, conn: ConnDep, user: UserDep, settings: SettingsDep) -> None:
    if body.analysis and body.text_version != settings.consent_version:
        raise HTTPException(status.HTTP_409_CONFLICT, "this is not the current consent text")
    conn.execute(
        "INSERT INTO consent (user_id, text_version, analysis, research_corpus, recorded_by) "
        "VALUES (%s, %s, %s, %s, 'site')",
        (user, body.text_version, body.analysis, body.analysis and body.research_corpus),
    )
    if not body.analysis:
        conn.execute("SELECT pause_my_sources()")


@router.put("/source", status_code=status.HTTP_204_NO_CONTENT)
def set_source(
    body: SourceIn, request: Request, conn: ConnDep, user: UserDep, settings: SettingsDep
) -> None:
    """Keeps the player's codes, after Steam accepted them. 422 names the refused field
    (`auth_code` or `share_code`); 409 when the player has not consented."""
    if settings.secret_key is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "codes cannot be stored here")
    consent = conn.execute(
        "SELECT analysis FROM consent_current WHERE user_id = %s", (user,)
    ).fetchone()
    if consent is None or not consent[0]:
        raise HTTPException(status.HTTP_409_CONFLICT, "consent first")
    auth_code = body.auth_code.strip().upper()
    share_code = body.share_code.strip()
    if not AUTH_CODE.match(auth_code):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {"field": "auth_code"})
    if not SHARE_CODE.match(share_code):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {"field": "share_code"})
    row = conn.execute("SELECT steam_id FROM app_user WHERE id = %s", (user,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not signed in")
    if settings.steam_api_key:
        client: httpx.Client = request.app.state.steam_client
        try:
            steam.check_codes(client, settings.steam_api_key, row[0], auth_code, share_code)
        except steam.CodeRejectedError as rejected:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, {"field": rejected.field}
            ) from rejected
        except steam.SteamUnavailableError as error:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "Steam did not answer"
            ) from error
    # ingest_source is out of the API role's reach: its own functions read and write it.
    found = conn.execute("SELECT id FROM my_source()").fetchone()
    source = found[0] if found else uuid.uuid4()
    secret = encrypt(settings.secret_key, auth_code, str(source))
    conn.execute("SELECT set_my_source(%s, %s, %s)", (source, secret, share_code))


class EraseIn(BaseModel):
    confirm: bool
    """Must be true: the site asks the player to confirm first."""


@router.post("/erase", status_code=status.HTTP_202_ACCEPTED)
def erase_me(body: EraseIn, response: Response, conn: ConnDep, settings: SettingsDep) -> None:
    """The player's right to erasure: their account closes at once (signed out, no longer
    followed), and the worker deletes their data (`erase_player`)."""
    if not body.confirm:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {"field": "confirm"})
    conn.execute("SELECT request_my_erasure()")
    response.delete_cookie(COOKIE, path="/", secure=settings.cookie_secure, httponly=True)
