# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The routes that answer without a database: they catch wiring mistakes (e.g. a dependency
FastAPI cannot resolve, read as a query parameter) without PostgreSQL."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from untraded_api.app import create_app
from untraded_api.db import Database
from untraded_api.settings import Settings


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(Database, "open", lambda self: None)
    settings = Settings(
        database_url="postgresql://unused@localhost/unused",
        public_url="https://app.example/api",
        web_url="https://app.example",
    )
    with TestClient(create_app(settings), follow_redirects=False) as client:
        yield client


def test_anonymous_requests(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/me").status_code == 401
    assert client.post("/auth/logout").status_code == 204


def test_sign_in_goes_to_steam_with_our_callback(client: TestClient) -> None:
    location = client.get("/auth/steam").headers["location"]
    assert location.startswith("https://steamcommunity.com/openid/login?")
    assert "app.example%2Fapi%2Fauth%2Fsteam%2Fcallback" in location
    assert "openid.realm=https%3A%2F%2Fapp.example%2F" in location


def test_over_https_the_sign_in_cookie_is_host_only(client: TestClient) -> None:
    cookie = client.get("/auth/steam").headers["set-cookie"]
    assert cookie.startswith("__Host-untraded_signin=")
    assert "Secure" in cookie
    assert "Path=/" in cookie
    assert "Domain" not in cookie


def test_a_refused_answer_goes_back_to_the_web(client: TestClient) -> None:
    response = client.get("/auth/steam/callback", params={"openid.mode": "cancel"})
    assert response.headers["location"] == "https://app.example/?signin=failed"
