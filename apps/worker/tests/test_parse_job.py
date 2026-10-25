# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The `parse` job against PostgreSQL, with the canonical tables of a fixture standing in for
the parser (no demo in the repository)."""

from __future__ import annotations

import dataclasses
import shutil
import uuid
from pathlib import Path
from typing import Any

import polars as pl
import psycopg
import pytest

from untraded.parsing import CanonicalMatch, UnsupportedModeError
from untraded_worker import queue, replays
from untraded_worker.analysis import Analysis
from untraded_worker.jobs import ON_DEAD, JobError, ParseJob
from untraded_worker.load import load_match, refresh_access, sql_frames
from untraded_worker.runner import Worker
from untraded_worker.store import LocalStore

SHA = "ab" * 32
pytestmark = pytest.mark.db


@pytest.fixture
def db(conn: psycopg.Connection[Any]) -> psycopg.Connection[Any]:
    conn.execute(
        "TRUNCATE match, player, app_user, workspace, metric_definition, metric_current CASCADE"
    )
    return conn


def _match(conn: psycopg.Connection[Any], demo_key: str | None = "demos/a.dem") -> uuid.UUID:
    row = conn.execute(
        "INSERT INTO match (mode, played_at, demo_key) VALUES ('premier', now(), %s) RETURNING id",
        (demo_key,),
    ).fetchone()
    assert row is not None
    return uuid.UUID(str(row[0]))


def _count(conn: psycopg.Connection[Any], table: str, match_id: uuid.UUID) -> int:
    row = conn.execute(f"SELECT count(*) FROM {table} WHERE match_id = %s", (match_id,)).fetchone()
    assert row is not None
    return int(row[0])


def test_load_is_complete_and_idempotent(db: psycopg.Connection[Any], analysis: Analysis) -> None:
    match_id = _match(db)
    for _ in range(2):  # a reparse replaces the rows
        load_match(db, match_id, analysis)
    for table, frame in sql_frames(analysis).items():
        assert _count(db, table, match_id) == frame.height, table
    assert _count(db, "metric_value", match_id) == analysis.values.height
    tables = sum(1 for f in analysis.table_values.values() for _ in f.group_by("steamid"))
    assert _count(db, "metric_table_value", match_id) == tables
    wide = db.execute(
        "SELECT count(*) FROM metric_wide_current WHERE match_id = %s AND scope = 'match' "
        "AND kills IS NOT NULL",
        (match_id,),
    ).fetchone()
    assert wide == (analysis.tables["player"].height,)  # metric_current is set
    directions = dict(db.execute("SELECT metric_id, better FROM metric_definition").fetchall())
    assert directions["base.deaths"] == "lower"
    assert directions["base.adr"] == "higher"
    cases = dict(db.execute("SELECT metric_id, cases FROM metric_definition").fetchall())
    assert cases["duel.opening_success_pct"] == ["duel.opening_attempts"]
    assert cases["base.kast"] == ["rounds"]
    assert cases["base.kills"] == []
    row = db.execute(
        "SELECT map, rounds_played, parser_version FROM match WHERE id = %s", (match_id,)
    ).fetchone()
    assert row == ("de_cache", 5, "demoparser2 0.42.0")


def _workspace(db: psycopg.Connection[Any], kind: str, steam_id: int) -> uuid.UUID:
    user = db.execute(
        "INSERT INTO app_user (steam_id, display_name) VALUES (%s, 'u') RETURNING id",
        (steam_id + 1000 if kind == "team" else steam_id,),
    ).fetchone()
    assert user is not None
    row = db.execute(
        "INSERT INTO workspace (kind, name, slug, created_by) VALUES (%s, 'w', %s, %s) "
        "RETURNING id",
        (kind, f"{kind}-{steam_id}", user[0]),
    ).fetchone()
    assert row is not None
    return uuid.UUID(str(row[0]))


def test_access(db: psycopg.Connection[Any], analysis: Analysis) -> None:
    match_id = _match(db)
    load_match(db, match_id, analysis)
    own = _workspace(db, "personal", 1)  # player 1 played
    _workspace(db, "personal", 99)  # did not
    team = _workspace(db, "team", 1)
    roster = db.execute(
        "INSERT INTO roster (workspace_id, name) VALUES (%s, 'main') RETURNING id", (team,)
    ).fetchone()
    assert roster is not None
    for steam_id in (1, 2):
        db.execute(
            "INSERT INTO roster_member (roster_id, steam_id, valid_from) "
            "VALUES (%s, %s, '2020-01-01')",
            (roster[0], steam_id),
        )
    assert refresh_access(db, match_id) == 1  # two roster members are not enough
    db.execute(
        "INSERT INTO roster_member (roster_id, steam_id, valid_from) VALUES (%s, 3, '2020-01-01')",
        (roster[0],),
    )
    assert refresh_access(db, match_id) == 2
    reasons = dict(
        db.execute(
            "SELECT workspace_id, reason::text FROM workspace_match WHERE match_id = %s",
            (match_id,),
        ).fetchall()
    )
    assert reasons == {own: "own", team: "roster"}


@dataclasses.dataclass
class FakeParser:
    canonical: CanonicalMatch
    calls: list[Path] = dataclasses.field(default_factory=list)

    def __call__(self, path: Path, **_: Any) -> CanonicalMatch:
        self.calls.append(path)
        return self.canonical


@pytest.fixture
def fake(canonical: CanonicalMatch) -> FakeParser:
    match = canonical.match.with_columns(pl.lit(SHA).alias("match_id"))
    return FakeParser(dataclasses.replace(canonical, match=match))


def test_parse_job_end_to_end(
    db: psycopg.Connection[Any], tmp_path: Path, fake: FakeParser
) -> None:
    store = LocalStore(tmp_path)
    match_id = _match(db)
    queue.enqueue(db, "parse", {"match_id": str(match_id)})
    worker = Worker("", {"parse": ParseJob(store, fake)}, on_dead=ON_DEAD)
    assert worker.step(db)
    assert fake.calls == [store.path("demos/a.dem")]
    row = db.execute(
        "SELECT status::text, sha256, parquet_prefix FROM match WHERE id = %s", (match_id,)
    ).fetchone()
    assert row == ("ready", SHA, f"matches/{match_id}")
    assert store.exists(f"matches/{match_id}/round_player.parquet")
    assert store.exists(f"matches/{match_id}/kill.parquet")
    # The 2D viewer's replays, one per round.
    assert store.exists(f"matches/{match_id}/replay/11.json.gz")
    assert store.exists(f"matches/{match_id}/replay/15.json.gz")

    # Matches parsed before replays existed get them from `untraded-worker replays`.
    shutil.rmtree(store.path(f"matches/{match_id}/replay"))
    assert replays.backfill(db, store) == 1
    assert store.exists(f"matches/{match_id}/replay/11.json.gz")
    assert replays.backfill(db, store) == 0  # nothing left to do
    assert replays.backfill(db, store, force=True) == 1


def test_a_known_demo_is_merged_into_its_match(
    db: psycopg.Connection[Any], tmp_path: Path, fake: FakeParser
) -> None:
    store = LocalStore(tmp_path)
    (tmp_path / "demos").mkdir()
    (tmp_path / "demos" / "b.dem").write_bytes(b"same demo, other copy")
    job = ParseJob(store, fake)
    first, second = _match(db), _match(db, "demos/b.dem")
    for match_id, external in ((first, "m1"), (second, "m2")):
        db.execute(
            "INSERT INTO match_source (match_id, kind, external_id) VALUES (%s, 'upload', %s)",
            (match_id, external),
        )
        job(db, queue.Job(1, "parse", {"match_id": str(match_id)}, 1, 5))
    assert db.execute("SELECT id FROM match").fetchall() == [(first,)]
    sources = db.execute("SELECT match_id FROM match_source").fetchall()
    assert sources == [(first,), (first,)]
    assert not store.exists("demos/b.dem")


def test_a_dead_parse_marks_the_match_failed(
    db: psycopg.Connection[Any], tmp_path: Path, fake: FakeParser
) -> None:
    match_id = _match(db, demo_key=None)
    queue.enqueue(db, "parse", {"match_id": str(match_id)}, max_attempts=1)
    worker = Worker("", {"parse": ParseJob(LocalStore(tmp_path), fake)}, on_dead=ON_DEAD)
    assert worker.step(db)
    row = db.execute("SELECT status::text, error FROM match WHERE id = %s", (match_id,)).fetchone()
    assert row is not None
    assert row[0] == "failed"
    assert row[1].startswith(JobError.__name__)


def test_a_match_of_another_mode_is_set_aside(db: psycopg.Connection[Any], tmp_path: Path) -> None:
    def competitive(path: Path, **_: Any) -> CanonicalMatch:
        raise UnsupportedModeError("not a Premier match: rank type 12 (Competitive)")

    store = LocalStore(tmp_path)
    (tmp_path / "demos").mkdir()
    (tmp_path / "demos" / "a.dem").write_bytes(b"demo")
    match_id = _match(db)
    ParseJob(store, competitive)(db, queue.Job(1, "parse", {"match_id": str(match_id)}, 1, 5))
    row = db.execute(
        "SELECT status::text, error, demo_deleted_at IS NOT NULL FROM match WHERE id = %s",
        (match_id,),
    ).fetchone()
    assert row == ("unavailable", "not a Premier match: rank type 12 (Competitive)", True)
    assert not store.exists("demos/a.dem")


def _sent_by(db: psycopg.Connection[Any], match_id: uuid.UUID, steam_id: int) -> None:
    """The match is a demo `steam_id` sent from the site."""
    user = db.execute(
        "INSERT INTO app_user (steam_id, display_name) VALUES (%s, 'u') RETURNING id", (steam_id,)
    ).fetchone()
    assert user is not None
    source = db.execute(
        "INSERT INTO ingest_source (user_id, kind) VALUES (%s, 'upload') RETURNING id", (user[0],)
    ).fetchone()
    assert source is not None
    db.execute(
        "INSERT INTO match_source (match_id, kind, external_id, source_id) "
        "VALUES (%s, 'upload', %s, %s)",
        (match_id, str(match_id), source[0]),
    )


def test_a_demo_sent_by_someone_who_did_not_play_is_not_analysed(
    db: psycopg.Connection[Any], tmp_path: Path, fake: FakeParser
) -> None:
    store = LocalStore(tmp_path)
    (tmp_path / "demos").mkdir()
    (tmp_path / "demos" / "a.dem").write_bytes(b"demo")
    match_id = _match(db)
    _sent_by(db, match_id, 99)  # the fixture's players are 1 to 10
    ParseJob(store, fake)(db, queue.Job(1, "parse", {"match_id": str(match_id)}, 1, 5))
    row = db.execute(
        "SELECT m.status::text, m.error, ms.rejected FROM match m "
        "JOIN match_source ms ON ms.match_id = m.id WHERE m.id = %s",
        (match_id,),
    ).fetchone()
    assert row == ("unavailable", "not_a_player", "not_a_player")
    assert not store.exists("demos/a.dem")
    assert _count(db, "match_player", match_id) == 0


def test_a_demo_sent_by_one_of_its_players_is_analysed(
    db: psycopg.Connection[Any], tmp_path: Path, fake: FakeParser
) -> None:
    match_id = _match(db)
    _sent_by(db, match_id, 1)
    ParseJob(LocalStore(tmp_path), fake)(
        db, queue.Job(1, "parse", {"match_id": str(match_id)}, 1, 5)
    )
    row = db.execute(
        "SELECT m.status::text, ms.rejected FROM match m "
        "JOIN match_source ms ON ms.match_id = m.id WHERE m.id = %s",
        (match_id,),
    ).fetchone()
    assert row == ("ready", None)
