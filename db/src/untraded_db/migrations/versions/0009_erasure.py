# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Erasing a player: the request (account marked deleted, `erase_player` job queued).

Revision ID: 0009
Revises: 0008
"""

from __future__ import annotations

from pathlib import Path

from untraded_db.migrations.script import run_script

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

SQL = Path(__file__).with_name("0009_erasure.sql")

DOWNGRADE = "DROP FUNCTION request_my_erasure(); DROP FUNCTION request_erasure(bigint);"


def upgrade() -> None:
    run_script(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    run_script(DOWNGRADE)
