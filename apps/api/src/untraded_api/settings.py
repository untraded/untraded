# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The API's configuration, from the environment."""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass


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
        )
