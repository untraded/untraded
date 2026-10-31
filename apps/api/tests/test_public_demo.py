# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The public demo: anyone opens it without Steam, sees the demo account only, and writes
nothing. Against PostgreSQL with the migrations applied (UNTRADED_TEST_DATABASE_URL)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from helpers import add_user

from untraded_api.app import COOKIE, create_app
from untraded_api.settings import Settings

URL = os.environ.get("UNTRADED_TEST_DATABASE_URL", "").replace(
    "postgresql+psycopg://", "postgresql://", 1
)
pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(not URL, reason="UNTRADED_TEST_DATABASE_URL is not set"),
]
DEMO, PLAYER = 76561190000100001, 76561198000000003


@pytest.fixture
def db() -> Iterator[psycopg.Connection[Any]]:
    with psycopg.connect(URL, autocommit=True) as conn:
        conn.execute("TRUNCATE match, app_user, player, invitation, job CASCADE")
        yield conn


def app(tmp_path: Path, demo: int | None = DEMO) -> TestClient:
    settings = Settings(
        database_url=URL,
        public_url="http://testserver",
        web_url="http://web",
        cookie_secure=False,
        admins=frozenset({DEMO}),  # even listed as an admin, the demo is not one
        demo_steam_id=demo,
        uploads_dir=str(tmp_path),
    )
    return TestClient(create_app(settings), follow_redirects=False)


def test_anyone_opens_the_demo_read_only(db: psycopg.Connection[Any], tmp_path: Path) -> None:
    add_user(db, DEMO)
    with app(tmp_path) as client:
        response = client.get("/auth/demo")
        assert response.status_code == 303
        assert response.headers["location"] == "http://web/"
        me = client.get("/me").json()
        assert me["demo"] is True
        assert me["admin"] is False
        assert client.get("/matches").status_code == 200
        # Every write is refused, whatever the route.
        refused = [
            client.post("/me/consent", json={"text_version": "2", "analysis": False}),
            client.put("/me/source", json={"auth_code": "x", "share_code": "y"}),
            client.post("/me/erase", json={"confirm": True}),
            client.post("/uploads?name=a.dem&mode=faceit&played_at=2026-10-01T00:00:00Z"),
            client.post("/advice/1/feedback", json={"vote": 1}),
            client.get("/admin/players"),
            client.delete("/admin/invitations/76561198000000009"),
        ]
        assert [r.status_code for r in refused] == [403] * len(refused)
        assert client.post("/auth/logout").status_code == 204
    assert db.execute(
        "SELECT deleted_at FROM app_user WHERE steam_id = %s", (DEMO,)
    ).fetchone() == (None,)


def test_a_player_still_writes(db: psycopg.Connection[Any], tmp_path: Path) -> None:
    add_user(db, DEMO)
    with app(tmp_path) as client:
        client.cookies.set(COOKIE, add_user(db, PLAYER))
        assert client.get("/me").json()["demo"] is False
        assert client.post("/me/erase", json={"confirm": False}).status_code == 422  # not 403


def test_no_demo_before_its_import(db: psycopg.Connection[Any], tmp_path: Path) -> None:
    with app(tmp_path) as client:
        assert client.get("/auth/demo").status_code == 404


def test_a_signed_in_player_keeps_their_session(
    db: psycopg.Connection[Any], tmp_path: Path
) -> None:
    add_user(db, DEMO)
    with app(tmp_path) as client:
        token = add_user(db, PLAYER)
        client.cookies.set(COOKIE, token)
        assert client.get("/auth/demo").status_code == 303
        assert client.cookies[COOKIE] == token
        assert client.get("/me").json()["demo"] is False


def test_no_demo_without_its_setting(db: psycopg.Connection[Any], tmp_path: Path) -> None:
    add_user(db, DEMO)
    with app(tmp_path, demo=None) as client:
        assert client.get("/auth/demo").status_code == 404
