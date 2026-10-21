# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The migrations, without a database (CI also applies them to PostgreSQL 16)."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.script import ScriptDirectory

from untraded_db import MIGRATIONS
from untraded_db.cli import config

ROOT = Path(__file__).parents[2]
TEST_URL = os.environ.get("UNTRADED_TEST_DATABASE_URL", "")


def test_the_initial_migration_is_the_reference_schema_of_adr_0011() -> None:
    frozen = (MIGRATIONS / "versions" / "0001_initial.sql").read_bytes()
    assert frozen == (ROOT / "docs" / "db" / "schema.sql").read_bytes()


def test_the_migrations_form_one_line_from_0001() -> None:
    scripts = ScriptDirectory.from_config(config("postgresql+psycopg://unused"))
    assert scripts.get_heads() == [scripts.get_current_head()]
    revisions = list(scripts.walk_revisions())
    assert revisions[-1].revision == "0001"
    assert revisions[-1].down_revision is None
    assert [r.revision for r in reversed(revisions)] == [
        "0001",
        "0002",
        "0003",
        "0004",
        "0005",
        "0006",
    ]


@pytest.mark.db
@pytest.mark.skipif(not TEST_URL, reason="UNTRADED_TEST_DATABASE_URL is not set")
def test_the_migrations_go_down_and_up_again() -> None:
    cfg = config(TEST_URL.replace("postgresql://", "postgresql+psycopg://", 1))
    command.downgrade(cfg, "0001")
    command.upgrade(cfg, "head")
    with psycopg.connect(TEST_URL.replace("postgresql+psycopg://", "postgresql://", 1)) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchall() == [("0006",)]
