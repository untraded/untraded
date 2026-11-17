# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Which teams see a match (`refresh_access`, `refresh_team_access`) and how an erasure leaves
its teams, against PostgreSQL. The `premier-half` fixture has players 1 to 5 on side A and 6 to
10 on side B."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import psycopg
import pytest

from untraded_worker import queue, team_access
from untraded_worker.analysis import Analysis
from untraded_worker.erase import EraseError, erase_player
from untraded_worker.load import load_match, refresh_access
from untraded_worker.runner import Worker
from untraded_worker.store import LocalStore

pytestmark = pytest.mark.db


@pytest.fixture
def db(conn: psycopg.Connection[Any]) -> psycopg.Connection[Any]:
    conn.execute(
        "TRUNCATE match, player, app_user, workspace, metric_definition, metric_current, "
        "invitation CASCADE"
    )
    return conn


def _user(db: psycopg.Connection[Any], steam_id: int, *, consents: bool = True) -> uuid.UUID:
    row = db.execute(
        "INSERT INTO app_user (steam_id, display_name) VALUES (%s, 'u') RETURNING id", (steam_id,)
    ).fetchone()
    assert row is not None
    db.execute(
        "INSERT INTO workspace (kind, name, slug, created_by) VALUES ('personal', 'w', %s, %s)",
        (f"u-{steam_id}", row[0]),
    )
    db.execute(
        "INSERT INTO consent (user_id, text_version, analysis, research_corpus, recorded_by) "
        "VALUES (%s, '2', %s, false, 'test')",
        (row[0], consents),
    )
    return uuid.UUID(str(row[0]))


def _team(db: psycopg.Connection[Any], owner: int, roster: list[int]) -> uuid.UUID:
    """A team as `create_team` makes it, with `roster` (registered players) on its roster since
    2020."""
    row = db.execute("SELECT create_team('Team', 'team', %s)", (owner,)).fetchone()
    assert row is not None
    team = uuid.UUID(str(row[0]))
    for steam_id in roster:
        db.execute(
            "INSERT INTO roster_member (roster_id, steam_id, valid_from) "
            "SELECT id, %s, '2020-01-01' FROM roster WHERE workspace_id = %s",
            (steam_id, team),
        )
    return team


def _match(db: psycopg.Connection[Any], analysis: Analysis) -> uuid.UUID:
    row = db.execute(
        "INSERT INTO match (mode, played_at, status) VALUES ('premier', now(), 'ready') "
        "RETURNING id"
    ).fetchone()
    assert row is not None
    match_id = uuid.UUID(str(row[0]))
    db.execute(
        "INSERT INTO match_source (match_id, kind, external_id) VALUES (%s, 'valve_bot', %s)",
        (match_id, str(match_id)),
    )
    load_match(db, match_id, analysis)
    return match_id


def _reason(db: psycopg.Connection[Any], team: uuid.UUID, match_id: uuid.UUID) -> str | None:
    row = db.execute(
        "SELECT reason::text FROM workspace_match WHERE workspace_id = %s AND match_id = %s",
        (team, match_id),
    ).fetchone()
    return str(row[0]) if row else None


def test_three_roster_players_on_the_same_side_open_the_match(
    db: psycopg.Connection[Any], analysis: Analysis
) -> None:
    for steam_id in (1, 2, 3, 6):
        _user(db, steam_id)
    match_id = _match(db, analysis)
    team = _team(db, 1, [1, 2, 6])
    refresh_access(db, match_id)
    assert _reason(db, team, match_id) is None  # 2 on side A, 1 on side B: they only met
    db.execute(
        "INSERT INTO roster_member (roster_id, steam_id, valid_from) "
        "SELECT id, 3, '2020-01-01' FROM roster WHERE workspace_id = %s",
        (team,),
    )
    refresh_access(db, match_id)
    assert _reason(db, team, match_id) == "roster"


def test_a_player_without_consent_counts_for_no_roster_and_shares_nothing(
    db: psycopg.Connection[Any], analysis: Analysis
) -> None:
    _user(db, 1)
    _user(db, 2)
    third = _user(db, 3, consents=False)
    match_id = _match(db, analysis)
    team = _team(db, 1, [1, 2, 3])
    refresh_access(db, match_id)
    assert _reason(db, team, match_id) is None
    db.execute(
        "INSERT INTO workspace_player (workspace_id, steam_id, share_solo) VALUES (%s, 3, true)",
        (team,),
    )
    refresh_access(db, match_id)
    assert _reason(db, team, match_id) is None
    db.execute(
        "INSERT INTO consent (user_id, text_version, analysis, research_corpus, recorded_by) "
        "VALUES (%s, '2', true, false, 'test')",
        (third,),
    )
    refresh_access(db, match_id)
    assert _reason(db, team, match_id) == "roster"


def test_a_roster_change_queues_the_job_that_recomputes_the_access(
    db: psycopg.Connection[Any], analysis: Analysis
) -> None:
    owner = _user(db, 1)
    for steam_id in (2, 3):
        _user(db, steam_id)
    match_id = _match(db, analysis)
    team = _team(db, 1, [1, 2])
    refresh_access(db, match_id)
    assert _reason(db, team, match_id) is None
    # Player 3 joins (as the database functions would let them), then goes on the roster.
    db.execute(
        "INSERT INTO membership (workspace_id, user_id, role_id) "
        "SELECT %s, u.id, r.id FROM app_user u, workspace_role r "
        "WHERE u.steam_id = 3 AND r.workspace_id = %s AND r.name = 'player'",
        (team, team),
    )
    with db.transaction():
        db.execute("SELECT set_config('app.user_id', %s, true)", (str(owner),))
        db.execute("SELECT set_roster_member(%s, 3, 'starter')", (team,))
    jobs = db.execute("SELECT kind, payload->>'steam_id' FROM job").fetchall()
    assert jobs == [("refresh_team_access", "3")]
    worker = Worker("", {"refresh_team_access": team_access.refresh_team_access})
    assert worker.step(db)
    assert _reason(db, team, match_id) == "roster"
    assert db.execute("SELECT status::text FROM job").fetchall() == [("done",)]


def test_a_full_refresh_recomputes_every_match(
    db: psycopg.Connection[Any], analysis: Analysis
) -> None:
    for steam_id in (1, 2, 3):
        _user(db, steam_id)
    match_id = _match(db, analysis)
    team = _team(db, 1, [1, 2, 3])
    assert _reason(db, team, match_id) is None  # loaded, never refreshed
    assert team_access.refresh_all(db) == 1
    assert _reason(db, team, match_id) == "roster"
    assert team_access.refresh_player(db, 1) == 1


def test_an_erased_player_leaves_the_roster_and_the_team_loses_what_they_opened(
    db: psycopg.Connection[Any], analysis: Analysis, tmp_path: Path
) -> None:
    for steam_id in (1, 2, 3):
        _user(db, steam_id)
    match_id = _match(db, analysis)
    team = _team(db, 1, [1, 2, 3])
    db.execute(
        "INSERT INTO membership (workspace_id, user_id, role_id) "
        "SELECT %s, u.id, r.id FROM app_user u, workspace_role r "
        "WHERE u.steam_id = 3 AND r.workspace_id = %s AND r.name = 'player'",
        (team, team),
    )
    db.execute(
        "INSERT INTO workspace_player (workspace_id, steam_id, share_solo) VALUES (%s, 3, true)",
        (team,),
    )
    refresh_access(db, match_id)
    assert _reason(db, team, match_id) == "roster"
    queue.enqueue(db, "refresh_team_access", {"steam_id": "3"})

    erase_player(db, LocalStore(tmp_path), 3)
    for table in ("roster_member", "workspace_player"):
        count = db.execute(f"SELECT count(*) FROM {table} WHERE steam_id = 3").fetchone()
        assert count == (0,), table
    assert db.execute(
        "SELECT count(*) FROM membership WHERE workspace_id = %s", (team,)
    ).fetchone() == (1,)
    assert _reason(db, team, match_id) is None  # the match stays (others' match), not the team's
    assert db.execute("SELECT count(*) FROM job WHERE kind = 'refresh_team_access'").fetchone() == (
        0,
    )


def test_an_owner_is_not_erased(db: psycopg.Connection[Any], tmp_path: Path) -> None:
    _user(db, 1)
    _team(db, 1, [])
    with pytest.raises(EraseError):
        erase_player(db, LocalStore(tmp_path), 1)
    assert db.execute("SELECT count(*) FROM app_user WHERE steam_id = 1").fetchone() == (1,)
