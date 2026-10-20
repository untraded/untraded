# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import urllib.parse

import httpx
import pytest

from untraded_api import steam

RETURN_TO = "https://app.example/api/auth/steam/callback"
STEAM_ID = 76561199000000001


def answer(**overrides: str) -> dict[str, str]:
    """A positive answer from Steam, as it sends it back to `return_to`."""
    claimed = f"https://steamcommunity.com/openid/id/{STEAM_ID}"
    params = {
        "openid.ns": steam.NAMESPACE,
        "openid.mode": "id_res",
        "openid.op_endpoint": steam.ENDPOINT,
        "openid.claimed_id": claimed,
        "openid.identity": claimed,
        "openid.return_to": RETURN_TO,
        "openid.response_nonce": "2026-10-20T16:00:00Zabc",
        "openid.assoc_handle": "1234567890",
        "openid.signed": "signed,op_endpoint,claimed_id,identity,return_to,response_nonce",
        "openid.sig": "c2ln",
    }
    return params | overrides


def steam_says(body: str, status: int = 200) -> tuple[httpx.Client, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, text=body)

    return httpx.Client(transport=httpx.MockTransport(handler)), seen


def test_login_url_asks_steam_to_choose_the_identity() -> None:
    url = urllib.parse.urlsplit(steam.login_url(RETURN_TO, "https://app.example/"))
    assert f"{url.scheme}://{url.netloc}{url.path}" == steam.ENDPOINT
    query = dict(urllib.parse.parse_qsl(url.query))
    assert query["openid.mode"] == "checkid_setup"
    assert query["openid.return_to"] == RETURN_TO
    assert query["openid.realm"] == "https://app.example/"
    assert query["openid.claimed_id"] == steam.IDENTIFIER_SELECT


def test_a_valid_answer_gives_the_steam_id_after_asking_steam() -> None:
    client, seen = steam_says("ns:http://specs.openid.net/auth/2.0\nis_valid:true\n")
    assert steam.verify(answer(), RETURN_TO, client) == STEAM_ID
    sent = dict(urllib.parse.parse_qsl(seen[0].content.decode()))
    assert str(seen[0].url) == steam.ENDPOINT
    assert sent["openid.mode"] == "check_authentication"
    assert sent["openid.sig"] == "c2ln"


@pytest.mark.parametrize(
    "params",
    [
        answer(**{"openid.mode": "cancel"}),
        answer(**{"openid.op_endpoint": "https://evil.example/openid/login"}),
        answer(**{"openid.return_to": "https://evil.example/callback"}),
        answer(**{"openid.claimed_id": "https://evil.example/openid/id/76561199000000001"}),
        answer(**{"openid.identity": "https://steamcommunity.com/openid/id/76561199000000002"}),
    ],
)
def test_malformed_answers_are_refused_without_asking_steam(params: dict[str, str]) -> None:
    client, seen = steam_says("is_valid:true\n")
    with pytest.raises(steam.SteamSignInError):
        steam.verify(params, RETURN_TO, client)
    assert seen == []


@pytest.mark.parametrize(
    ("body", "status"), [("ns:x\nis_valid:false\n", 200), ("", 200), ("oops", 503)]
)
def test_steam_must_confirm(body: str, status: int) -> None:
    client, _ = steam_says(body, status)
    with pytest.raises(steam.SteamSignInError):
        steam.verify(answer(), RETURN_TO, client)
