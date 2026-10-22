# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The API's configuration, from the environment."""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass

from untraded_api.secrets_box import secret_key


@dataclass(frozen=True)
class Settings:
    database_url: str
    """psycopg connection string (the SQLAlchemy `postgresql+psycopg://` form is accepted)."""
    public_url: str
    """Where the API is reached from browsers, e.g. `https://app.untraded.gg/api`: Steam sends
    the user back to `{public_url}/auth/steam/callback`."""
    web_url: str
    """Where the user lands after signing in or out."""
    session_ttl: dt.timedelta = dt.timedelta(days=30)
    cookie_secure: bool = True
    """Off only for local development over plain http."""
    admins: frozenset[int] = frozenset()
    """SteamID64s of the admins (`UNTRADED_ADMIN_STEAM_IDS`, comma-separated): they manage
    invitations and sources (`/admin`)."""
    consent_version: str = "1"
    """The version of the consent text the site shows (`UNTRADED_CONSENT_VERSION`): a player
    agrees to this one."""
    secret_key: bytes | None = None
    """`UNTRADED_SECRET_KEY`, decoded: encrypts the codes players give. Without it, players
    cannot add their matches on the site."""
    steam_api_key: str | None = None
    """`STEAM_WEB_API_KEY`: checks a player's codes with Steam before keeping them."""
    backups_dir: str | None = None
    """`UNTRADED_BACKUPS_DIR`: where the `backup` service writes its dumps, for `/admin/health`."""
    store_dir: str | None = None
    """`UNTRADED_STORE_DIR`: the worker's store (read-only here), for the round replays."""

    @classmethod
    def from_env(cls) -> Settings:
        url = os.environ.get(
            "UNTRADED_DATABASE_URL", "postgresql://untraded:untraded@localhost:5432/untraded"
        )
        public = os.environ.get("UNTRADED_PUBLIC_URL", "http://localhost:8000").rstrip("/")
        return cls(
            database_url=url.replace("postgresql+psycopg://", "postgresql://", 1),
            public_url=public,
            web_url=os.environ.get("UNTRADED_WEB_URL", "http://localhost:3000").rstrip("/"),
            session_ttl=dt.timedelta(days=float(os.environ.get("UNTRADED_SESSION_DAYS", "30"))),
            cookie_secure=public.startswith("https://"),
            admins=frozenset(
                int(part)
                for part in os.environ.get("UNTRADED_ADMIN_STEAM_IDS", "").split(",")
                if part.strip()
            ),
            consent_version=os.environ.get("UNTRADED_CONSENT_VERSION", "1"),
            secret_key=secret_key(key) if (key := os.environ.get("UNTRADED_SECRET_KEY")) else None,
            steam_api_key=os.environ.get("STEAM_WEB_API_KEY") or None,
            backups_dir=os.environ.get("UNTRADED_BACKUPS_DIR") or None,
            store_dir=os.environ.get("UNTRADED_STORE_DIR") or None,
        )
