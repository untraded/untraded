# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The spread of a reference: its 10th and 90th percentiles over per-match values.

Four nullable columns, no default and no rewrite: adding a nullable column without a default
only changes the catalog, so the lock is held for an instant. `lock_timeout` makes the migration
give up (and fail, to be run again) rather than queue behind a long transaction and block the
API and the worker behind it.

Revision ID: 0015
Revises: 0014
"""

from __future__ import annotations

from untraded_db.migrations.script import run_script

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

UPGRADE = """
SET LOCAL lock_timeout = '5s';
ALTER TABLE play_session_metric
    ADD COLUMN reference_p10 double precision,   -- null: the reference is not shown, or its
    ADD COLUMN reference_p90 double precision;   -- spread rests on too few matches
ALTER TABLE level_reference
    ADD COLUMN p10 double precision,             -- 10th and 90th percentiles of the per-match
    ADD COLUMN p90 double precision;             -- values of the pooled rows (totals per round)
"""

DOWNGRADE = """
SET LOCAL lock_timeout = '5s';
ALTER TABLE play_session_metric DROP COLUMN reference_p10, DROP COLUMN reference_p90;
ALTER TABLE level_reference DROP COLUMN p10, DROP COLUMN p90;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
