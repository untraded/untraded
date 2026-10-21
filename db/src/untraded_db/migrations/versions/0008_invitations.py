# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Invitations, the account created at the first sign-in, and the player's own consent and
source.

Revision ID: 0008
Revises: 0007
"""

from __future__ import annotations

from pathlib import Path

from untraded_db.migrations.script import run_script

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

SQL = Path(__file__).with_name("0008_invitations.sql")

DOWNGRADE = """
REVOKE INSERT ON consent FROM untraded_api;
DROP FUNCTION my_source(), set_my_source(uuid, bytea, text), pause_my_sources();
CREATE OR REPLACE FUNCTION open_auth_session(steam bigint, token bytea, ttl interval)
RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
    found uuid;
BEGIN
    SELECT id INTO found FROM app_user WHERE steam_id = steam AND deleted_at IS NULL;
    IF found IS NOT NULL THEN
        INSERT INTO auth_session (token_hash, user_id, expires_at)
        VALUES (token, found, now() + ttl);
    END IF;
    RETURN found;
END;
$$;
DROP TABLE invitation;
"""


def upgrade() -> None:
    run_script(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    run_script(DOWNGRADE)
