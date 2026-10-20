# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The migrations, without a database (CI also applies them to PostgreSQL 16)."""

from __future__ import annotations

from pathlib import Path

from alembic.script import ScriptDirectory

from untraded_db import MIGRATIONS
from untraded_db.cli import config

ROOT = Path(__file__).parents[2]


def test_the_initial_migration_is_the_reference_schema_of_adr_0011() -> None:
    frozen = (MIGRATIONS / "versions" / "0001_initial.sql").read_bytes()
    assert frozen == (ROOT / "docs" / "db" / "schema.sql").read_bytes()


def test_the_migrations_form_one_line_from_0001() -> None:
    scripts = ScriptDirectory.from_config(config("postgresql+psycopg://unused"))
    assert scripts.get_heads() == [scripts.get_current_head()]
    revisions = list(scripts.walk_revisions())
    assert revisions[-1].revision == "0001"
    assert revisions[-1].down_revision is None
