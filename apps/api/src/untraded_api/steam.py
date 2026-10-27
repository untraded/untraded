# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Steam sign-in (OpenID 2.0, the only protocol Steam offers).

Steam sends the user back with signed parameters; we ask Steam itself whether they are valid
(`check_authentication`), which also makes each answer usable only once. The Steam id is the
last part of `openid.claimed_id`.
"""

from __future__ import annotations

import re
import urllib.parse
from collections.abc import Mapping

import httpx

ENDPOINT = "https://steamcommunity.com/openid/login"
IDENTIFIER_SELECT = "http://specs.openid.net/auth/2.0/identifier_select"
NAMESPACE = "http://specs.openid.net/auth/2.0"
CLAIMED_ID = re.compile(r"^https://steamcommunity\.com/openid/id/(7656119\d{10})$")


class SteamSignInError(ValueError):
    """The answer from Steam is not a valid sign-in."""


def login_url(return_to: str, realm: str) -> str:
    """Where to send the user to sign in with Steam."""
    params = {
        "openid.ns": NAMESPACE,
        "openid.mode": "checkid_setup",
        "openid.return_to": return_to,
        "openid.realm": realm,
        "openid.identity": IDENTIFIER_SELECT,
        "openid.claimed_id": IDENTIFIER_SELECT,
    }
    return f"{ENDPOINT}?{urllib.parse.urlencode(params)}"


def verify(params: Mapping[str, str], return_to: str, client: httpx.Client) -> int:
    """Checks Steam's answer and returns the Steam id. Raises SteamSignInError."""
    if params.get("openid.mode") != "id_res":
        raise SteamSignInError(f"not a positive answer: {params.get('openid.mode')!r}")
    if params.get("openid.op_endpoint") != ENDPOINT:
        raise SteamSignInError("answer from another OpenID provider")
    if params.get("openid.return_to") != return_to:
        raise SteamSignInError("answer meant for another address")
    claimed = CLAIMED_ID.match(params.get("openid.claimed_id", ""))
    if claimed is None or params.get("openid.identity") != params.get("openid.claimed_id"):
        raise SteamSignInError("no Steam id in the answer")
    check = {key: value for key, value in params.items() if key.startswith("openid.")}
    check["openid.mode"] = "check_authentication"
    try:
        response = client.post(ENDPOINT, data=check, timeout=10)
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise SteamSignInError(f"Steam could not confirm the sign-in: {error}") from error
    fields = dict(line.split(":", 1) for line in response.text.splitlines() if ":" in line)
    if fields.get("is_valid") != "true":
        raise SteamSignInError("Steam says the answer is not valid")
    return int(claimed.group(1))


SHARE_CODES = "https://api.steampowered.com/ICSGOPlayers_730/GetNextMatchSharingCode/v1"


class CodeRejectedError(ValueError):
    """Steam refuses a player's codes: `field` is `auth_code` (403) or `share_code` (412)."""

    def __init__(self, field: str) -> None:
        super().__init__(field)
        self.field = field


def check_codes(
    client: httpx.Client, api_key: str, steam_id: int, auth_code: str, share_code: str
) -> None:
    """Asks Steam for the match after `share_code`, as the collector will: raises CodeRejectedError
    when Steam refuses the codes, SteamUnavailableError when it does not answer."""
    try:
        response = client.get(
            SHARE_CODES,
            params={
                "key": api_key,
                "steamid": str(steam_id),
                "steamidkey": auth_code,
                "knowncode": share_code,
            },
            timeout=15,
        )
    except httpx.HTTPError as error:
        raise SteamUnavailableError(str(error)) from error
    if response.status_code == 403:
        raise CodeRejectedError("auth_code")
    if response.status_code == 412:
        raise CodeRejectedError("share_code")
    if response.status_code not in (200, 202):
        raise SteamUnavailableError(f"HTTP {response.status_code}")


class SteamUnavailableError(Exception):
    """Steam did not answer the check: try again later."""


PLAYER_SUMMARIES = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2"


def persona_name(client: httpx.Client, api_key: str, steam_id: int) -> str | None:
    """The account's public Steam name, or None when Steam does not give it (best effort: it
    only helps the admin recognise who asks for an invitation)."""
    try:
        response = client.get(
            PLAYER_SUMMARIES, params={"key": api_key, "steamids": str(steam_id)}, timeout=5
        )
        players = response.json()["response"]["players"] if response.status_code == 200 else []
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return None
    name = players[0].get("personaname") if players else None
    return name.strip()[:64] or None if isinstance(name, str) else None
