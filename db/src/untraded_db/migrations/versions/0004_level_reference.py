# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""References by level, and which reference a session report used.

Revision ID: 0004
Revises: 0003
"""

from __future__ import annotations

from pathlib import Path

from untraded_db.migrations.script import run_script

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

SQL = Path(__file__).with_name("0004_level_reference.sql")

DOWNGRADE = """
ALTER TABLE play_session DROP COLUMN reference_kind, DROP COLUMN reference_level_low,
    DROP COLUMN reference_level_high;
DROP TABLE level_reference;
"""


def upgrade() -> None:
    run_script(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    run_script(DOWNGRADE)
