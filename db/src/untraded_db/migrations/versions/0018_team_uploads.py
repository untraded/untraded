# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Demos a team sends for itself: a source owned by the workspace, who sent each upload, the
functions the API records and lists them with, and a team's deletion that takes its matches.

Revision ID: 0018
Revises: 0017
"""

from __future__ import annotations

from pathlib import Path

from untraded_db.migrations.script import run_script

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

SQL = Path(__file__).with_name("0018_team_uploads.sql")

# The teams' sources go first (their matches then count for nobody, as an erased player's upload):
# `user_id` cannot become mandatory again while they exist.
DOWNGRADE = """
SET LOCAL lock_timeout = '5s';
DELETE FROM job WHERE kind = 'drop_team_matches';
DROP FUNCTION team_uploads(uuid, integer),
    add_team_upload(uuid, uuid, text, match_mode, timestamptz, integer, integer),
    team_upload_refusal(uuid, integer, integer);
DROP TABLE upload_sender;
DROP POLICY visible ON match_source;
ALTER TABLE match_source DISABLE ROW LEVEL SECURITY;
DELETE FROM ingest_source WHERE workspace_id IS NOT NULL;
DROP INDEX ingest_source_workspace;
ALTER TABLE ingest_source DROP CONSTRAINT ingest_source_workspace_kind,
    DROP CONSTRAINT ingest_source_one_owner,
    DROP COLUMN workspace_id;
ALTER TABLE ingest_source ALTER COLUMN user_id SET NOT NULL;

CREATE OR REPLACE FUNCTION delete_team(w uuid) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    PERFORM team_caller(w);
    IF NOT has_permission(w, 'team.delete') THEN
        PERFORM team_refuse('forbidden');
    END IF;
    PERFORM 1 FROM app_user u
    WHERE u.id IN (SELECT user_id FROM membership WHERE workspace_id = w)
    ORDER BY u.id
    FOR SHARE;
    DELETE FROM workspace WHERE id = w AND kind = 'team';
END;
$$;
"""


def upgrade() -> None:
    run_script(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    run_script(DOWNGRADE)
