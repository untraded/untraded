# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Sign-in and the signed-in user, against PostgreSQL with the migrations applied
(UNTRADED_TEST_DATABASE_URL; skipped otherwise). Steam is replaced by a fake that confirms."""

from __future__ import annotations

import os
import urllib.parse
from collections.abc import Iterator

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient

from untraded_api.app import COOKIE, create_app
from untraded_api.auth import REQUEST_COOKIE, request_token
from untraded_api.settings import Settings
from untraded_api.steam import ENDPOINT, NAMESPACE

URL = os.environ.get("UNTRADED_TEST_DATABASE_URL", "").replace(
    "postgresql+psycopg://", "postgresql://", 1
)
pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(not URL, reason="UNTRADED_TEST_DATABASE_URL is not set"),
]
PUBLIC = "http://testserver"
WEB = "http://web.test"
INVITED, STRANGER, OTHER = 76561199000000001, 76561199000000002, 76561199000000003


def steam_answer(steam_id: int) -> dict[str, str]:
    claimed = f"https://steamcommunity.com/openid/id/{steam_id}"
    return {
        "openid.ns": NAMESPACE,
        "openid.mode": "id_res",
        "openid.op_endpoint": ENDPOINT,
        "openid.claimed_id": claimed,
        "openid.identity": claimed,
        "openid.return_to": f"{PUBLIC}/auth/steam/callback",
        "openid.sig": "c2ln",
    }


@pytest.fixture
def client() -> Iterator[TestClient]:
    with psycopg.connect(URL, autocommit=True) as conn:
        conn.execute("TRUNCATE app_user, invitation_request CASCADE")
        conn.execute(
            "INSERT INTO app_user (steam_id, display_name) VALUES (%s, 'me'), (%s, 'other')",
            (INVITED, OTHER),
        )
    steam = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text="is_valid:true\n"))
    )
    settings = Settings(database_url=URL, public_url=PUBLIC, web_url=WEB, cookie_secure=False)
    with TestClient(create_app(settings, steam_client=steam), follow_redirects=False) as client:
        yield client


def sign_in(client: TestClient, steam_id: int) -> httpx.Response:
    response: httpx.Response = client.get("/auth/steam/callback", params=steam_answer(steam_id))
    return response


def test_sign_in_starts_at_steam(client: TestClient) -> None:
    response = client.get("/auth/steam")
    assert response.status_code == 303
    location = urllib.parse.urlsplit(response.headers["location"])
    query = dict(urllib.parse.parse_qsl(location.query))
    assert query["openid.return_to"] == f"{PUBLIC}/auth/steam/callback"
    assert query["openid.realm"] == f"{PUBLIC}/"


def test_an_invited_player_signs_in_and_sees_only_themselves(client: TestClient) -> None:
    response = sign_in(client, INVITED)
    assert response.status_code == 303
    assert response.headers["location"] == f"{WEB}/"
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    me = client.get("/me")
    assert me.status_code == 200
    assert me.json()["steam_id"] == str(INVITED)
    assert me.json()["display_name"] == "me"


def test_a_stranger_is_not_let_in(client: TestClient) -> None:
    response = sign_in(client, STRANGER)
    assert response.headers["location"] == f"{WEB}/?signin=not_invited"
    assert COOKIE not in response.cookies
    assert client.get("/me").status_code == 401


def test_a_stranger_may_ask_for_an_invitation_once(client: TestClient) -> None:
    # Nothing is recorded by the refused sign-in itself: only a signed cookie to ask with.
    sign_in(client, STRANGER)
    assert REQUEST_COOKIE in client.cookies
    assert requests() == []
    response = client.post("/auth/invitation-request")
    assert response.headers["location"] == f"{WEB}/?signin=requested"
    assert REQUEST_COOKIE not in client.cookies  # used
    assert requests() == [STRANGER]
    sign_in(client, STRANGER)
    client.post("/auth/invitation-request")
    assert requests() == [STRANGER]  # one request per account
    assert client.get("/me").status_code == 401  # asking lets no one in


def test_no_request_without_a_valid_cookie(client: TestClient) -> None:
    assert client.post("/auth/invitation-request").headers["location"] == (
        f"{WEB}/?signin=request_expired"
    )
    forged = request_token(STRANGER).replace(str(STRANGER), str(OTHER + 10))
    client.cookies.set(REQUEST_COOKIE, forged)
    assert client.post("/auth/invitation-request").headers["location"].endswith("request_expired")
    assert requests() == []


def test_a_user_cannot_be_requested(client: TestClient) -> None:
    client.cookies.set(REQUEST_COOKIE, request_token(INVITED))
    assert client.post("/auth/invitation-request").headers["location"].endswith("requested")
    assert requests() == []


def requests() -> list[int]:
    with psycopg.connect(URL) as conn:
        return [r[0] for r in conn.execute("SELECT steam_id FROM invitation_request")]


def test_a_bad_answer_is_refused(client: TestClient) -> None:
    params = steam_answer(INVITED) | {"openid.return_to": "http://evil.test/callback"}
    response = client.get("/auth/steam/callback", params=params)
    assert response.headers["location"] == f"{WEB}/?signin=failed"
    assert client.get("/me").status_code == 401


def test_sign_out_ends_the_session(client: TestClient) -> None:
    sign_in(client, INVITED)
    token = client.cookies[COOKIE]
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/me").status_code == 401
    client.cookies.set(COOKIE, token)  # an old copy of the cookie is dead too
    assert client.get("/me").status_code == 401


def test_a_forged_cookie_is_nobody(client: TestClient) -> None:
    client.cookies.set(COOKIE, "forged")
    assert client.get("/me").status_code == 401
    assert client.get("/health").json() == {"status": "ok"}
