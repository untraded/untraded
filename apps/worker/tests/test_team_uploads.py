# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Demos a team sends for itself (migration 0018), against PostgreSQL: the roster rule at the
parse, the team's access, and what an erasure or the team's deletion leaves. The `premier-half`
fixture has players 1 to 5 on side A and 6 to 10 on side B."""

from __future__ import annotations

import dataclasses
import datetime as dt
import uuid
from pathlib import Path
from typing import Any

import polars as pl
import psycopg
import pytest

from untraded.parsing import CanonicalMatch
from untraded_worker import queue
from untraded_worker.erase import drop_team_matches, erase_player
from untraded_worker.jobs import ParseJob
from untraded_worker.store import LocalStore
from untraded_worker.team_access import refresh_matches

pytestmark = pytest.mark.db
SHA = "cd" * 32
COACH = 500  # not a player of the fixture


@pytest.fixture
def db(conn: psycopg.Connection[Any]) -> psycopg.Connection[Any]:
    conn.execute(
        "TRUNCATE match, player, app_user, workspace, metric_definition, metric_current, "
        "invitation CASCADE"
    )
    return conn


@dataclasses.dataclass
class FakeParser:
    canonical: CanonicalMatch

    def __call__(self, path: Path, **_: Any) -> CanonicalMatch:
        return self.canonical


@pytest.fixture
def fake(canonical: CanonicalMatch) -> FakeParser:
    match = canonical.match.with_columns(pl.lit(SHA).alias("match_id"))
    return FakeParser(dataclasses.replace(canonical, match=match))


def _user(db: psycopg.Connection[Any], steam_id: int, *, consents: bool = True) -> uuid.UUID:
    db.execute(
        "INSERT INTO player (steam_id, last_name) VALUES (%s, 'p') ON CONFLICT DO NOTHING",
        (steam_id,),
    )
    row = db.execute(
        "INSERT INTO app_user (steam_id, display_name) VALUES (%s, %s) RETURNING id",
        (steam_id, f"user {steam_id}"),
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


def _team(
    db: psycopg.Connection[Any], roster: list[int], *, since: str = "2020-01-01"
) -> uuid.UUID:
    """A team as `create_team` makes it, owned by the coach, with `roster` (registered players)
    on its roster since `since`."""
    row = db.execute("SELECT create_team('Team', 'team', %s)", (COACH,)).fetchone()
    assert row is not None
    team = uuid.UUID(str(row[0]))
    for steam_id in roster:
        db.execute(
            "INSERT INTO roster_member (roster_id, steam_id, valid_from) "
            "SELECT id, %s, %s FROM roster WHERE workspace_id = %s",
            (steam_id, since, team),
        )
    return team


def _as(db: psycopg.Connection[Any], user: uuid.UUID | None) -> None:
    db.execute("SELECT set_config('app.user_id', %s, false)", (str(user) if user else "",))


def _team_upload(
    db: psycopg.Connection[Any], team: uuid.UUID, sender: uuid.UUID, demo: str = "demos/a.dem"
) -> uuid.UUID:
    """What `add_team_upload` records, as `sender`, then the demo in the store (as
    `ingest_upload` leaves it)."""
    upload = uuid.uuid4()
    _as(db, sender)
    refused = db.execute(
        "SELECT add_team_upload(%s, %s, 'x.dem', 'scrim', %s, 0, 0)",
        (team, upload, dt.datetime(2026, 11, 1, 20, tzinfo=dt.UTC)),
    ).fetchone()
    _as(db, None)
    assert refused == (None,)
    db.execute("UPDATE match SET demo_key = %s, status = 'parsing' WHERE id = %s", (demo, upload))
    db.execute("DELETE FROM job")
    return upload


def _parse(
    db: psycopg.Connection[Any], store: LocalStore, fake: FakeParser, match: uuid.UUID
) -> None:
    ParseJob(store, fake)(db, queue.Job(1, "parse", {"match_id": str(match)}, 1, 5))


def _store(tmp_path: Path, *names: str) -> LocalStore:
    (tmp_path / "demos").mkdir(exist_ok=True)
    for name in names:
        (tmp_path / "demos" / name).write_bytes(b"demo")
    return LocalStore(tmp_path)


def _state(db: psycopg.Connection[Any], match: uuid.UUID) -> tuple[Any, ...] | None:
    return db.execute(
        "SELECT m.status::text, m.error, ms.rejected FROM match m "
        "JOIN match_source ms ON ms.match_id = m.id WHERE m.id = %s",
        (match,),
    ).fetchone()


def _access(db: psycopg.Connection[Any], match: uuid.UUID) -> set[tuple[str, str]]:
    rows = db.execute(
        "SELECT w.slug::text, wm.reason::text FROM workspace_match wm "
        "JOIN workspace w ON w.id = wm.workspace_id WHERE wm.match_id = %s",
        (match,),
    ).fetchall()
    return {(row[0], row[1]) for row in rows}


def test_a_coach_who_did_not_play_sends_the_teams_match(
    db: psycopg.Connection[Any], tmp_path: Path, fake: FakeParser
) -> None:
    coach = _user(db, COACH)
    for steam_id in (1, 2, 3):
        _user(db, steam_id)
    team = _team(db, [1, 2, 3])
    store = _store(tmp_path, "a.dem")
    match = _team_upload(db, team, coach)
    _parse(db, store, fake, match)
    assert _state(db, match) == ("ready", None, None)
    # The team's alone: neither the players' own spaces nor their sessions see it.
    assert _access(db, match) == {("team", "team")}
    assert db.execute("SELECT count(*) FROM job WHERE kind = 'session'").fetchone() == (0,)
    sender = db.execute(
        "SELECT u.steam_id FROM upload_sender us JOIN app_user u ON u.id = us.user_id"
    ).fetchall()
    assert sender == [(COACH,)]

    # Leaving the roster later does not take the match back from the team.
    db.execute("UPDATE roster_member SET valid_to = '2020-06-01'")
    refresh_matches(db, [match])
    assert _access(db, match) == {("team", "team")}


def test_three_of_the_roster_on_both_sides_are_refused(
    db: psycopg.Connection[Any], tmp_path: Path, fake: FakeParser
) -> None:
    coach = _user(db, COACH)
    for steam_id in (1, 2, 6, 7):
        _user(db, steam_id)  # three registered players on side B would pass: only two are listed
    team = _team(db, [1, 2, 6])
    store = _store(tmp_path, "a.dem")
    match = _team_upload(db, team, coach)
    _parse(db, store, fake, match)
    assert _state(db, match) == ("unavailable", "not_enough_roster", "not_enough_roster")
    assert not store.exists("demos/a.dem")
    assert _access(db, match) == set()


def test_a_teams_date_gives_way_to_a_players_own_copy(
    db: psycopg.Connection[Any], tmp_path: Path, fake: FakeParser
) -> None:
    coach = _user(db, COACH)
    player = _user(db, 1)
    for steam_id in (2, 3):
        _user(db, steam_id)
    team = _team(db, [1, 2, 3])
    store = _store(tmp_path, "a.dem", "b.dem")
    sent = _team_upload(db, team, coach)
    _parse(db, store, fake, sent)
    # Player 1 sends the same demo from their own space, with the date they know.
    own = db.execute(
        "INSERT INTO match (mode, played_at, demo_key, status) "
        "VALUES ('faceit', '2026-10-05 20:00+00', 'demos/b.dem', 'parsing') RETURNING id"
    ).fetchone()
    assert own is not None
    source = db.execute(
        "INSERT INTO ingest_source (user_id, kind) VALUES (%s, 'upload') RETURNING id", (player,)
    ).fetchone()
    assert source is not None
    db.execute(
        "INSERT INTO match_source (match_id, kind, external_id, source_id) "
        "VALUES (%s, 'upload', 'own-copy', %s)",
        (own[0], source[0]),
    )
    _parse(db, store, fake, own[0])
    row = db.execute(
        "SELECT mode::text, played_at, ended_at > played_at, "
        "ended_at - played_at < interval '3 hours' FROM match WHERE id = %s",
        (sent,),
    ).fetchone()
    assert row == ("faceit", dt.datetime(2026, 10, 5, 20, tzinfo=dt.UTC), True, True)
    assert _access(db, sent) == {("team", "team"), ("u-1", "own")}


def test_the_roster_on_the_date_of_the_match_and_consenting(
    db: psycopg.Connection[Any], tmp_path: Path, fake: FakeParser
) -> None:
    coach = _user(db, COACH)
    _user(db, 1)
    _user(db, 2)
    _user(db, 3, consents=False)  # does not consent to the analysis: not counted
    _user(db, 4)
    _user(db, 5)
    team = _team(db, [1, 2, 3, 5])  # 5 consents: the roster passes the check before the upload
    db.execute("UPDATE roster_member SET valid_to = '2026-10-01' WHERE steam_id = 5")
    db.execute(  # joined after the match (played on Nov 1)
        "INSERT INTO roster_member (roster_id, steam_id, valid_from) "
        "SELECT id, 4, '2026-11-10' FROM roster WHERE workspace_id = %s",
        (team,),
    )
    store = _store(tmp_path, "a.dem")
    match = _team_upload(db, team, coach)
    _parse(db, store, fake, match)
    assert _state(db, match) == ("unavailable", "not_enough_roster", "not_enough_roster")


def test_an_erased_player_leaves_the_teams_match(
    db: psycopg.Connection[Any], tmp_path: Path, fake: FakeParser
) -> None:
    coach = _user(db, COACH)
    for steam_id in (1, 2, 3):
        _user(db, steam_id)
    team = _team(db, [1, 2, 3])
    store = _store(tmp_path, "a.dem")
    match = _team_upload(db, team, coach)
    _parse(db, store, fake, match)

    erased = erase_player(db, store, 1)
    assert erased.matches == 0  # it counted for nobody's account, yet it is the team's
    assert _access(db, match) == {("team", "team")}
    assert store.exists(f"matches/{match}/round.parquet")

    # The sender is erased too (after handing the team over): the history no longer names them.
    db.execute(
        "UPDATE membership SET role_id = (SELECT id FROM workspace_role "
        "WHERE workspace_id = %s AND name = 'coach') WHERE workspace_id = %s",
        (team, team),
    )
    erase_player(db, store, COACH)
    assert db.execute("SELECT count(*) FROM upload_sender").fetchone() == (0,)
    assert _access(db, match) == {("team", "team")}


def test_a_deleted_teams_matches_go_unless_they_count_for_someone(
    db: psycopg.Connection[Any], tmp_path: Path, fake: FakeParser, canonical: CanonicalMatch
) -> None:
    coach = _user(db, COACH)
    player = _user(db, 1)
    for steam_id in (2, 3):
        _user(db, steam_id)
    team = _team(db, [1, 2, 3])
    store = _store(tmp_path, "a.dem", "b.dem")
    alone = _team_upload(db, team, coach)
    _parse(db, store, fake, alone)
    # Another match, which player 1 also sent from their own space: it counts for them.
    other_sha = FakeParser(
        dataclasses.replace(
            canonical, match=canonical.match.with_columns(pl.lit("ef" * 32).alias("match_id"))
        )
    )
    kept = _team_upload(db, team, coach, "demos/b.dem")
    source = db.execute(
        "INSERT INTO ingest_source (user_id, kind) VALUES (%s, 'upload') RETURNING id", (player,)
    ).fetchone()
    assert source is not None
    db.execute(
        "INSERT INTO match_source (match_id, kind, external_id, source_id) "
        "VALUES (%s, 'upload', 'own-copy', %s)",
        (kept, source[0]),
    )
    _parse(db, store, other_sha, kept)

    _as(db, coach)
    db.execute("SELECT delete_team(%s)", (team,))
    _as(db, None)
    job = db.execute("SELECT payload FROM job WHERE kind = 'drop_team_matches'").fetchone()
    assert job is not None
    assert sorted(job[0]["match_ids"]) == sorted([str(alone), str(kept)])

    dropped = drop_team_matches(db, store, [alone, kept])
    assert dropped.matches == 1
    remaining = db.execute("SELECT id FROM match").fetchall()
    assert remaining == [(kept,)]
    assert not store.exists(f"matches/{alone}/round.parquet")
    assert not store.exists("demos/a.dem")
    assert store.exists("demos/b.dem")
    assert _access(db, kept) == {("u-1", "own")}
    assert drop_team_matches(db, store, [alone, kept]).matches == 0  # harmless again
