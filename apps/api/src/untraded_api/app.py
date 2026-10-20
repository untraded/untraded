# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The HTTP API: Steam sign-in (`auth`), the matches the user may see (`matches`) and their
play sessions with their report (`sessions`).

Every route that reads data runs in one transaction as `untraded_api`, seen as the signed-in
user (`deps.as_user`): row-level security (ADR 0011) decides what it returns.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from untraded_api import auth, feedback, matches, sessions
from untraded_api.db import Database
from untraded_api.deps import COOKIE
from untraded_api.settings import Settings

__all__ = ["COOKIE", "create_app"]


def create_app(settings: Settings, *, steam_client: httpx.Client | None = None) -> FastAPI:
    db = Database(settings.database_url)
    client = steam_client or httpx.Client()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        db.open()
        try:
            yield
        finally:
            db.close()
            client.close()

    app = FastAPI(title="Untraded API", version="0.0.0", lifespan=lifespan)
    app.state.db = db
    app.state.settings = settings
    app.state.steam_client = client

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(matches.router)
    app.include_router(sessions.router)
    app.include_router(feedback.router)
    return app
