# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The Untraded Rating in the wide view of the current values.

Revision ID: 0012
Revises: 0011
"""

from __future__ import annotations

from pathlib import Path

from untraded_db.migrations.script import run_script

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

SQL = Path(__file__).with_name("0012_untraded_rating.sql")

# A view cannot lose a column in place: it is recreated as migration 0001 left it.
DOWNGRADE = """
DROP VIEW metric_wide_current;
CREATE VIEW metric_wide_current WITH (security_invoker = true) AS
SELECT v.match_id,
       v.steam_id,
       v.scope,
       max(v.value) FILTER (WHERE v.metric_id = 'base.kills')  AS kills,
       max(v.value) FILTER (WHERE v.metric_id = 'base.deaths') AS deaths,
       max(v.value) FILTER (WHERE v.metric_id = 'base.adr')    AS adr,
       max(v.value) FILTER (WHERE v.metric_id = 'base.kast')   AS kast,
       max(v.value) FILTER (WHERE v.metric_id = 'rating.hltv1') AS hltv1,
       max(v.value) FILTER (WHERE v.metric_id = 'trade.untraded_deaths') AS untraded_deaths
FROM metric_value v
JOIN metric_current c USING (metric_id, version)
WHERE v.params_hash = 'default'
GROUP BY v.match_id, v.steam_id, v.scope;
GRANT SELECT ON metric_wide_current TO untraded_api;
"""


def upgrade() -> None:
    run_script(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    run_script(DOWNGRADE)
