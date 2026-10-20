# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Match end times, sign-in sessions, play sessions and their report, the API role.

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

from pathlib import Path

from untraded_db.migrations.script import run_script

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

SQL = Path(__file__).with_name("0002_sessions.sql")

DOWNGRADE = """
DROP TABLE play_session_metric, play_session_match, play_session;
DROP FUNCTION own_player(bigint);
DROP TABLE auth_session;
DROP FUNCTION open_auth_session(bigint, bytea, interval), auth_session_user(bytea),
    close_auth_session(bytea);
ALTER VIEW metric_wide_current RESET (security_invoker);
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM untraded_api;
REVOKE USAGE ON SCHEMA public FROM untraded_api;
ALTER TABLE match DROP COLUMN ended_at;
"""
"""The role itself stays: roles belong to the whole PostgreSQL cluster."""


def upgrade() -> None:
    run_script(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    run_script(DOWNGRADE)
