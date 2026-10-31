# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""A flash can blind a bot: `blind.victim` is null then, as `kill.victim` already is.

Revision ID: 0013
Revises: 0012
"""

from __future__ import annotations

from untraded_db.migrations.script import run_script

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

UPGRADE = """
-- null for a bot nobody controls (the parser has no steamid for it), like kill.victim.
ALTER TABLE blind ALTER COLUMN victim DROP NOT NULL;
"""

# The bots' blinds have no place in the older schema: they go.
DOWNGRADE = """
DELETE FROM blind WHERE victim IS NULL;
ALTER TABLE blind ALTER COLUMN victim SET NOT NULL;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
