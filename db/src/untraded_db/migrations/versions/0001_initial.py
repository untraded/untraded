# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The reference schema of ADR 0011, frozen.

Revision ID: 0001
Revises:
"""

from __future__ import annotations

from pathlib import Path

from untraded_db.migrations.script import run_script

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SQL = Path(__file__).with_name("0001_initial.sql")


def upgrade() -> None:
    run_script(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    raise NotImplementedError("the initial schema has no downgrade: drop the database instead")
