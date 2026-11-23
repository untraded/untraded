# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The demo keeps its age: its dates move forward together, and nothing else ever moves."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import polars as pl
import psycopg
import pytest

from untraded import demo, demo_team, fixtures
from untraded_worker import demo_dates
from untraded_worker.demo import import_demo
from untraded_worker.demo_team import import_demo_team
from untraded_worker.store import LocalStore

FIXTURES = Path(__file__).parents[3] / "packages/untraded-py/tests/fixtures"
REAL = 76561199000000000
TODAY = dt.datetime.now(dt.UTC).date()


@pytest.fixture
def db(conn: psycopg.Connection[Any]) -> psycopg.Connection[Any]:
    conn.execute("TRUNCATE match, player, app_user, invitation, metric_definition, job CASCADE")
    conn.execute("TRUNCATE workspace CASCADE")
    return conn


def _load(
    db: psycopg.Connection[Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> LocalStore:
    matches = []
    for day, name in enumerate(("premier-half", "premier-abandon"), start=1):
        tables = fixtures.read(FIXTURES / name)
        ids = tables["player"]["steamid"].to_list()
        tables = fixtures.replace_players(tables, {i: REAL + i for i in ids})
        tables["match"] = tables["match"].with_columns(
            pl.lit(dt.date(2026, 10, day)).alias("played_at")
        )
        matches.append(tables)
    end = dt.datetime.combine(TODAY - dt.timedelta(days=20), dt.time(12), tzinfo=dt.UTC)
    demo.write(demo.build(matches, REAL + 1, end), tmp_path / "demo")
    monkeypatch.setattr(demo_team, "MODES", (("premier", "roster"), ("scrim", "team")))
    demo_team.write(demo_team.build(demo.read(tmp_path / "demo")), tmp_path / "team")
    store = LocalStore(tmp_path / "store")
    import_demo(
        db, store, tmp_path / "demo", steam_id=demo.PROTAGONIST, name="Demo", consent_version="2"
    )
    import_demo_team(
        db, store, tmp_path / "team", owner_steam_id=demo.PROTAGONIST, consent_version="2"
    )
    return store


def _real_rows(db: psycopg.Connection[Any]) -> tuple[Any, ...]:
    """A real player's match (served by Valve) and session, which must never move."""
    match = db.execute(
        "INSERT INTO match (mode, status, played_at, ended_at) "
        "VALUES ('premier', 'ready', '2026-09-01 20:00Z', '2026-09-01 20:40Z') RETURNING id"
    ).fetchone()
    assert match is not None
    db.execute(
        "INSERT INTO match_source (match_id, kind, external_id) VALUES (%s, 'valve_bot', 'x')",
        (match[0],),
    )
    db.execute("INSERT INTO player (steam_id) VALUES (%s)", (REAL + 99,))
    db.execute(
        "INSERT INTO play_session (steam_id, started_at, ended_at, matches, rounds, "
        "reference_from, reference_to, reference_matches, reference_rounds, enough, params) "
        "VALUES (%s, '2026-09-01 20:00Z', '2026-09-01 20:40Z', 1, 24, '2026-08-02', "
        "'2026-08-31', 0, 0, false, '{}')",
        (REAL + 99,),
    )
    return match[0], _snapshot_real(db, match[0])


def _snapshot_real(db: psycopg.Connection[Any], match: Any) -> tuple[Any, ...]:
    row = db.execute(
        "SELECT m.played_at, m.ended_at, ms.received_at, s.started_at, s.reference_to "
        "FROM match m JOIN match_source ms ON ms.match_id = m.id, play_session s "
        "WHERE m.id = %s AND s.steam_id = %s",
        (match, REAL + 99),
    ).fetchone()
    assert row is not None
    return tuple(row)


def _demo_dates(db: psycopg.Connection[Any]) -> dict[str, Any]:
    return dict(
        db.execute(
            "SELECT m.sha256, m.played_at FROM match m WHERE m.sha256 IS NOT NULL"
        ).fetchall()
    )


@pytest.mark.db
def test_the_demo_moves_together_and_nothing_else(
    db: psycopg.Connection[Any], conninfo: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _load(db, tmp_path, monkeypatch)
    real, real_before = _real_rows(db)
    before = _demo_dates(db)
    comments_before = db.execute("SELECT min(created_at) FROM review_comment").fetchone()
    assert comments_before is not None

    # The demo user's sessions are queued: the shift waits for them.
    assert db.execute("SELECT count(*) FROM job WHERE kind = 'session'").fetchone() != (0,)
    assert demo_dates.shift(db, TODAY) == 0
    assert _demo_dates(db) == before
    db.execute("UPDATE job SET status = 'done' WHERE kind = 'session'")

    # An import running elsewhere holds the lock: the shift waits too.
    with psycopg.connect(conninfo, autocommit=True) as other, demo_dates.demo_lock(other):
        assert demo_dates.shift(db, TODAY) == 0

    last = max(v for v in before.values()).astimezone(dt.UTC).date()
    days = (TODAY - dt.timedelta(days=1) - last).days
    assert days > 0
    # Two sessions exactly `days` apart: the first moves onto the second's start.
    for start in ("2026-10-01 19:00Z", f"{dt.date(2026, 10, 1) + dt.timedelta(days=days)} 19:00Z"):
        db.execute(
            "INSERT INTO play_session (steam_id, started_at, ended_at, matches, rounds, "
            "reference_from, reference_to, reference_matches, reference_rounds, enough, "
            "params) VALUES (%s, %s, %s::timestamptz + interval '1 hour', 1, 24, "
            "%s::date - 30, %s::date - 1, 0, 0, false, '{}')",
            (demo.PROTAGONIST, start, start, start[:10], start[:10]),
        )
    sessions_before = db.execute(
        "SELECT started_at, reference_from FROM play_session WHERE steam_id <> %s "
        "ORDER BY started_at",
        (REAL + 99,),
    ).fetchall()
    assert len(sessions_before) >= 2
    assert demo_dates.shift(db, TODAY) == days
    after = _demo_dates(db)
    assert after == {k: v + dt.timedelta(days=days) for k, v in before.items()}
    assert max(after.values()).astimezone(dt.UTC).date() == TODAY - dt.timedelta(days=1)
    sessions_after = db.execute(
        "SELECT started_at, reference_from FROM play_session WHERE steam_id <> %s "
        "ORDER BY started_at",
        (REAL + 99,),
    ).fetchall()
    assert sessions_after == [
        (s + dt.timedelta(days=days), r + dt.timedelta(days=days)) for s, r in sessions_before
    ]
    moved = db.execute(
        "SELECT min(created_at), max(created_at) <= now(), bool_and(edited_at IS NULL) "
        "FROM review_comment"
    ).fetchone()
    assert moved is not None
    assert moved[0] > comments_before[0]
    assert moved[1:] == (True, True)  # never past now, an unedited comment stays unedited
    received = db.execute(
        "SELECT bool_and(ms.received_at <= now()) FROM match_source ms "
        "JOIN match m ON m.id = ms.match_id WHERE m.sha256 IS NOT NULL"
    ).fetchone()
    assert received == (True,)
    assert _snapshot_real(db, real) == real_before
    # Already up to date: nothing moves.
    assert demo_dates.shift(db, TODAY) == 0
    assert demo_dates.current_offset(db, store) == dt.timedelta(days=days)


@pytest.mark.db
def test_a_match_brought_back_joins_the_moved_demo(
    db: psycopg.Connection[Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _load(db, tmp_path, monkeypatch)
    db.execute("UPDATE job SET status = 'done'")
    before = _demo_dates(db)
    days = demo_dates.shift(db, TODAY)
    assert days > 0
    gone = next(iter(demo.read(tmp_path / "demo"))).match_id
    db.execute("DELETE FROM match WHERE sha256 = %s", (gone,))
    import_demo(
        db, store, tmp_path / "demo", steam_id=demo.PROTAGONIST, name="Demo", consent_version="2"
    )
    assert _demo_dates(db)[gone] == before[gone] + dt.timedelta(days=days)


@pytest.mark.db
def test_a_real_players_data_stops_the_shift(
    db: psycopg.Connection[Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _load(db, tmp_path, monkeypatch)
    db.execute("UPDATE job SET status = 'done'")
    before = _demo_dates(db)
    # A demo match that Valve served too (impossible in practice): it is a real one.
    db.execute(
        "INSERT INTO match_source (match_id, kind, external_id) "
        "SELECT id, 'valve_bot', 'real' FROM match WHERE sha256 IS NOT NULL LIMIT 1"
    )
    assert demo_dates.shift(db, TODAY) == 0
    assert _demo_dates(db) == before
    db.execute("DELETE FROM match_source WHERE external_id = 'real'")
    # A real player joins the demo's team: its matches are no longer the demo's alone.
    db.execute("INSERT INTO invitation (steam_id, display_name) VALUES (%s, 'x')", (REAL + 50,))
    db.execute("SELECT open_auth_session(%s, %s, interval '1 minute')", (REAL + 50, b"t" * 32))
    db.execute(
        "INSERT INTO membership (workspace_id, user_id, role_id) "
        "SELECT w.id, u.id, r.id FROM workspace w JOIN workspace_role r ON r.workspace_id = w.id "
        "AND r.name = 'viewer', app_user u WHERE w.slug = %s AND u.steam_id = %s",
        (demo_team.TEAM_SLUG, REAL + 50),
    )
    assert demo_dates.shift(db, TODAY) == 0
    assert _demo_dates(db) == before
