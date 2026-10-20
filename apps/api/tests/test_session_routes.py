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
        workspace = conn.execute(
            "SELECT w.id FROM workspace w JOIN app_user u ON u.id = w.created_by "
            "WHERE u.steam_id = %s",
            (ME,),
        ).fetchone()
        assert workspace is not None
        evidence = [{"match_id": str(match_id), "round": 12, "tick": 64000, "goto_tick": 63680}]
        conn.execute(
            """
            INSERT INTO advice (steam_id, workspace_id, session_from, session_to, rule_id,
                rule_version, priority, message_key, message_args, evidence, session_id, cost,
                events, rounds_touched, rounds_lost)
            VALUES (%s, %s, %s, %s, 'trade.untraded_deaths', '1.0.0', 1,
                'advice.trade.untraded_deaths', %s, %s, %s, 3.5, 4, 4, 3)
            """,
            (
                ME,
                workspace[0],
                START,
                START,
                Jsonb({"events": 4, "actions": ["adjust.trade_distance"]}),
                Jsonb(evidence),
                found[ME],
            ),
        )
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
        "kind": "self",
        "level_low": None,
        "level_high": None,
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


def test_the_report_carries_its_priorities(client: TestClient, session_id: uuid.UUID) -> None:
    me = as_player(client, ME)
    (advice,) = me.get(f"/sessions/{session_id}").json()["advice"]
    assert (advice["rule_id"], advice["priority"], advice["my_vote"]) == (
        "trade.untraded_deaths",
        1,
        None,
    )
    assert advice["evidence"][0]["goto_tick"] == 63680
    assert advice["args"]["actions"] == ["adjust.trade_distance"]

    url = f"/advice/{advice['id']}/feedback"
    assert me.post(url, json={"vote": 1}).status_code == 204
    assert me.get(f"/sessions/{session_id}").json()["advice"][0]["my_vote"] == 1
    assert me.post(url, json={"vote": -1}).status_code == 204
    assert me.get(f"/sessions/{session_id}").json()["advice"][0]["my_vote"] == -1
    assert me.post(url, json={"vote": 0}).status_code == 204
    assert me.get(f"/sessions/{session_id}").json()["advice"][0]["my_vote"] is None
    assert me.post(url, json={"vote": 2}).status_code == 422

    stranger = as_player(client, STRANGER)
    assert stranger.post(url, json={"vote": 1}).status_code == 404
    client.cookies.clear()
    assert client.post(url, json={"vote": 1}).status_code == 401
