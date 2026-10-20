# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Database migrations of the Untraded services (ADR 0006, 0011)."""

from __future__ import annotations

import os
from pathlib import Path

MIGRATIONS = Path(__file__).parent / "migrations"
DEFAULT_URL = "postgresql+psycopg://untraded:untraded@localhost:5432/untraded"
"""The development database of compose.dev.yaml."""


def database_url() -> str:
    return os.environ.get("UNTRADED_DATABASE_URL", DEFAULT_URL)
