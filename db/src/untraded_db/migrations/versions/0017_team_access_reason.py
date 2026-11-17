# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""A new reason a workspace sees a match: `team`, a match the team sent itself (migration 0018).

On its own: PostgreSQL cannot use an enum value in the transaction that adds it, and each
migration runs in its own transaction (`transaction_per_migration`). Adding a value only changes
the catalog: no table is rewritten.

The downgrade rebuilds the type without it, after removing the rows that use it: the worker adds
them back from the sources (`untraded-worker refresh-access`) once upgraded again.

Revision ID: 0017
Revises: 0016
"""

from __future__ import annotations

from untraded_db.migrations.script import run_script

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

UPGRADE = """
SET LOCAL lock_timeout = '5s';
ALTER TYPE access_reason ADD VALUE IF NOT EXISTS 'team' BEFORE 'roster';
"""

DOWNGRADE = """
SET LOCAL lock_timeout = '5s';
DELETE FROM workspace_match WHERE reason::text = 'team';
ALTER TYPE access_reason RENAME TO access_reason_old;
CREATE TYPE access_reason AS ENUM ('own', 'shared', 'roster');
ALTER TABLE workspace_match
    ALTER COLUMN reason TYPE access_reason USING reason::text::access_reason;
DROP TYPE access_reason_old;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
