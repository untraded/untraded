# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""What each player agreed to (`consent`): analysis, and the research corpus.

Revision ID: 0007
Revises: 0006
"""

from __future__ import annotations

from pathlib import Path

from untraded_db.migrations.script import run_script

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

SQL = Path(__file__).with_name("0007_consent.sql")

DOWNGRADE = "DROP VIEW consent_current; DROP TABLE consent;"


def upgrade() -> None:
    run_script(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    run_script(DOWNGRADE)
