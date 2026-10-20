# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Running a SQL script from a migration."""

from __future__ import annotations

from alembic import op


def run_script(sql: str) -> None:
    """Runs `sql` as one script through the driver: SQLAlchemy would read `:name` and `%` in it
    as parameters (casts such as `::uuid`, `format('%I', ...)`)."""
    connection = op.get_bind().connection.dbapi_connection
    if connection is None:
        raise RuntimeError("no DBAPI connection")
    cursor = connection.cursor()
    try:
        cursor.execute(sql)
    finally:
        cursor.close()
