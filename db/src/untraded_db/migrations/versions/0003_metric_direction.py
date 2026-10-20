# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Which way is an improvement for each metric (`metric_definition.better`).

Revision ID: 0003
Revises: 0002
"""

from __future__ import annotations

from untraded_db.migrations.script import run_script

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

UPGRADE = """
-- higher: more is better (kills); lower: less is better (deaths); neutral: a style, not a
-- level (opening attempts). The worker fills it from the registry.
ALTER TABLE metric_definition
    ADD COLUMN better text NOT NULL DEFAULT 'neutral'
    CHECK (better IN ('higher', 'lower', 'neutral'));
"""

DOWNGRADE = "ALTER TABLE metric_definition DROP COLUMN better;"


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
