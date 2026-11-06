# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Every finding of a session is kept: `advice.priority` goes past the three priorities.

Revision ID: 0014
Revises: 0013
"""

from __future__ import annotations

from untraded_db.migrations.script import run_script

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

UPGRADE = """
-- 1 to 3 are the priorities; from 4 on, the session's other findings, costliest first.
ALTER TABLE advice DROP CONSTRAINT advice_priority_check;
ALTER TABLE advice ADD CONSTRAINT advice_priority_check CHECK (priority >= 1);
"""

# The other findings have no place in the older schema: they go, with their votes (cascade).
DOWNGRADE = """
DELETE FROM advice WHERE priority > 3;
ALTER TABLE advice DROP CONSTRAINT advice_priority_check;
ALTER TABLE advice ADD CONSTRAINT advice_priority_check CHECK (priority BETWEEN 1 AND 3);
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
