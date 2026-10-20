# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The Untraded worker: consumes the PostgreSQL job queue (ADR 0004) and runs the untraded
library on the demos it brings."""

from __future__ import annotations

import os

from untraded_db import database_url


def conninfo() -> str:
    """psycopg connection string from UNTRADED_DATABASE_URL (SQLAlchemy form accepted)."""
    return database_url().replace("postgresql+psycopg://", "postgresql://", 1)


def store_dir() -> str:
    return os.environ.get("UNTRADED_STORE_DIR", "store")
