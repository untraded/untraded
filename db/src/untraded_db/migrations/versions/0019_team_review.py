# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""A team's review: comments on a round, tags on a round and playlists of rounds, each row the
team's and a match's, read by the team alone and written through functions that check the
caller's permission (cadrage équipe § 5.5, ADR 0012).

Revision ID: 0019
Revises: 0018
"""

from __future__ import annotations

from pathlib import Path

from untraded_db.migrations.script import run_script

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

SQL = Path(__file__).with_name("0019_team_review.sql")

DOWNGRADE = """
SET LOCAL lock_timeout = '5s';
DROP FUNCTION
    add_review_comment(uuid, uuid, integer, integer, text),
    edit_review_comment(uuid, uuid, text), delete_review_comment(uuid, uuid),
    set_review_tags(uuid, uuid, integer, text[]),
    create_review_playlist(uuid, text, text),
    update_review_playlist(uuid, uuid, text, text), delete_review_playlist(uuid, uuid),
    add_review_playlist_round(uuid, uuid, uuid, integer),
    remove_review_playlist_round(uuid, uuid, uuid, integer),
    order_review_playlist(uuid, uuid, uuid[], integer[]),
    review_playlist_managed(uuid, uuid), review_author(uuid),
    review_line(text, integer, integer, text), review_body(text), review_unsafe(text),
    review_round(uuid, uuid, integer), review_caller(uuid, text);
DROP TABLE review_playlist_round, review_playlist, review_tag, review_comment;
DROP FUNCTION review_readable(uuid, uuid);
"""


def upgrade() -> None:
    run_script(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    run_script(DOWNGRADE)
