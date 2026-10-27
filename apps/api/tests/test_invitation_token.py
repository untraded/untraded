# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The signed cookie a visitor who is not invited asks for an invitation with."""

from __future__ import annotations

import httpx

from untraded_api.auth import REQUEST_SECONDS, request_token, requested_steam_id
from untraded_api.steam import persona_name

STEAM_ID = 76561199000000002


def test_a_token_names_its_account_until_it_expires() -> None:
    token = request_token(STEAM_ID, now=1000.0)
    assert requested_steam_id(token, now=1000.0) == STEAM_ID
    assert requested_steam_id(token, now=1000.0 + REQUEST_SECONDS + 1) is None


def test_a_changed_token_is_refused() -> None:
    token = request_token(STEAM_ID, now=1000.0)
    steam_id, expires, signature = token.split(".")
    assert requested_steam_id(f"{int(steam_id) + 1}.{expires}.{signature}", now=1000.0) is None
    assert requested_steam_id(f"{steam_id}.{int(expires) + 999}.{signature}", now=1000.0) is None
    assert requested_steam_id("garbage", now=1000.0) is None
    assert requested_steam_id(None) is None


def test_the_steam_name_is_best_effort() -> None:
    def answer(request: httpx.Request) -> httpx.Response:
        assert request.url.params["steamids"] == str(STEAM_ID)
        return httpx.Response(200, json={"response": {"players": [{"personaname": " Player "}]}})

    with httpx.Client(transport=httpx.MockTransport(answer)) as client:
        assert persona_name(client, "key", STEAM_ID) == "Player"
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(500))) as client:
        assert persona_name(client, "key", STEAM_ID) is None
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text="x"))
    ) as client:
        assert persona_name(client, "key", STEAM_ID) is None
