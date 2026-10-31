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

from untraded import demo, fixtures
from untraded_worker.demo import import_demo
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
