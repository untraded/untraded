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
    consent_version: str = "2"
    """The version of the consent text the site shows (`UNTRADED_CONSENT_VERSION`): a player
    agrees to this one."""
    secret_key: bytes | None = None
    """`UNTRADED_SECRET_KEY`, decoded: encrypts the codes players give. Without it, players
    cannot add their matches on the site."""
    steam_api_key: str | None = None
    """`STEAM_WEB_API_KEY`: checks a player's codes with Steam before keeping them."""
    faceit_api_key: str | None = None
    """`FACEIT_API_KEY` (FACEIT Data API, server side): the date of a FACEIT demo sent, from its
    match. Without it, the date the player gives stays."""
    backups_dir: str | None = None
    """`UNTRADED_BACKUPS_DIR`: where the `backup` service writes its dumps, for `/admin/health`."""
    store_dir: str | None = None
    """`UNTRADED_STORE_DIR`: the worker's store (read-only here), for the round replays."""
    uploads_dir: str | None = None
    """`UNTRADED_UPLOADS_DIR`: where the demos players send are written, for the worker to take
    (`ingest_upload`). Without it, players cannot send demos."""
    upload_max_bytes: int = 400_000_000
    """`UNTRADED_UPLOAD_MAX_MB`: the largest file a player may send (FACEIT demos: up to 300 MB)."""
    uploads_per_day: int = 20
    """`UNTRADED_UPLOADS_PER_DAY`: uploads per player in 24 hours; 0 for no limit."""
    uploads_in_flight: int = 3
    """`UNTRADED_UPLOADS_IN_FLIGHT`: a player's uploads not yet analysed; 0 for no limit."""
    upload_min_free_bytes: int = 5_000_000_000
    """`UNTRADED_UPLOAD_MIN_FREE_GB`: uploads are refused when the disk has less free space."""
    demo_steam_id: int | None = None
    """`UNTRADED_DEMO_STEAM_ID`: the demo account (`untraded-worker import-demo`), open to anyone
    in read-only through `/auth/demo`; unset, there is no public demo."""

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
            consent_version=os.environ.get("UNTRADED_CONSENT_VERSION", "2"),
            secret_key=secret_key(key) if (key := os.environ.get("UNTRADED_SECRET_KEY")) else None,
            steam_api_key=os.environ.get("STEAM_WEB_API_KEY") or None,
            faceit_api_key=os.environ.get("FACEIT_API_KEY") or None,
            backups_dir=os.environ.get("UNTRADED_BACKUPS_DIR") or None,
            store_dir=os.environ.get("UNTRADED_STORE_DIR") or None,
            uploads_dir=os.environ.get("UNTRADED_UPLOADS_DIR") or None,
            upload_max_bytes=int(float(os.environ.get("UNTRADED_UPLOAD_MAX_MB", "400")) * 1e6),
            uploads_per_day=int(os.environ.get("UNTRADED_UPLOADS_PER_DAY", "20")),
            uploads_in_flight=int(os.environ.get("UNTRADED_UPLOADS_IN_FLIGHT", "3")),
            demo_steam_id=demo_account(os.environ.get("UNTRADED_DEMO_STEAM_ID")),
            upload_min_free_bytes=int(
                float(os.environ.get("UNTRADED_UPLOAD_MIN_FREE_GB", "5")) * 1e9
            ),
        )


FIRST_REAL_STEAM_ID = 76561197960265728
"""The first SteamID64 of an individual account: a demo account's id is below it."""


def demo_account(value: str | None) -> int | None:
    """`UNTRADED_DEMO_STEAM_ID`, refused unless it is a fake id: set to a real player's by
    mistake, it would open their account to anyone."""
    if not value or not value.strip():
        return None
    steam_id = int(value)
    if steam_id >= FIRST_REAL_STEAM_ID:
        raise ValueError("UNTRADED_DEMO_STEAM_ID must be a fake id (untraded-worker import-demo)")
    return steam_id
