# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The match routes against PostgreSQL (UNTRADED_TEST_DATABASE_URL; skipped otherwise), with the
`premier-half` fixture loaded the way the worker loads a parsed match. Its players are
anonymized (steam ids 1 to 10), so sessions are opened in the database instead of through Steam.
"""

from __future__ import annotations

import datetime as dt
import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient

from untraded import fixtures
from untraded.metrics import REGISTRY
from untraded_api.app import COOKIE, create_app
from untraded_api.deps import token_hash
from untraded_api.settings import Settings
from untraded_worker.analysis import analyze
from untraded_worker.load import load_match, refresh_access

URL = os.environ.get("UNTRADED_TEST_DATABASE_URL", "").replace(
    "postgresql+psycopg://", "postgresql://", 1
)
pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(not URL, reason="UNTRADED_TEST_DATABASE_URL is not set"),
]
FIXTURE = Path(__file__).parents[3] / "packages/untraded-py/tests/fixtures/premier-half"
ME, STRANGER = 1, 99  # player 1 played the fixture (team A, lost 4-11); 99 did not


def _user(conn: psycopg.Connection[Any], steam_id: int) -> str:
    """A user with a personal workspace, signed in: returns the session token."""
    user = conn.execute(
        "INSERT INTO app_user (steam_id, display_name) VALUES (%s, 'u') RETURNING id", (steam_id,)
    ).fetchone()
    assert user is not None
    workspace = conn.execute(
        "INSERT INTO workspace (kind, name, slug, created_by) "
        "VALUES ('personal', 'w', %s, %s) RETURNING id",
        (f"u-{steam_id}", user[0]),
    ).fetchone()
    assert workspace is not None
    role = conn.execute(
        "INSERT INTO workspace_role (workspace_id, name) VALUES (%s, 'owner') RETURNING id",
        (workspace[0],),
    ).fetchone()
    assert role is not None
    conn.execute(
        "INSERT INTO membership (workspace_id, user_id, role_id) VALUES (%s, %s, %s)",
        (workspace[0], user[0], role[0]),
    )
    token = f"token-{steam_id}"
    conn.execute(
        "SELECT open_auth_session(%s, %s, interval '1 day')", (steam_id, token_hash(token))
    )
    return token


@pytest.fixture(scope="module")
def match_id() -> uuid.UUID:
    analysis = analyze(fixtures.read(FIXTURE))
    with psycopg.connect(URL, autocommit=True) as conn:
        conn.execute("TRUNCATE match, app_user, player, metric_definition CASCADE")
        row = conn.execute(
            "INSERT INTO match (mode, status, played_at) VALUES ('premier', 'ready', %s) "
            "RETURNING id",
            (dt.datetime(2026, 10, 19, 20, tzinfo=dt.UTC),),
        ).fetchone()
        assert row is not None
        match_id = uuid.UUID(str(row[0]))
        load_match(conn, match_id, analysis)
        tokens = {steam_id: _user(conn, steam_id) for steam_id in (ME, STRANGER)}
        refresh_access(conn, match_id)
    _TOKENS.update(tokens)
    return match_id


_TOKENS: dict[int, str] = {}


@pytest.fixture
def client(match_id: uuid.UUID) -> Iterator[TestClient]:
    settings = Settings(
        database_url=URL, public_url="http://testserver", web_url="http://web", cookie_secure=False
    )
    with TestClient(create_app(settings)) as client:
        yield client


def as_player(client: TestClient, steam_id: int) -> TestClient:
    client.cookies.set(COOKIE, _TOKENS[steam_id])
    return client


def test_my_matches(client: TestClient, match_id: uuid.UUID) -> None:
    body = as_player(client, ME).get("/matches").json()
    assert [m["id"] for m in body["items"]] == [str(match_id)]
    match = body["items"][0]
    assert (match["map"], match["score_a"], match["score_b"]) == ("de_cache", 4, 11)
    assert (match["my_team"], match["my_result"]) == ("A", "loss")
    assert match["my_line"]["kills"] is not None


def test_match_detail(client: TestClient, match_id: uuid.UUID) -> None:
    detail = as_player(client, ME).get(f"/matches/{match_id}").json()
    assert [r["round"] for r in detail["rounds"]] == [11, 12, 13, 14, 15]
    assert len(detail["players"]) == 10
    assert {p["team"] for p in detail["players"]} == {"A", "B"}
    assert all(p["line"]["kills"] is not None for p in detail["players"])
    assert all(isinstance(p["steam_id"], str) for p in detail["players"])


def test_player_metrics(client: TestClient, match_id: uuid.UUID) -> None:
    body = as_player(client, ME).get(f"/matches/{match_id}/players/2").json()
    values = sum(1 for m in REGISTRY.values() if m.kind == "value")
    assert len(body["metrics"]) == values * 3
    assert {m["scope"] for m in body["metrics"]} == {"match", "ct", "t"}
    adr = next(m for m in body["metrics"] if m["metric_id"] == "base.adr")
    assert adr["unit"] == REGISTRY["base.adr"].unit


def test_a_stranger_sees_nothing(client: TestClient, match_id: uuid.UUID) -> None:
    stranger = as_player(client, STRANGER)
    assert stranger.get("/matches").json()["items"] == []
    assert stranger.get(f"/matches/{match_id}").status_code == 404
    assert stranger.get(f"/matches/{match_id}/players/1").status_code == 404


def test_anonymous_requests_are_refused(client: TestClient, match_id: uuid.UUID) -> None:
    assert client.get("/matches").status_code == 401
    assert client.get(f"/matches/{match_id}").status_code == 401


def test_bad_parameters(client: TestClient) -> None:
    me = as_player(client, ME)
    assert me.get("/matches", params={"limit": 0}).status_code == 422
    assert me.get("/matches/not-a-uuid").status_code == 422
    assert me.get(f"/matches/{uuid.uuid4()}").status_code == 404
