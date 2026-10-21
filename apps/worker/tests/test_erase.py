# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Erasing a player (`erase_player`), against PostgreSQL."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import psycopg
import pytest
from psycopg.types.json import Jsonb

from untraded_worker.erase import erase_player
from untraded_worker.store import LocalStore

pytestmark = pytest.mark.db
GONE, OTHER, STRANGER = 76561198000000011, 76561198000000012, 76561198000000013


@pytest.fixture
def db(conn: psycopg.Connection[Any]) -> psycopg.Connection[Any]:
    conn.execute("TRUNCATE match, app_user, player, invitation CASCADE")
    return conn


def user(db: psycopg.Connection[Any], steam_id: int) -> uuid.UUID:
    row = db.execute(
        "INSERT INTO app_user (steam_id, display_name) VALUES (%s, 'u') RETURNING id", (steam_id,)
    ).fetchone()
    assert row is not None
    space = db.execute(
        "INSERT INTO workspace (kind, name, slug, created_by) VALUES ('personal', 'w', %s, %s) "
        "RETURNING id",
        (f"u-{steam_id}", row[0]),
    ).fetchone()
    assert space is not None
    role = db.execute(
        "INSERT INTO workspace_role (workspace_id, name) VALUES (%s, 'owner') RETURNING id",
        (space[0],),
    ).fetchone()
    assert role is not None
    db.execute(
        "INSERT INTO membership (workspace_id, user_id, role_id) VALUES (%s, %s, %s)",
        (space[0], row[0], role[0]),
    )
    db.execute(
        "INSERT INTO consent (user_id, text_version, analysis, research_corpus, recorded_by) "
        "VALUES (%s, '1', true, true, 'test')",
        (row[0],),
    )
    db.execute(
        "INSERT INTO ingest_source (user_id, kind, secret) VALUES (%s, 'valve_bot', 'x')",
        (row[0],),
    )
    return uuid.UUID(str(row[0]))


def match(
    db: psycopg.Connection[Any], store: LocalStore, players: list[int], demo: str
) -> uuid.UUID:
    row = db.execute(
        "INSERT INTO match (mode, status, demo_key) VALUES ('premier', 'ready', %s) RETURNING id",
        (demo,),
    ).fetchone()
    assert row is not None
    match_id = uuid.UUID(str(row[0]))
    prefix = f"matches/{match_id}"
    db.execute("UPDATE match SET parquet_prefix = %s WHERE id = %s", (prefix, match_id))
    for steam_id in players:
        db.execute(
            "INSERT INTO player (steam_id, last_name) VALUES (%s, 'p') ON CONFLICT DO NOTHING",
            (steam_id,),
        )
        db.execute(
            "INSERT INTO match_player (match_id, steam_id, team, name, rounds_on_team) "
            "VALUES (%s, %s, 'A', 'p', 5)",
            (match_id, steam_id),
        )
    store.path(f"{prefix}/round.parquet").parent.mkdir(parents=True, exist_ok=True)
    store.path(f"{prefix}/round.parquet").write_bytes(b"parquet")
    store.path(demo).parent.mkdir(parents=True, exist_ok=True)
    store.path(demo).write_bytes(b"demo")
    return match_id


def test_a_player_is_erased_and_shared_matches_stay(
    db: psycopg.Connection[Any], tmp_path: Path
) -> None:
    store = LocalStore(tmp_path)
    gone = user(db, GONE)
    user(db, OTHER)
    alone = match(db, store, [GONE, STRANGER], "demos/a.dem.bz2")  # no other user: erased
    shared = match(db, store, [GONE, OTHER], "demos/b.dem.bz2")  # another user: kept
    db.execute(
        "INSERT INTO play_session (steam_id, started_at, ended_at, matches, rounds, "
        "reference_from, reference_to, reference_matches, reference_rounds, enough, params) "
        "VALUES (%s, now(), now(), 1, 5, current_date, current_date, 0, 0, false, %s)",
        (GONE, Jsonb({})),
    )
    db.execute("SELECT request_erasure(%s)", (GONE,))
    assert db.execute("SELECT kind FROM job").fetchall() == [("erase_player",)]
    assert db.execute(
        "SELECT deleted_at IS NOT NULL FROM app_user WHERE id = %s", (gone,)
    ).fetchone() == (True,)

    erased = erase_player(db, store, GONE)
    assert erased.matches == 1
    assert erased.files == 2  # the Parquet and the demo of the match only they brought

    assert db.execute("SELECT id FROM match ORDER BY created_at").fetchall() == [(shared,)]
    assert not store.path(f"matches/{alone}").exists()
    assert not store.exists("demos/a.dem.bz2")
    assert store.exists("demos/b.dem.bz2")
    assert store.path(f"matches/{shared}/round.parquet").exists()
    for table in ("app_user", "consent", "ingest_source", "play_session", "membership"):
        count = db.execute(
            f"SELECT count(*) FROM {table} t "
            + (
                "JOIN app_user u ON u.id = t.user_id WHERE u.steam_id = %s"
                if table in ("consent", "ingest_source", "membership")
                else "WHERE t.steam_id = %s"
            ),
            (GONE,),
        ).fetchone()
        assert count == (0,), table
    # In the shared match, they are a player like any other, out of the level references.
    assert db.execute(
        "SELECT benchmark_opt_out FROM player WHERE steam_id = %s", (GONE,)
    ).fetchone() == (True,)
    assert db.execute("SELECT count(*) FROM workspace").fetchone() == (1,)  # OTHER's

    # Again: nothing left to do.
    assert erase_player(db, store, GONE).matches == 0


def test_an_invitation_alone_is_withdrawn(db: psycopg.Connection[Any], tmp_path: Path) -> None:
    db.execute("INSERT INTO invitation (steam_id, display_name) VALUES (%s, 'i')", (GONE,))
    db.execute("SELECT request_erasure(%s)", (GONE,))
    erase_player(db, LocalStore(tmp_path), GONE)
    assert db.execute("SELECT count(*) FROM invitation").fetchone() == (0,)
