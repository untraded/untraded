# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""What each rate stands on, and which metrics can be negative (`metric_definition`).

Revision ID: 0006
Revises: 0005
"""

from __future__ import annotations

from untraded_db.migrations.script import run_script

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

UPGRADE = """
-- cases: '{rounds}' for a rate over the rounds played, else the count metrics whose sum is its
-- number of cases; empty for totals. signed: the value can be negative (K-D). The worker fills
-- both from the registry.
ALTER TABLE metric_definition
    ADD COLUMN cases  text[]  NOT NULL DEFAULT '{}',
    ADD COLUMN signed boolean NOT NULL DEFAULT false;
"""

DOWNGRADE = "ALTER TABLE metric_definition DROP COLUMN cases, DROP COLUMN signed;"


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
