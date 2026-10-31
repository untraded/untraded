# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The date of a FACEIT match, from FACEIT's Data API (replaced by a fake here)."""

from __future__ import annotations

import datetime as dt

import httpx
import pytest

from untraded_api import faceit
from untraded_api.faceit import match_id, started_at

FACEIT_ID = "1-0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"


@pytest.fixture(autouse=True)
def fresh() -> None:
    faceit.forget()


def fake(answer: httpx.Response) -> httpx.Client:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/data/v4/matches/{FACEIT_ID}"
        assert request.headers["authorization"] == "Bearer key"
        return answer

    return httpx.Client(transport=httpx.MockTransport(handle))


def test_the_match_id_is_read_from_the_file_name() -> None:
    assert match_id(f"{FACEIT_ID}-1-1.dem.zst") == FACEIT_ID
    assert match_id(f"Downloads {FACEIT_ID.upper()}-1-1.DEM.GZ") == FACEIT_ID
    assert match_id("my-scrim.dem") is None


def test_the_start_comes_from_faceit() -> None:
    client = fake(httpx.Response(200, json={"started_at": 1761510000, "configured_at": 1}))
    assert started_at(client, "key", FACEIT_ID) == dt.datetime.fromtimestamp(1761510000, dt.UTC)
    faceit.forget()  # the same match: its answer is kept otherwise
    configured = fake(httpx.Response(200, json={"configured_at": 1761500000}))
    assert started_at(configured, "key", FACEIT_ID) == dt.datetime.fromtimestamp(1761500000, dt.UTC)


def test_faceit_failing_keeps_the_given_date() -> None:
    for answer in (
        httpx.Response(404, json={}),
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"started_at": "soon"}),
        httpx.Response(200, json=[]),
    ):
        assert started_at(fake(answer), "key", FACEIT_ID) is None
    assert started_at(fake(httpx.Response(200, json={})), "key", "../../admin") is None


def test_implausible_dates_are_dropped() -> None:
    for value in (True, 10, 4102444800, 10**20):  # a bool, 1970, 2100, out of range
        faceit.forget()
        assert (
            started_at(fake(httpx.Response(200, json={"started_at": value})), "key", FACEIT_ID)
            is None
        )


def test_an_answer_is_kept_and_calls_are_bounded() -> None:
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json={"started_at": 1761510000})

    client = httpx.Client(transport=httpx.MockTransport(handle))
    assert started_at(client, "key", FACEIT_ID) is not None
    assert started_at(client, "key", FACEIT_ID) is not None
    assert len(calls) == 1  # the second one is kept
    # Every slot taken: no call, no date.
    faceit.forget()
    for _ in range(faceit.CONCURRENT):
        faceit._slots.acquire()
    try:
        assert started_at(client, "key", FACEIT_ID) is None
    finally:
        for _ in range(faceit.CONCURRENT):
            faceit._slots.release()
    assert len(calls) == 1
