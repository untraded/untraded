# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Demos sent by players: why an upload was refused, and the functions the API records and lists
them with.

Revision ID: 0010
Revises: 0009
"""

from __future__ import annotations

from pathlib import Path

from untraded_db.migrations.script import run_script

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

SQL = Path(__file__).with_name("0010_uploads.sql")

DOWNGRADE = """
DROP FUNCTION my_uploads(integer);
DROP FUNCTION add_my_upload(uuid, text, match_mode, timestamptz, integer, integer);
DROP FUNCTION my_upload_refusal(integer, integer);
ALTER TABLE match_source DROP COLUMN rejected;
"""


def upgrade() -> None:
    run_script(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    run_script(DOWNGRADE)
