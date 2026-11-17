# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""`untraded-worker import-demo`: the demo user and its matches, loaded once."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import polars as pl
import psycopg
import pytest

from untraded import demo, demo_team, fixtures
from untraded_worker.demo import import_demo
from untraded_worker.demo_team import _only_fake_players, import_demo_team, remove_demo_team
from untraded_worker.store import LocalStore

FIXTURES = Path(__file__).parents[3] / "packages/untraded-py/tests/fixtures"
REAL = 76561199000000000


@pytest.fixture
def db(conn: psycopg.Connection[Any]) -> psycopg.Connection[Any]:
    conn.execute("TRUNCATE match, player, app_user, invitation, metric_definition, job CASCADE")
    return conn


@pytest.mark.db
def test_the_demo_is_loaded_once(db: psycopg.Connection[Any], tmp_path: Path) -> None:
    matches = []
    for day, name in enumerate(("premier-half", "premier-abandon"), start=1):
        tables = fixtures.read(FIXTURES / name)
        ids = tables["player"]["steamid"].to_list()
        tables = fixtures.replace_players(tables, {i: REAL + i for i in ids})
        tables["match"] = tables["match"].with_columns(
            pl.lit(dt.date(2026, 10, day)).alias("played_at")
        )
        matches.append(tables)
    built = demo.build(matches, REAL + 1, dt.datetime(2026, 10, 31, 12, tzinfo=dt.UTC))
    demo.write(built, tmp_path / "demo")
    store = LocalStore(tmp_path / "store")

    assert (
        import_demo(
            db,
            store,
            tmp_path / "demo",
            steam_id=demo.PROTAGONIST,
            name="Demo",
            consent_version="2",
        )
        == 2
    )
    user = db.execute(
        "SELECT u.id, u.display_name FROM app_user u WHERE u.steam_id = %s", (demo.PROTAGONIST,)
    ).fetchone()
    assert user is not None
    assert user[1] == "Demo"
    consent = db.execute(
        "SELECT analysis, research_corpus FROM consent_current WHERE user_id = %s", (user[0],)
    ).fetchone()
    assert consent == (True, False)
    ready = db.execute(
        "SELECT count(*) FROM match WHERE status = 'ready' AND parquet_prefix IS NOT NULL"
    ).fetchone()
    assert ready == (2,)
    seen = db.execute(
        "SELECT count(*) FROM workspace_match wm JOIN workspace w ON w.id = wm.workspace_id "
        "WHERE w.created_by = %s",
        (user[0],),
    ).fetchone()
    assert seen == (2,)
    queued = db.execute("SELECT count(*) FROM job WHERE kind = 'session'").fetchone()
    assert queued is not None
    assert queued[0] == 2  # one per match, for the demo user
    opted_out = db.execute(
        "SELECT benchmark_opt_out FROM player WHERE steam_id = %s", (demo.PROTAGONIST,)
    ).fetchone()
    assert opted_out == (True,)
    assert db.execute("SELECT count(*) FROM auth_session").fetchone() == (0,)
    # Again: nothing new.
    assert (
        import_demo(
            db,
            store,
            tmp_path / "demo",
            steam_id=demo.PROTAGONIST,
            name="Demo",
            consent_version="2",
        )
        == 0
    )


@pytest.mark.db
def test_the_demo_team_is_loaded_once(
    db: psycopg.Connection[Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db.execute("TRUNCATE workspace CASCADE")
    matches = []
    for day, name in enumerate(("premier-half", "premier-abandon"), start=1):
        tables = fixtures.read(FIXTURES / name)
        ids = tables["player"]["steamid"].to_list()
        tables = fixtures.replace_players(tables, {i: REAL + i for i in ids})
        tables["match"] = tables["match"].with_columns(
            pl.lit(dt.date(2026, 10, day)).alias("played_at")
        )
        matches.append(tables)
    built = demo.build(matches, REAL + 1, dt.datetime(2026, 10, 31, 12, tzinfo=dt.UTC))
    demo.write(built, tmp_path / "demo")
    # One match a player sent (the team sees it through its roster), one sent for the team.
    monkeypatch.setattr(demo_team, "MODES", (("premier", "roster"), ("scrim", "team")))
    team = demo_team.build(demo.read(tmp_path / "demo"))
    demo_team.write(team, tmp_path / "team")
    store = LocalStore(tmp_path / "store")
    import_demo(
        db, store, tmp_path / "demo", steam_id=demo.PROTAGONIST, name="Demo", consent_version="2"
    )
    sessions_before = db.execute("SELECT count(*) FROM job WHERE kind = 'session'").fetchone()

    def load() -> int:
        return import_demo_team(
            db, store, tmp_path / "team", owner_steam_id=demo.PROTAGONIST, consent_version="2"
        )

    assert load() == 2
    space = db.execute(
        "SELECT id, name FROM workspace WHERE kind = 'team' AND slug = %s", (demo_team.TEAM_SLUG,)
    ).fetchone()
    assert space is not None
    assert space[1] == demo_team.TEAM_NAME
    w = space[0]
    roles = dict(
        db.execute(
            "SELECT u.steam_id, r.name FROM membership m JOIN app_user u ON u.id = m.user_id "
            "JOIN workspace_role r ON r.id = m.role_id WHERE m.workspace_id = %s",
            (w,),
        ).fetchall()
    )
    assert roles == {p.steam_id: p.role for p in demo_team.PEOPLE}
    roster = db.execute(
        "SELECT count(*) FROM roster_member rm JOIN roster r ON r.id = rm.roster_id "
        "WHERE r.workspace_id = %s AND rm.valid_to IS NULL AND rm.valid_from < %s",
        (w, team.matches[0].played_at.date()),
    ).fetchone()
    assert roster == (sum(p.roster is not None for p in demo_team.PEOPLE),)
    # The fake accounts consent to the analysis only, and stay out of the references.
    consents = db.execute(
        "SELECT count(*) FROM app_user u JOIN consent_current c ON c.user_id = u.id "
        "WHERE u.steam_id = ANY (%s) AND c.analysis AND NOT c.research_corpus",
        ([p.steam_id for p in demo_team.PEOPLE],),
    ).fetchone()
    assert consents == (len(demo_team.PEOPLE),)
    opted = db.execute(
        "SELECT bool_and(benchmark_opt_out) FROM player WHERE steam_id = ANY (%s)",
        ([p.steam_id for p in demo_team.PEOPLE],),
    ).fetchone()
    assert opted == (True,)
    # The team sees both matches, each for its reason; the demo user's own space does not.
    variants = [m.match_id for m in team.matches]
    seen = db.execute(
        "SELECT m.sha256, wm.reason::text FROM workspace_match wm "
        "JOIN match m ON m.id = wm.match_id "
        "WHERE wm.workspace_id = %s ORDER BY m.played_at",
        (w,),
    ).fetchall()
    assert seen == [(variants[0], "roster"), (variants[1], "team")]
    personal = db.execute(
        "SELECT count(*) FROM workspace_match wm JOIN workspace s ON s.id = wm.workspace_id "
        "JOIN app_user u ON u.id = s.created_by JOIN match m ON m.id = wm.match_id "
        "WHERE u.steam_id = %s AND m.sha256 = ANY (%s)",
        (demo.PROTAGONIST, variants),
    ).fetchone()
    assert personal == (0,)
    assert (
        db.execute("SELECT count(*) FROM job WHERE kind = 'session'").fetchone() == sessions_before
    )
    sent = db.execute(
        "SELECT u.steam_id FROM upload_sender us JOIN app_user u ON u.id = us.user_id"
    ).fetchall()
    assert sent == [(team.matches[1].sent_by,)]
    stats = db.execute(
        "SELECT count(DISTINCT v.match_id) FROM team_metric_value v "
        "JOIN match m ON m.id = v.match_id "
        "WHERE m.sha256 = ANY (%s)",
        (variants,),
    ).fetchone()
    assert stats == (2,)
    # The review, written by its authors.
    counts = db.execute(
        "SELECT (SELECT count(*) FROM review_comment WHERE workspace_id = %(w)s), "
        "(SELECT count(DISTINCT (match_id, round)) FROM review_tag WHERE workspace_id = %(w)s), "
        "(SELECT count(*) FROM review_playlist WHERE workspace_id = %(w)s)",
        {"w": w},
    ).fetchone()
    assert counts == (len(team.comments), len(team.tags), len(demo_team.PLAYLISTS))
    authors = db.execute(
        "SELECT DISTINCT author_name FROM review_comment WHERE workspace_id = %s", (w,)
    ).fetchall()
    assert {a for (a,) in authors} <= {p.name for p in demo_team.PEOPLE}
    # Again: nothing new.
    assert load() == 0
    again = db.execute(
        "SELECT (SELECT count(*) FROM review_comment WHERE workspace_id = %(w)s), "
        "(SELECT count(DISTINCT (match_id, round)) FROM review_tag WHERE workspace_id = %(w)s), "
        "(SELECT count(*) FROM review_playlist WHERE workspace_id = %(w)s), "
        "(SELECT count(*) FROM membership WHERE workspace_id = %(w)s), "
        "(SELECT count(*) FROM workspace WHERE kind = 'team')",
        {"w": w},
    ).fetchone()
    assert again == (*counts, len(demo_team.PEOPLE), 1)

    # Removed: the team, the matches sent for it (a job), and its invented members (erased).
    assert remove_demo_team(db, owner_steam_id=demo.PROTAGONIST, slug=demo_team.TEAM_SLUG) == (
        len(demo_team.PEOPLE) - 1
    )
    assert db.execute("SELECT count(*) FROM workspace WHERE kind = 'team'").fetchone() == (0,)
    jobs = dict(
        db.execute(
            "SELECT kind, count(*) FROM job WHERE kind IN ('erase_player', 'drop_team_matches') "
            "GROUP BY kind"
        ).fetchall()
    )
    assert jobs == {"erase_player": len(demo_team.PEOPLE) - 1, "drop_team_matches": 1}
    assert db.execute(
        "SELECT deleted_at IS NULL FROM app_user WHERE steam_id = %s", (demo.PROTAGONIST,)
    ).fetchone() == (True,)


@pytest.mark.db
def test_the_demo_team_never_takes_over_another_team(
    db: psycopg.Connection[Any], tmp_path: Path
) -> None:
    db.execute("TRUNCATE workspace CASCADE")
    db.execute("INSERT INTO invitation (steam_id, display_name) VALUES (%s, 'x')", (REAL + 50,))
    db.execute("SELECT open_auth_session(%s, %s, interval '1 minute')", (REAL + 50, b"t" * 32))
    db.execute("SELECT create_team('Someone', %s, %s)", (demo_team.TEAM_SLUG, REAL + 50))
    tables = fixtures.read(FIXTURES / "premier-half")
    ids = tables["player"]["steamid"].to_list()
    tables = fixtures.replace_players(tables, {i: REAL + i for i in ids})
    built = demo.build([tables], REAL + 1, dt.datetime(2026, 10, 31, 12, tzinfo=dt.UTC))
    demo.write(built, tmp_path / "demo")
    demo_team.write(demo_team.build(demo.read(tmp_path / "demo")), tmp_path / "team")
    store = LocalStore(tmp_path / "store")
    import_demo(
        db, store, tmp_path / "demo", steam_id=demo.PROTAGONIST, name="Demo", consent_version="2"
    )
    with pytest.raises(RuntimeError, match="does not own it"):
        import_demo_team(
            db, store, tmp_path / "team", owner_steam_id=demo.PROTAGONIST, consent_version="2"
        )


def test_a_real_match_is_never_published_as_the_demo_team() -> None:
    # The fixture's players are numbered 1 to 10: not demo ids.
    with pytest.raises(ValueError, match="outside the demo's fake range"):
        _only_fake_players(FIXTURES / "premier-half")
