# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Demos sent from the site (`/uploads`), against PostgreSQL (UNTRADED_TEST_DATABASE_URL;
skipped otherwise)."""

from __future__ import annotations

import dataclasses
import datetime as dt
import os
import uuid
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
PLAYER = 76561198000000003
ZSTD = b"\x28\xb5\x2f\xfd" + bytes(1000)  # what a FACEIT demo starts with
PARAMS = {"name": "match.dem.zst", "mode": "faceit", "played_at": "2026-10-24T20:00:00+02:00"}
CONSENT = {"text_version": "1", "analysis": True, "research_corpus": False}


@pytest.fixture
def db() -> Iterator[psycopg.Connection[Any]]:
    with psycopg.connect(URL, autocommit=True) as conn:
        conn.execute("TRUNCATE match, app_user, player, job CASCADE")
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
    )


@pytest.fixture
def client(db: psycopg.Connection[Any]) -> Iterator[Any]:
    """Opens the signed-in player's client on the given settings, consenting first."""
    opened: list[TestClient] = []
    token = add_user(db, PLAYER)

    def start(settings: Settings, *, consent: bool = True) -> TestClient:
        client = TestClient(create_app(settings)).__enter__()
        opened.append(client)
        client.cookies.set(COOKIE, token)
        if consent:
            assert client.post("/me/consent", json=CONSENT).status_code == 204
        return client

    yield start
    for client in opened:
        client.__exit__(None, None, None)


def files(settings: Settings) -> list[str]:
    assert settings.uploads_dir is not None
    return sorted(p.name for p in Path(settings.uploads_dir).iterdir())


def test_a_demo_is_received_and_queued(
    db: psycopg.Connection[Any], settings: Settings, client: Any
) -> None:
    me = client(settings)
    sent = me.post("/uploads", params=PARAMS, content=ZSTD)
    assert sent.status_code == 202
    upload = uuid.UUID(sent.json()["upload_id"])
    assert files(settings) == [f"{upload}.dem.zst"]
    assert (Path(settings.uploads_dir or "") / f"{upload}.dem.zst").read_bytes() == ZSTD
    match = db.execute(
        "SELECT mode::text, status::text, played_at FROM match WHERE id = %s", (upload,)
    ).fetchone()
    assert match is not None
    assert match == ("faceit", "pending", dt.datetime(2026, 10, 24, 18, tzinfo=dt.UTC))
    job = db.execute("SELECT kind, payload FROM job").fetchone()
    assert job == ("ingest_upload", {"match_id": str(upload), "file": f"{upload}.dem.zst"})
    listed = me.get("/uploads").json()["items"]
    assert [(i["upload_id"], i["state"], i["mode"]) for i in listed] == [
        (str(upload), "processing", "faceit")
    ]


def test_what_is_refused_before_it_is_kept(
    db: psycopg.Connection[Any], settings: Settings, client: Any
) -> None:
    me = client(dataclasses.replace(settings, upload_max_bytes=500))
    cases = [
        ({**PARAMS, "name": "match.zip"}, ZSTD, 422, "not_a_demo"),
        (PARAMS, b"<html>" + bytes(100), 422, "not_a_demo"),  # not what its name says
        (PARAMS, ZSTD, 413, "too_large"),
    ]
    for params, body, status, reason in cases:
        refused = me.post("/uploads", params=params, content=body)
        assert (refused.status_code, refused.json()["detail"]) == (status, {"reason": reason})
    assert (
        me.post("/uploads", params={**PARAMS, "mode": "premier"}, content=ZSTD).status_code == 422
    )
    future = {**PARAMS, "played_at": "2099-01-01T00:00:00Z"}
    assert me.post("/uploads", params=future, content=ZSTD[:100]).status_code == 422
    assert files(settings) == []
    assert db.execute("SELECT count(*) FROM match").fetchone() == (0,)


def test_consent_comes_first(settings: Settings, client: Any) -> None:
    me = client(settings, consent=False)
    assert me.get("/uploads").json()["refusal"] == "consent"  # the site says so first
    refused = me.post("/uploads", params=PARAMS, content=ZSTD)
    assert (refused.status_code, refused.json()["detail"]) == (409, {"reason": "consent"})


def test_the_limits(db: psycopg.Connection[Any], settings: Settings, client: Any) -> None:
    me = client(dataclasses.replace(settings, uploads_per_day=0, uploads_in_flight=1))
    room = me.get("/uploads").json()
    assert (room["refusal"], room["max_bytes"]) == (None, settings.upload_max_bytes)
    assert me.post("/uploads", params=PARAMS, content=ZSTD).status_code == 202
    assert me.get("/uploads").json()["refusal"] == "busy"
    busy = me.post("/uploads", params=PARAMS, content=ZSTD)
    assert (busy.status_code, busy.json()["detail"]) == (429, {"reason": "busy"})
    db.execute("UPDATE match SET status = 'ready'")  # analysed: room again
    assert me.post("/uploads", params=PARAMS, content=ZSTD).status_code == 202

    db.execute("UPDATE match SET status = 'ready'")
    me = client(dataclasses.replace(settings, uploads_per_day=2, uploads_in_flight=0))
    quota = me.post("/uploads", params=PARAMS, content=ZSTD)
    assert (quota.status_code, quota.json()["detail"]) == (429, {"reason": "quota"})
    assert len(files(settings)) == 2


def test_a_full_disk_and_uploads_off(settings: Settings, client: Any) -> None:
    full = client(dataclasses.replace(settings, upload_min_free_bytes=1 << 62))
    assert full.get("/uploads").json()["refusal"] == "disk_full"
    refused = full.post("/uploads", params=PARAMS, content=ZSTD)
    assert (refused.status_code, refused.json()["detail"]) == (507, {"reason": "disk_full"})
    off = client(dataclasses.replace(settings, uploads_dir=None))
    assert off.get("/uploads").json()["refusal"] == "off"
    assert off.post("/uploads", params=PARAMS, content=ZSTD).status_code == 503


def test_what_became_of_each_upload(
    db: psycopg.Connection[Any], settings: Settings, client: Any
) -> None:
    me = client(dataclasses.replace(settings, uploads_in_flight=0))
    sent = [
        uuid.UUID(me.post("/uploads", params=PARAMS, content=ZSTD).json()["upload_id"])
        for _ in range(4)
    ]
    db.execute("UPDATE match SET status = 'ready', map = 'de_mirage' WHERE id = %s", (sent[0],))
    db.execute(
        "UPDATE match_source SET rejected = 'not_a_player' WHERE external_id = %s",
        (str(sent[1]),),
    )
    db.execute("UPDATE match SET status = 'failed' WHERE id = %s", (sent[2],))
    states = {
        uuid.UUID(i["upload_id"]): (i["state"], i["reason"])
        for i in me.get("/uploads").json()["items"]
    }
    assert states == {
        sent[0]: ("ready", None),
        sent[1]: ("refused", "not_a_player"),
        sent[2]: ("failed", "parse_failed"),
        sent[3]: ("processing", None),
    }
    assert me.get("/uploads").json()["items"][-1]["upload_id"] == str(sent[0])  # newest first
