# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Advice tied to its session report, and the API's right to record feedback.

Revision ID: 0005
Revises: 0004
"""

from __future__ import annotations

from untraded_db.migrations.script import run_script

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

UPGRADE = """
-- A session's priorities go with its report: recomputing the session replaces them.
ALTER TABLE advice
    ADD COLUMN session_id     uuid REFERENCES play_session (id) ON DELETE CASCADE,
    ADD COLUMN cost           double precision NOT NULL DEFAULT 0,
    ADD COLUMN events         integer NOT NULL DEFAULT 0,
    ADD COLUMN rounds_touched integer NOT NULL DEFAULT 0,
    ADD COLUMN rounds_lost    integer NOT NULL DEFAULT 0;
CREATE INDEX advice_session ON advice (session_id, priority);

-- 👍/👎: the API records the signed-in user's own vote (row-level security: user_id is theirs).
GRANT INSERT, UPDATE, DELETE ON advice_feedback TO untraded_api;
"""

DOWNGRADE = """
REVOKE INSERT, UPDATE, DELETE ON advice_feedback FROM untraded_api;
DROP INDEX advice_session;
ALTER TABLE advice DROP COLUMN session_id, DROP COLUMN cost, DROP COLUMN events,
    DROP COLUMN rounds_touched, DROP COLUMN rounds_lost;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
