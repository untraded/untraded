# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Demos sent for a team (`POST /uploads?team=`, `GET /teams/{slug}/uploads`), against
PostgreSQL (UNTRADED_TEST_DATABASE_URL; skipped otherwise), as the API role under row-level
security."""

from __future__ import annotations

import dataclasses
import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
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
OWNER, COACH, VIEWER, OUTSIDER = (76561198000000200 + n for n in range(4))
ROSTER = [76561198000000210 + n for n in range(3)]
ZSTD = b"\x28\xb5\x2f\xfd" + bytes(1000)
PARAMS = {
    "name": "scrim.dem.zst",
    "mode": "scrim",
    "played_at": "2026-11-10T20:00:00+01:00",
    "team": "team-one",
}


@pytest.fixture
def db() -> Iterator[psycopg.Connection[Any]]:
    with psycopg.connect(URL, autocommit=True) as conn:
        conn.execute("TRUNCATE match, app_user, player, job, workspace CASCADE")
        yield conn


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=URL,
        public_url="http://testserver",
        web_url="http://web",
        cookie_secure=False,
        uploads_dir=str(tmp_path / "uploads"),
        upload_min_free_bytes=0,
        uploads_in_flight=0,
    )


class Team:
    """A team with its owner, a coach (not on the roster), a viewer and three players on the
    roster, all consenting; plus someone who is not a member."""

    def __init__(self, db: psycopg.Connection[Any]) -> None:
        self.db = db
        self.tokens = {s: add_user(db, s) for s in (OWNER, COACH, VIEWER, OUTSIDER, *ROSTER)}
        db.execute(
            "INSERT INTO consent (user_id, text_version, analysis, research_corpus, recorded_by) "
            "SELECT id, '2', true, false, 'test' FROM app_user"
        )
        row = db.execute("SELECT create_team('Team', 'team-one', %s)", (OWNER,)).fetchone()
        assert row is not None
        self.id = uuid.UUID(str(row[0]))
        for steam_id, role in [(COACH, "coach"), (VIEWER, "viewer")] + [
            (s, "player") for s in ROSTER
        ]:
            db.execute(
                "INSERT INTO membership (workspace_id, user_id, role_id) "
                "SELECT %s, u.id, r.id FROM app_user u, workspace_role r "
                "WHERE u.steam_id = %s AND r.workspace_id = %s AND r.name = %s",
                (self.id, steam_id, self.id, role),
            )
        self.roster(ROSTER)

    def roster(self, players: list[int]) -> None:
        self.db.execute("DELETE FROM roster_member")
        for steam_id in players:
            self.db.execute(
                "INSERT INTO player (steam_id, last_name) VALUES (%s, 'p') ON CONFLICT DO NOTHING",
                (steam_id,),
            )
            self.db.execute(
                "INSERT INTO roster_member (roster_id, steam_id, valid_from) "
                "SELECT id, %s, '2026-01-01' FROM roster WHERE workspace_id = %s",
                (steam_id, self.id),
            )


@pytest.fixture
def team(db: psycopg.Connection[Any]) -> Team:
    return Team(db)


@pytest.fixture
def client(team: Team) -> Iterator[Any]:
    """Opens a client on the given settings, signed in as the given member."""
    opened: list[TestClient] = []

    def start(settings: Settings, steam_id: int) -> TestClient:
        steam = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(500)))
        client = TestClient(create_app(settings, steam_client=steam)).__enter__()
        opened.append(client)
        client.cookies.set(COOKIE, team.tokens[steam_id])
        return client

    yield start
    for client in opened:
        client.__exit__(None, None, None)


def test_a_coach_who_did_not_play_sends_a_match_for_the_team(
    db: psycopg.Connection[Any], settings: Settings, client: Any, team: Team
) -> None:
    coach = client(settings, COACH)
    sent = coach.post("/uploads", params=PARAMS, content=ZSTD)
    assert sent.status_code == 202, sent.text
    upload = uuid.UUID(sent.json()["upload_id"])
    source = db.execute(
        "SELECT s.workspace_id, s.user_id, m.mode::text FROM match_source ms "
        "JOIN ingest_source s ON s.id = ms.source_id JOIN match m ON m.id = ms.match_id "
        "WHERE ms.external_id = %s",
        (str(upload),),
    ).fetchone()
    assert source == (team.id, None, "scrim")  # the team's source, not the coach's
    job = db.execute("SELECT kind, payload FROM job").fetchone()
    assert job == ("ingest_upload", {"match_id": str(upload), "file": f"{upload}.dem.zst"})

    listed = coach.get("/teams/team-one/uploads").json()
    assert [(i["upload_id"], i["state"], i["sent_by"]) for i in listed["items"]] == [
        (str(upload), "processing", "u")
    ]
    assert listed["refusal"] is None
    assert coach.get("/uploads").json()["items"] == []  # not in the coach's own uploads
    # Every member who reads the team's matches reads its history.
    assert len(client(settings, VIEWER).get("/teams/TEAM-ONE/uploads").json()["items"]) == 1


def test_who_may_send_for_the_team(settings: Settings, client: Any, team: Team) -> None:
    viewer = client(settings, VIEWER)
    assert viewer.get("/teams/team-one/uploads").json()["refusal"] == "forbidden"
    refused = viewer.post("/uploads", params=PARAMS, content=ZSTD)
    assert (refused.status_code, refused.json()["detail"]) == (403, {"reason": "forbidden"})

    outsider = client(settings, OUTSIDER)
    refused = outsider.post("/uploads", params=PARAMS, content=ZSTD)
    assert (refused.status_code, refused.json()["detail"]) == (404, {"reason": "team_not_found"})
    assert outsider.get("/teams/team-one/uploads").status_code == 404
    personal = outsider.post("/uploads", params={**PARAMS, "team": f"u-{OWNER}"}, content=ZSTD)
    assert personal.status_code == 404  # a personal space is no team
    assert sorted(Path(settings.uploads_dir or "").iterdir()) == []


def test_a_roster_that_cannot_pass_the_rule_is_said_first(
    db: psycopg.Connection[Any], settings: Settings, client: Any, team: Team
) -> None:
    team.roster(ROSTER[:2])
    coach = client(settings, COACH)
    assert coach.get("/teams/team-one/uploads").json()["refusal"] == "not_enough_roster"
    refused = coach.post("/uploads", params=PARAMS, content=ZSTD)
    assert (refused.status_code, refused.json()["detail"]) == (
        409,
        {"reason": "not_enough_roster"},
    )
    # A roster player who does not consent does not count either.
    team.roster(ROSTER)
    db.execute(
        "UPDATE consent SET analysis = false WHERE user_id = "
        "(SELECT id FROM app_user WHERE steam_id = %s)",
        (ROSTER[0],),
    )
    assert coach.get("/teams/team-one/uploads").json()["refusal"] == "not_enough_roster"


def test_the_limits_are_counted_per_team(
    db: psycopg.Connection[Any], settings: Settings, client: Any, team: Team
) -> None:
    limited = dataclasses.replace(settings, uploads_in_flight=1)
    coach = client(limited, COACH)
    assert coach.post("/uploads", params=PARAMS, content=ZSTD).status_code == 202
    player = client(limited, ROSTER[0])
    busy = player.post("/uploads", params=PARAMS, content=ZSTD)
    assert (busy.status_code, busy.json()["detail"]) == (429, {"reason": "busy"})
    # The team's upload takes nothing from the coach's own room.
    own = {k: v for k, v in PARAMS.items() if k != "team"}
    assert coach.post("/uploads", params=own, content=ZSTD).status_code == 202


def test_the_api_role_reads_neither_senders_nor_sources(
    db: psycopg.Connection[Any], settings: Settings, client: Any, team: Team
) -> None:
    assert client(settings, COACH).post("/uploads", params=PARAMS, content=ZSTD).status_code == 202
    with db.transaction():
        db.execute("SET LOCAL ROLE untraded_api")
        for table in ("upload_sender", "ingest_source"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
                db.execute(f"SELECT * FROM {table}")
        db.execute("SELECT set_config('app.user_id', '', true)")
    # A non-member calling the functions directly gets nothing, and records nothing.
    outsider = db.execute("SELECT id FROM app_user WHERE steam_id = %s", (OUTSIDER,)).fetchone()
    assert outsider is not None
    with db.transaction():
        db.execute("SET LOCAL ROLE untraded_api")
        db.execute("SELECT set_config('app.user_id', %s, true)", (str(outsider[0]),))
        assert db.execute("SELECT * FROM team_uploads(%s, 30)", (team.id,)).fetchall() == []
        with pytest.raises(psycopg.Error, match="team_not_found"), db.transaction():
            db.execute(
                "SELECT add_team_upload(%s, gen_random_uuid(), 'x.dem', 'scrim', now(), 0, 0)",
                (team.id,),
            )
