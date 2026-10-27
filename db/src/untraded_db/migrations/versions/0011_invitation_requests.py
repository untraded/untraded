# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Invitation requests: a Steam account that is not invited asks for an invitation, and the
admin invites it or dismisses the request.

Revision ID: 0011
Revises: 0010
"""

from __future__ import annotations

from pathlib import Path

from untraded_db.migrations.script import run_script

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

SQL = Path(__file__).with_name("0011_invitation_requests.sql")

DOWNGRADE = """
DROP FUNCTION request_invitation(bigint, text);
DROP TABLE invitation_request;
"""


def upgrade() -> None:
    run_script(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    run_script(DOWNGRADE)
