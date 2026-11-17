# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Team metrics (`untraded.metrics.team`): counts per side of a match, not per player.

A new kind of metric definition, `team`, and the table holding their values: one row per match,
side (`A` or `B`), metric, version, parameters, `key` and `sub_key`, with `cases` and `hits` (the
rate is hits ÷ cases; counts add up over matches, rates would not). Which side is a team's is
decided when read, from the roster on the match's date, so the rows never depend on a roster.
Visible like any match data (`visible_match`); the API role reads them.

The table is created empty: the worker fills it at each analysis, and `untraded-worker
backfill-team-stats` fills the matches parsed before (nothing else is recomputed). Replacing the
`kind` check only reads `metric_definition` (a few hundred rows) under its lock.

Revision ID: 0020
Revises: 0019
"""

from __future__ import annotations

from untraded_db.migrations.script import run_script

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

UPGRADE = """
SET LOCAL lock_timeout = '5s';
ALTER TABLE metric_definition DROP CONSTRAINT metric_definition_kind_check,
    ADD CONSTRAINT metric_definition_kind_check CHECK (kind IN ('value', 'table', 'team'));

CREATE TABLE team_metric_value (
    match_id    uuid NOT NULL REFERENCES match (id) ON DELETE CASCADE,
    team        char(1) NOT NULL CHECK (team IN ('A', 'B')),
    metric_id   text NOT NULL,
    version     text NOT NULL,
    params_hash text NOT NULL,           -- hash of the parameters used (defaults: 'default')
    key         text NOT NULL,
    sub_key     text NOT NULL DEFAULT '',
    cases       integer NOT NULL CHECK (cases >= 0),
    hits        integer NOT NULL CHECK (hits >= 0 AND hits <= cases),
    computed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (match_id, team, metric_id, version, params_hash, key, sub_key),
    FOREIGN KEY (metric_id, version) REFERENCES metric_definition (metric_id, version)
);

ALTER TABLE team_metric_value ENABLE ROW LEVEL SECURITY;
CREATE POLICY visible ON team_metric_value USING (visible_match(match_id));
GRANT SELECT ON team_metric_value TO untraded_api;
"""

# The team metrics' definitions go with their values: the old check refuses them.
DOWNGRADE = """
SET LOCAL lock_timeout = '5s';
DROP TABLE team_metric_value;
DELETE FROM metric_current
WHERE metric_id IN (SELECT metric_id FROM metric_definition WHERE kind = 'team');
DELETE FROM metric_definition WHERE kind = 'team';
ALTER TABLE metric_definition DROP CONSTRAINT metric_definition_kind_check,
    ADD CONSTRAINT metric_definition_kind_check CHECK (kind IN ('value', 'table'));
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
