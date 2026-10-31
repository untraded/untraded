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

import psycopg
import pytest
from fastapi.testclient import TestClient
from helpers import add_user

from untraded import fixtures
from untraded.metrics import REGISTRY
from untraded.replay import build_replays, to_json_gz
from untraded_api.app import COOKIE, create_app
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
        tokens = {steam_id: add_user(conn, steam_id) for steam_id in (ME, STRANGER)}
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
    # The Untraded Rating is each player's headline, and sorts the players of a team.
    ratings = [p["line"]["untraded"] for p in detail["players"] if p["team"] == "A"]
    assert all(r is not None for r in ratings)
    assert ratings == sorted(ratings, reverse=True)


def test_player_rating_adds_up_from_its_parts(client: TestClient, match_id: uuid.UUID) -> None:
    body = as_player(client, ME).get(f"/matches/{match_id}/players/1/rating").json()
    assert body["value"] is not None
    assert body["margin"] > 0
    assert body["rounds"] > 0
    parts = {p["part"]: p["points"] for p in body["parts"]}
    assert set(parts) == {"kills", "deaths", "plants", "defuses", "baseline"}
    assert sum(parts.values()) == pytest.approx(body["value"], abs=1e-6)
    assert parts["deaths"] <= 0 <= parts["kills"]
    stranger = as_player(client, STRANGER)
    assert stranger.get(f"/matches/{match_id}/players/1/rating").status_code == 404


def test_player_metrics(client: TestClient, match_id: uuid.UUID) -> None:
    body = as_player(client, ME).get(f"/matches/{match_id}/players/2").json()
    values = sum(1 for m in REGISTRY.values() if m.kind == "value")
    assert len(body["metrics"]) == values * 3
    assert {m["scope"] for m in body["metrics"]} == {"match", "ct", "t"}
    adr = next(m for m in body["metrics"] if m["metric_id"] == "base.adr")
    assert adr["unit"] == REGISTRY["base.adr"].unit
    assert adr["better"] == "higher"


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


def test_a_round_replay_is_served_to_who_may_see_the_match(
    match_id: uuid.UUID, tmp_path: Path
) -> None:
    replays = build_replays(fixtures.read(FIXTURE))
    prefix = f"matches/{match_id}"
    (tmp_path / prefix / "replay").mkdir(parents=True)
    (tmp_path / prefix / "replay" / "11.json.gz").write_bytes(to_json_gz(replays[11]))
    with psycopg.connect(URL, autocommit=True) as conn:
        conn.execute("UPDATE match SET parquet_prefix = %s WHERE id = %s", (prefix, match_id))
    settings = Settings(
        database_url=URL,
        public_url="http://testserver",
        web_url="http://web",
        cookie_secure=False,
        store_dir=str(tmp_path),
    )
    with TestClient(create_app(settings)) as client:
        me = as_player(client, ME)
        answer = me.get(f"/matches/{match_id}/rounds/11/replay")
        assert answer.status_code == 200
        assert answer.headers["content-encoding"] == "gzip"
        body = answer.json()  # the client unzips it
        assert (body["round"], len(body["players"])) == (11, 10)
        version = body["version"]
        assert me.get(f"/matches/{match_id}/rounds/11/replay?v={version}").status_code == 200
        newer = me.get(f"/matches/{match_id}/rounds/11/replay?v={version + 1}")
        assert (newer.status_code, newer.headers["cache-control"]) == (404, "no-store")
        assert me.get(f"/matches/{match_id}/rounds/12/replay").status_code == 404
        stranger = as_player(client, STRANGER)
        assert stranger.get(f"/matches/{match_id}/rounds/11/replay").status_code == 404
