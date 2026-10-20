# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The session routes against PostgreSQL (UNTRADED_TEST_DATABASE_URL; skipped otherwise): the
`premier-half` fixture loaded as the worker would, and a session report written as the worker
writes it."""

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
from psycopg.types.json import Jsonb

from untraded import fixtures
from untraded.metrics import REGISTRY
from untraded_api.app import COOKIE, create_app
from untraded_api.sessions import HEADLINES
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
ME, STRANGER = 1, 99
START = dt.datetime(2026, 10, 19, 20, tzinfo=dt.UTC)
COMPARED = (*HEADLINES, "base.kills")
TOKENS: dict[int, str] = {}


@pytest.fixture(scope="module")
def session_id() -> uuid.UUID:
    analysis = analyze(fixtures.read(FIXTURE))
    with psycopg.connect(URL, autocommit=True) as conn:
        conn.execute("TRUNCATE match, app_user, player, metric_definition CASCADE")
        row = conn.execute(
            "INSERT INTO match (mode, status, played_at, ended_at) "
            "VALUES ('premier', 'ready', %s, %s) RETURNING id",
            (START, START + dt.timedelta(minutes=40)),
        ).fetchone()
        assert row is not None
        match_id = row[0]
        load_match(conn, match_id, analysis)
        TOKENS.update({steam_id: add_user(conn, steam_id) for steam_id in (ME, STRANGER)})
        refresh_access(conn, match_id)
        found = {}
        for steam_id in (ME, 2):  # player 2 is not a user: their session stays hidden
            session = conn.execute(
                """
                INSERT INTO play_session (steam_id, started_at, ended_at, matches, rounds,
                    reference_from, reference_to, reference_matches, reference_rounds, enough,
                    params)
                VALUES (%s, %s, %s, 1, 5, '2026-09-19', '2026-10-18', 6, 140, true, %s)
                RETURNING id
                """,
                (steam_id, START, START + dt.timedelta(minutes=40), Jsonb({"min_matches": 5})),
            ).fetchone()
            assert session is not None
            conn.execute(
                "INSERT INTO play_session_match (session_id, match_id) VALUES (%s, %s)",
                (session[0], match_id),
            )
            for metric in COMPARED:
                basis = "per_round" if metric == "base.kills" else "value"
                conn.execute(
                    "INSERT INTO play_session_metric (session_id, metric_id, version, basis, "
                    "session, reference, delta) VALUES (%s, %s, %s, %s, 1.5, 1.0, 0.5)",
                    (session[0], metric, REGISTRY[metric].version, basis),
                )
            found[steam_id] = session[0]
    return uuid.UUID(str(found[ME]))


@pytest.fixture
def client(session_id: uuid.UUID) -> Iterator[TestClient]:
    settings = Settings(
        database_url=URL, public_url="http://testserver", web_url="http://web", cookie_secure=False
    )
    with TestClient(create_app(settings)) as client:
        yield client


def as_player(client: TestClient, steam_id: int) -> TestClient:
    client.cookies.set(COOKIE, TOKENS[steam_id])
    return client


def test_my_sessions(client: TestClient, session_id: uuid.UUID) -> None:
    body = as_player(client, ME).get("/sessions").json()
    assert [s["id"] for s in body["items"]] == [str(session_id)]
    session = body["items"][0]
    assert (session["matches"], session["wins"], session["losses"], session["ties"]) == (1, 0, 1, 0)
    assert [h["metric_id"] for h in session["headlines"]] == list(HEADLINES)
    assert session["headlines"][0]["delta"] == 0.5


def test_session_report(client: TestClient, session_id: uuid.UUID) -> None:
    report = as_player(client, ME).get(f"/sessions/{session_id}").json()
    assert report["reference"] == {
        "since": "2026-09-19",
        "until": "2026-10-18",
        "matches": 6,
        "rounds": 140,
        "enough": True,
        "min_matches": 5,
        "min_rounds": 0,
    }
    assert [m["map"] for m in report["match_list"]] == ["de_cache"]
    assert report["match_list"][0]["my_result"] == "loss"
    metrics = {m["metric_id"]: m for m in report["metrics"]}
    assert set(metrics) == set(COMPARED)
    assert metrics["base.kills"]["basis"] == "per_round"
    assert metrics["base.adr"]["name"] == REGISTRY["base.adr"].name
    assert metrics["trade.untraded_deaths"]["better"] == "lower"


def test_a_stranger_sees_no_session(client: TestClient, session_id: uuid.UUID) -> None:
    stranger = as_player(client, STRANGER)
    assert stranger.get("/sessions").json()["items"] == []
    assert stranger.get(f"/sessions/{session_id}").status_code == 404


def test_anonymous_and_unknown(client: TestClient) -> None:
    assert client.get("/sessions").status_code == 401
    me = as_player(client, ME)
    assert me.get(f"/sessions/{uuid.uuid4()}").status_code == 404
    assert me.get("/sessions", params={"limit": 101}).status_code == 422
