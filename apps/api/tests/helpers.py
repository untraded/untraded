# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Shared by the database tests of the API."""

from __future__ import annotations

from typing import Any

import psycopg

from untraded_api.deps import token_hash


def add_user(conn: psycopg.Connection[Any], steam_id: int) -> str:
    """A user with a personal workspace, signed in: returns the session token."""
    user = conn.execute(
        "INSERT INTO app_user (steam_id, display_name) VALUES (%s, 'u') RETURNING id", (steam_id,)
    ).fetchone()
    assert user is not None
    workspace = conn.execute(
        "INSERT INTO workspace (kind, name, slug, created_by) "
        "VALUES ('personal', 'w', %s, %s) RETURNING id",
        (f"u-{steam_id}", user[0]),
    ).fetchone()
    assert workspace is not None
    role = conn.execute(
        "INSERT INTO workspace_role (workspace_id, name) VALUES (%s, 'owner') RETURNING id",
        (workspace[0],),
    ).fetchone()
    assert role is not None
    conn.execute(
        "INSERT INTO membership (workspace_id, user_id, role_id) VALUES (%s, %s, %s)",
        (workspace[0], user[0], role[0]),
    )
    token = f"token-{steam_id}"
    conn.execute(
        "SELECT open_auth_session(%s, %s, interval '1 day')", (steam_id, token_hash(token))
    )
    return token
