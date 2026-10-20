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
