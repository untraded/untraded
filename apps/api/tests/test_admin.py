# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Invitations, what an invited player gives on the site, and the admin's routes, against
PostgreSQL (UNTRADED_TEST_DATABASE_URL; skipped otherwise)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient
from helpers import add_user

from untraded_api.app import COOKIE, create_app
from untraded_api.deps import token_hash
from untraded_api.secrets_box import decrypt
from untraded_api.settings import Settings

URL = os.environ.get("UNTRADED_TEST_DATABASE_URL", "").replace(
    "postgresql+psycopg://", "postgresql://", 1
)
pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(not URL, reason="UNTRADED_TEST_DATABASE_URL is not set"),
]
ADMIN, GUEST, PLAYER = 76561198000000001, 76561198000000002, 76561198000000003
KEY = bytes(range(32))
AUTH_CODE, SHARE_CODE = "AAAA-BBBBB-CCCC", "CSGO-aaaaa-bbbbb-ccccc-ddddd-eeeee"


@pytest.fixture
def db() -> Iterator[psycopg.Connection[Any]]:
    with psycopg.connect(URL, autocommit=True) as conn:
        conn.execute("TRUNCATE match, app_user, player, invitation, job CASCADE")
        yield conn


def steam(status: int) -> httpx.Client:
    """Steam's share-code endpoint, answering `status`."""
    return httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(status, json={})))


def app(tmp_path: Path, steam_status: int = 200) -> TestClient:
    settings = Settings(
        database_url=URL,
        public_url="http://testserver",
        web_url="http://web",
        cookie_secure=False,
        admins=frozenset({ADMIN}),
        consent_version="2",
        secret_key=KEY,
        steam_api_key="key",
        backups_dir=str(tmp_path),
    )
    return TestClient(create_app(settings, steam_client=steam(steam_status)))


def sign_in(conn: psycopg.Connection[Any], client: TestClient, steam_id: int) -> object:
    """What the Steam callback does: returns the user, or None when refused."""
    token = f"token-{steam_id}"
    row = conn.execute(
        "SELECT open_auth_session(%s, %s, interval '1 day')", (steam_id, token_hash(token))
    ).fetchone()
    client.cookies.set(COOKIE, token)
    return row[0] if row else None


def test_an_invited_player_joins_consents_and_gives_their_codes(
    db: psycopg.Connection[Any], tmp_path: Path
) -> None:
    with app(tmp_path) as client:
        client.cookies.set(COOKIE, add_user(db, ADMIN))
        invited = client.post(
            "/admin/invitations", json={"steam_id": str(PLAYER), "display_name": "p3"}
        )
        assert invited.status_code == 201
        assert invited.json()["state"] == "invited"
        again = {"steam_id": str(PLAYER), "display_name": "p3"}
        assert client.post("/admin/invitations", json=again).status_code == 409

        # Not invited: no account. Invited: the first sign-in creates it.
        assert sign_in(db, client, GUEST) is None
        assert sign_in(db, client, PLAYER) is not None
        me = client.get("/me").json()
        assert (me["display_name"], me["admin"], me["consent"], me["source"]) == (
            "p3",
            False,
            None,
            None,
        )
        assert me["consent_version"] == "2"
        workspace = db.execute(
            "SELECT count(*) FROM workspace w JOIN membership m ON m.workspace_id = w.id "
            "JOIN app_user u ON u.id = m.user_id WHERE u.steam_id = %s AND w.kind = 'personal'",
            (PLAYER,),
        ).fetchone()
        assert workspace == (1,)

        # Codes before consent are refused; an old text is refused.
        codes = {"auth_code": AUTH_CODE.lower(), "share_code": SHARE_CODE}
        assert client.put("/me/source", json=codes).status_code == 409
        old = {"text_version": "1", "analysis": True, "research_corpus": True}
        assert client.post("/me/consent", json=old).status_code == 409
        consent = {"text_version": "2", "analysis": True, "research_corpus": True}
        assert client.post("/me/consent", json=consent).status_code == 204

        bad = {"auth_code": "nope", "share_code": SHARE_CODE}
        assert client.put("/me/source", json=bad).json()["detail"] == {"field": "auth_code"}
        assert client.put("/me/source", json=codes).status_code == 204
        me = client.get("/me").json()
        assert me["consent"]["research_corpus"] is True
        assert me["source"]["enabled"] is True

    source = db.execute(
        "SELECT s.id, s.secret, s.config->>'known_share_code' FROM ingest_source s "
        "JOIN app_user u ON u.id = s.user_id WHERE u.steam_id = %s",
        (PLAYER,),
    ).fetchone()
    assert source is not None
    assert decrypt(KEY, bytes(source[1]), str(source[0])) == AUTH_CODE  # upper-cased
    assert source[2] == SHARE_CODE


def test_steam_refusing_the_codes_names_the_field(
    db: psycopg.Connection[Any], tmp_path: Path
) -> None:
    for status, field in ((403, "auth_code"), (412, "share_code")):
        with app(tmp_path, steam_status=status) as client:
            client.cookies.set(COOKIE, add_user(db, PLAYER + status))
            consent = {"text_version": "2", "analysis": True, "research_corpus": False}
            client.post("/me/consent", json=consent)
            answer = client.put(
                "/me/source", json={"auth_code": AUTH_CODE, "share_code": SHARE_CODE}
            )
            assert (answer.status_code, answer.json()["detail"]) == (422, {"field": field})


def test_a_withdrawal_stops_the_source(db: psycopg.Connection[Any], tmp_path: Path) -> None:
    with app(tmp_path) as client:
        client.cookies.set(COOKIE, add_user(db, PLAYER))
        client.post(
            "/me/consent", json={"text_version": "2", "analysis": True, "research_corpus": True}
        )
        client.put("/me/source", json={"auth_code": AUTH_CODE, "share_code": SHARE_CODE})
        withdraw = {"text_version": "2", "analysis": False, "research_corpus": True}
        assert client.post("/me/consent", json=withdraw).status_code == 204
        me = client.get("/me").json()
        assert me["consent"]["analysis"] is False
        assert me["consent"]["research_corpus"] is False
        assert me["source"]["enabled"] is False


def test_the_admin_lists_and_manages_players(db: psycopg.Connection[Any], tmp_path: Path) -> None:
    (tmp_path / "daily").mkdir()
    (tmp_path / "daily" / "untraded-2026-10-21.dump").write_bytes(b"dump")
    (tmp_path / "offsite.json").write_text('{"ok": true, "at": "2026-10-21T04:00:00Z"}')
    with app(tmp_path) as client:
        player = add_user(db, PLAYER)
        client.cookies.set(COOKIE, player)
        client.post(
            "/me/consent", json={"text_version": "2", "analysis": True, "research_corpus": False}
        )
        client.put("/me/source", json={"auth_code": AUTH_CODE, "share_code": SHARE_CODE})
        assert client.get("/admin/players").status_code == 403  # not an admin

        client.cookies.set(COOKIE, add_user(db, ADMIN))
        client.post("/admin/invitations", json={"steam_id": str(GUEST), "display_name": "g"})
        items = {p["steam_id"]: p for p in client.get("/admin/players").json()["items"]}
        assert items[str(GUEST)]["state"] == "invited"
        assert items[str(ADMIN)]["state"] == "joined"
        followed = items[str(PLAYER)]
        assert followed["state"] == "followed"
        assert "secret" not in str(followed)
        assert AUTH_CODE not in str(followed)

        source = followed["source"]["id"]
        assert client.post(f"/admin/sources/{source}/pause").status_code == 204
        states = {p["steam_id"]: p["state"] for p in client.get("/admin/players").json()["items"]}
        assert states[str(PLAYER)] == "paused"
        assert client.post(f"/admin/sources/{source}/resume").status_code == 204
        assert client.delete(f"/admin/sources/{source}").status_code == 204
        assert client.delete(f"/admin/sources/{source}").status_code == 404

        assert client.delete(f"/admin/invitations/{GUEST}").status_code == 204
        assert client.delete(f"/admin/invitations/{GUEST}").status_code == 404
        listed = [p["steam_id"] for p in client.get("/admin/players").json()["items"]]
        assert str(GUEST) not in listed

        # A dead job and one waiting to retry after an error are failures; a job done is not.
        db.execute(
            "INSERT INTO job (kind, status, attempts, last_error) VALUES ('parse', 'dead', 5, "
            "'boom'), ('session', 'queued', 1, 'oops'), ('parse', 'done', 1, NULL)"
        )
        health = client.get("/admin/health").json()
        assert [(j["kind"], j["error"]) for j in health["failed_jobs"]] == [
            ("session", "oops"),
            ("parse", "boom"),
        ]
        assert health["backups"]["last"]["name"] == "untraded-2026-10-21.dump"
        assert health["backups"]["offsite"]["ok"] is True
        assert health["sources"]["total"] == 0
        assert health["disk"]["total"] > 0


def test_a_player_erases_themselves(db: psycopg.Connection[Any], tmp_path: Path) -> None:
    with app(tmp_path) as client:
        client.cookies.set(COOKIE, add_user(db, PLAYER))
        assert client.post("/me/erase", json={"confirm": False}).status_code == 422
        assert client.post("/me/erase", json={"confirm": True}).status_code == 202
        assert client.get("/me").status_code == 401  # signed out, for good
    assert sign_in(db, client, PLAYER) is None
    assert db.execute("SELECT kind, payload->>'steam_id' FROM job").fetchall() == [
        ("erase_player", str(PLAYER))
    ]


def test_the_admin_erases_a_player(db: psycopg.Connection[Any], tmp_path: Path) -> None:
    with app(tmp_path) as client:
        add_user(db, PLAYER)
        client.cookies.set(COOKIE, add_user(db, ADMIN))
        assert client.delete(f"/admin/players/{ADMIN}").status_code == 409  # not oneself
        assert client.delete(f"/admin/players/{GUEST}").status_code == 404
        assert client.delete(f"/admin/players/{PLAYER}").status_code == 202
        listed = [p["steam_id"] for p in client.get("/admin/players").json()["items"]]
        assert str(PLAYER) not in listed
        assert client.delete(f"/admin/players/{PLAYER}").status_code == 404
