# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Database access, under row-level security.

Each request runs in one transaction as the `untraded_api` role (migration 0002), which owns
nothing and bypasses nothing, with `app.user_id` set to the signed-in user: the policies of
ADR 0011 decide what the request sees, whatever the query.

The one exception is `admin()`: the `/admin` routes manage every player, so they run as the
connection's own role. Only `deps.admin` opens it, after checking the signed-in user is an admin.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg_pool import ConnectionPool

API_ROLE = "untraded_api"


class Database:
    def __init__(self, url: str, *, max_size: int = 10) -> None:
        self.pool: ConnectionPool[psycopg.Connection[Any]] = ConnectionPool(
            url, min_size=1, max_size=max_size, open=False
        )

    def open(self) -> None:
        self.pool.open(wait=True, timeout=30)

    def close(self) -> None:
        self.pool.close()

    @contextmanager
    def transaction(self, user: uuid.UUID | None) -> Iterator[psycopg.Connection[Any]]:
        """A transaction as `untraded_api`, seen as `user` (or as nobody). Commits at the end,
        rolls back on an exception."""
        with self.pool.connection() as conn:
            conn.execute(f"SET LOCAL ROLE {API_ROLE}")
            if user is not None:
                conn.execute("SELECT set_config('app.user_id', %s, true)", (str(user),))
            yield conn

    @contextmanager
    def admin(self) -> Iterator[psycopg.Connection[Any]]:
        """A transaction as the connection's own role, which row-level security does not limit.
        For the `/admin` routes only."""
        with self.pool.connection() as conn:
            yield conn
