# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The reference schema of ADR 0011, frozen.

Revision ID: 0001
Revises:
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SQL = Path(__file__).with_name("0001_initial.sql")


def upgrade() -> None:
    # Run as one script through the driver: SQLAlchemy would read `:name` and `%` in it as
    # parameters (casts such as `::uuid`, `format('%I', ...)`).
    connection = op.get_bind().connection.dbapi_connection
    if connection is None:
        raise RuntimeError("no DBAPI connection")
    cursor = connection.cursor()
    try:
        cursor.execute(SQL.read_text(encoding="utf-8"))
    finally:
        cursor.close()


def downgrade() -> None:
    raise NotImplementedError("the initial schema has no downgrade: drop the database instead")
