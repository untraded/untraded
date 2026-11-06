# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Whom a match counts for, against PostgreSQL: a demo sent from the site names players anyone can
add, so it counts for its sender alone until Valve serves the same demo. The fixture's players are
1 to 10; `SENDER` forged nothing here, but nothing tells that apart from a forgery."""

from __future__ import annotations

import dataclasses
import uuid
from pathlib import Path
from typing import Any

import polars as pl
import psycopg
import pytest

from untraded.parsing import CanonicalMatch
from untraded_worker import queue, reanalyze
from untraded_worker.credit import credited
from untraded_worker.erase import erase_player
from untraded_worker.jobs import ParseJob
from untraded_worker.load import refresh_access
from untraded_worker.sessions import SessionJob, queue_sessions
from untraded_worker.store import LocalStore

SENDER, NAMED, THIRD = 1, 2, 3
SHA = "cd" * 32
pytestmark = pytest.mark.db


@pytest.fixture
def db(conn: psycopg.Connection[Any]) -> psycopg.Connection[Any]:
    conn.execute(
        "TRUNCATE match, player, app_user, workspace, metric_definition, metric_current CASCADE"
    )
    return conn


@pytest.fixture
def store(tmp_path: Path) -> LocalStore:
    return LocalStore(tmp_path)


@pytest.fixture
def parse(canonical: CanonicalMatch) -> Any:
    match = canonical.match.with_columns(pl.lit(SHA).alias("match_id"))
    same_demo = dataclasses.replace(canonical, match=match)
    return lambda path, **_: same_demo


def _user(db: psycopg.Connection[Any], steam_id: int) -> uuid.UUID:
    """A registered player, with their personal workspace."""
    user = db.execute(
        "INSERT INTO app_user (steam_id, display_name) VALUES (%s, 'u') RETURNING id", (steam_id,)
    ).fetchone()
    assert user is not None
    db.execute(
        "INSERT INTO workspace (kind, name, slug, created_by) VALUES ('personal', 'w', %s, %s)",
        (f"u-{steam_id}", user[0]),
    )
    return uuid.UUID(str(user[0]))


def _match(db: psycopg.Connection[Any], demo: str = "demos/a.dem") -> uuid.UUID:
    row = db.execute(
        "INSERT INTO match (mode, played_at, demo_key) VALUES ('premier', now(), %s) RETURNING id",
        (demo,),
    ).fetchone()
    assert row is not None
    return uuid.UUID(str(row[0]))


def _sent(db: psycopg.Connection[Any], match_id: uuid.UUID, user: uuid.UUID) -> None:
    source = db.execute(
        "INSERT INTO ingest_source (user_id, kind) VALUES (%s, 'upload') RETURNING id", (user,)
    ).fetchone()
    assert source is not None
    db.execute(
        "INSERT INTO match_source (match_id, kind, external_id, source_id) "
        "VALUES (%s, 'upload', %s, %s)",
        (match_id, str(match_id), source[0]),
    )


def _run_parse(
    db: psycopg.Connection[Any], store: LocalStore, parse: Any, match_id: uuid.UUID
) -> None:
    ParseJob(store, parse)(db, queue.Job(1, "parse", {"match_id": str(match_id)}, 1, 5))


def _sent_match(
    db: psycopg.Connection[Any], store: LocalStore, parse: Any, user: uuid.UUID
) -> uuid.UUID:
    match_id = _match(db)
    _sent(db, match_id, user)
    _run_parse(db, store, parse, match_id)
    return match_id


def _queued(db: psycopg.Connection[Any]) -> list[int]:
    rows = db.execute("SELECT payload->>'steam_id' FROM job WHERE kind = 'session'").fetchall()
    return sorted(int(r[0]) for r in rows)


def _seen_by(db: psycopg.Connection[Any], match_id: uuid.UUID) -> list[int]:
    rows = db.execute(
        "SELECT u.steam_id FROM workspace_match wm JOIN workspace w ON w.id = wm.workspace_id "
        "JOIN app_user u ON u.id = w.created_by WHERE wm.match_id = %s AND w.kind = 'personal'",
        (match_id,),
    ).fetchall()
    return sorted(r[0] for r in rows)


def _counts_for(db: psycopg.Connection[Any], match_id: uuid.UUID, steam_id: int) -> bool:
    row = db.execute(f"SELECT {credited('%s', '%s::bigint')}", (match_id, steam_id)).fetchone()
    assert row is not None
    return bool(row[0])


def test_a_sent_demo_reaches_no_account_but_its_senders(
    db: psycopg.Connection[Any], store: LocalStore, parse: Any
) -> None:
    sender = _user(db, SENDER)
    _user(db, NAMED)  # the demo names them too: a teammate, or a victim
    match_id = _sent_match(db, store, parse, sender)
    assert _queued(db) == [SENDER]
    assert _seen_by(db, match_id) == [SENDER]

    # A session job for them (queued before the update) finds nothing, and writes nothing.
    job = SessionJob(store)
    job(db, queue.Job(2, "session", {"steam_id": str(NAMED), "match_id": str(match_id)}, 1, 5))
    assert db.execute("SELECT count(*) FROM play_session").fetchone() == (0,)
    job(db, queue.Job(3, "session", {"steam_id": str(SENDER), "match_id": str(match_id)}, 1, 5))
    owners = db.execute("SELECT steam_id FROM play_session").fetchall()
    assert owners == [(SENDER,)]


def test_a_later_valve_match_does_not_bring_it_back(
    db: psycopg.Connection[Any], store: LocalStore, parse: Any, canonical: CanonicalMatch
) -> None:
    # `_played` is what a session reads: a real match of the named player must not pull the sent
    # one into their session or their reference.
    sender = _user(db, SENDER)
    _user(db, NAMED)
    sent = _sent_match(db, store, parse, sender)
    real = _match(db, "demos/b.dem")
    db.execute(
        "INSERT INTO match_source (match_id, kind, external_id) VALUES (%s, 'valve_bot', 'v1')",
        (real,),
    )
    other = canonical.match.with_columns(pl.lit("ef" * 32).alias("match_id"))
    _run_parse(db, store, lambda path, **_: dataclasses.replace(canonical, match=other), real)
    job = SessionJob(store)
    job(db, queue.Job(2, "session", {"steam_id": str(NAMED), "match_id": str(real)}, 1, 5))
    held = db.execute(
        "SELECT sm.match_id FROM play_session s JOIN play_session_match sm ON sm.session_id = s.id "
        "WHERE s.steam_id = %s",
        (NAMED,),
    ).fetchall()
    assert held == [(real,)]
    assert sent != real


def test_a_teammate_gets_the_match_by_sending_the_same_file(
    db: psycopg.Connection[Any], store: LocalStore, parse: Any
) -> None:
    first = _sent_match(db, store, parse, _user(db, SENDER))
    teammate = _user(db, NAMED)
    _user(db, THIRD)
    db.execute("DELETE FROM job")
    second = _match(db)
    _sent(db, second, teammate)
    _run_parse(db, store, parse, second)
    assert db.execute("SELECT id FROM match").fetchall() == [(first,)]  # merged
    assert _queued(db) == [SENDER, NAMED]
    assert _seen_by(db, first) == [SENDER, NAMED]
    # Two senders vouch for themselves, not for a third player: they could be one person.
    assert not _counts_for(db, first, THIRD)


def test_the_same_file_sent_after_retention_does_not_stay_on_disk(
    db: psycopg.Connection[Any], store: LocalStore, parse: Any
) -> None:
    first = _sent_match(db, store, parse, _user(db, SENDER))
    db.execute("UPDATE match SET demo_deleted_at = now() WHERE id = %s", (first,))
    store.path("demos/a.dem").parent.mkdir(parents=True, exist_ok=True)
    store.path("demos/a.dem").write_bytes(b"the same file, sent again")
    second = _match(db)
    _sent(db, second, _user(db, NAMED))
    _run_parse(db, store, parse, second)
    assert db.execute("SELECT id FROM match").fetchall() == [(first,)]
    assert not store.exists("demos/a.dem")  # the sweep skips a match whose demo already went
    assert _seen_by(db, first) == [SENDER, NAMED]


def test_the_collector_bringing_the_same_demo_confirms_it_for_everyone(
    db: psycopg.Connection[Any], store: LocalStore, parse: Any
) -> None:
    first = _sent_match(db, store, parse, _user(db, SENDER))
    _user(db, NAMED)
    assert _seen_by(db, first) == [SENDER]
    db.execute("DELETE FROM job")
    collected = _match(db)
    db.execute(
        "INSERT INTO match_source (match_id, kind, external_id) VALUES (%s, 'valve_bot', 'v1')",
        (collected,),
    )
    _run_parse(db, store, parse, collected)
    assert db.execute("SELECT id FROM match").fetchall() == [(first,)]
    assert _queued(db) == [SENDER, NAMED]
    assert _seen_by(db, first) == [SENDER, NAMED]


def test_no_other_source_vouches_for_everyone(
    db: psycopg.Connection[Any], store: LocalStore, parse: Any
) -> None:
    match_id = _sent_match(db, store, parse, _user(db, SENDER))
    assert not _counts_for(db, match_id, NAMED)
    # A source another way in may add later: it counts for its sender, nothing more.
    db.execute(
        "INSERT INTO match_source (match_id, kind, external_id) VALUES (%s, 'url', 'u1')",
        (match_id,),
    )
    assert not _counts_for(db, match_id, NAMED)
    # An id that only looks like the demo import's, on another kind of source, does not either.
    db.execute(
        "INSERT INTO match_source (match_id, kind, external_id) VALUES (%s, 'url', 'demo:x')",
        (match_id,),
    )
    assert not _counts_for(db, match_id, NAMED)
    db.execute(
        "INSERT INTO match_source (match_id, kind, external_id) VALUES (%s, 'upload', 'demo:x')",
        (match_id,),
    )
    assert _counts_for(db, match_id, NAMED)  # the demo account's import


def test_a_refused_upload_counts_for_nobody(
    db: psycopg.Connection[Any], store: LocalStore, parse: Any
) -> None:
    match_id = _sent_match(db, store, parse, _user(db, SENDER))
    assert _counts_for(db, match_id, SENDER)
    db.execute("UPDATE match_source SET rejected = 'corrupt' WHERE match_id = %s", (match_id,))
    assert not _counts_for(db, match_id, SENDER)
    assert queue_sessions(db, match_id) == 0


def test_a_team_does_not_see_a_forged_demo_naming_its_roster(
    db: psycopg.Connection[Any], store: LocalStore, parse: Any
) -> None:
    sender = _user(db, 10)  # player 10 of the fixture, outside the roster
    match_id = _sent_match(db, store, parse, sender)
    owner = _user(db, 99)
    team = db.execute(
        "INSERT INTO workspace (kind, name, slug, created_by) "
        "VALUES ('team', 't', 'team', %s) RETURNING id",
        (owner,),
    ).fetchone()
    assert team is not None
    roster = db.execute(
        "INSERT INTO roster (workspace_id, name) VALUES (%s, 'main') RETURNING id", (team[0],)
    ).fetchone()
    assert roster is not None
    for steam_id in (1, 2, 3):
        db.execute(
            "INSERT INTO roster_member (roster_id, steam_id, valid_from) "
            "VALUES (%s, %s, '2020-01-01')",
            (roster[0], steam_id),
        )
    db.execute(
        "INSERT INTO workspace_player (workspace_id, steam_id, share_solo) VALUES (%s, 2, true)",
        (team[0],),
    )
    refresh_access(db, match_id)

    def reasons() -> list[str]:
        rows = db.execute(
            "SELECT reason::text FROM workspace_match WHERE match_id = %s AND workspace_id = %s",
            (match_id, team[0]),
        ).fetchall()
        return [r[0] for r in rows]

    assert reasons() == []
    # One of its players sends it: the team's scrim reaches the team.
    member = _user(db, 1)
    source = db.execute(
        "INSERT INTO ingest_source (user_id, kind) VALUES (%s, 'upload') RETURNING id", (member,)
    ).fetchone()
    assert source is not None
    db.execute(
        "INSERT INTO match_source (match_id, kind, external_id, source_id) "
        "VALUES (%s, 'upload', 'second', %s)",
        (match_id, source[0]),
    )
    refresh_access(db, match_id)
    assert reasons() == ["roster"]


def _stale_session(db: psycopg.Connection[Any], steam_id: int, matches: list[uuid.UUID]) -> None:
    session = db.execute(
        "INSERT INTO play_session (steam_id, started_at, ended_at, matches, rounds, "
        "reference_from, reference_to, reference_matches, reference_rounds, enough, params) "
        "VALUES (%s, now(), now(), 2, 5, current_date, current_date, 0, 0, false, '{}') "
        "RETURNING id",
        (steam_id,),
    ).fetchone()
    assert session is not None
    for match_id in matches:
        db.execute(
            "INSERT INTO play_session_match (session_id, match_id) VALUES (%s, %s)",
            (session[0], match_id),
        )


def test_reanalysis_withdraws_the_sessions_written_before_the_rule(
    db: psycopg.Connection[Any], store: LocalStore, parse: Any
) -> None:
    sent = _sent_match(db, store, parse, _user(db, SENDER))
    _user(db, NAMED)
    real = _match(db, "demos/b.dem")
    db.execute(
        "INSERT INTO match_source (match_id, kind, external_id) VALUES (%s, 'valve_bot', 'v1')",
        (real,),
    )
    _stale_session(db, NAMED, [sent, real])
    _stale_session(db, SENDER, [sent])
    db.execute("DELETE FROM job")

    assert reanalyze.reanalyze(db, store, sent)
    owners = db.execute("SELECT steam_id FROM play_session").fetchall()
    assert owners == [(SENDER,)]  # theirs stands: the match counts for them
    payloads = db.execute("SELECT payload FROM job WHERE kind = 'session'").fetchall()
    assert {"steam_id": str(NAMED), "match_id": str(real)} in [p for (p,) in payloads]
    assert sorted({int(p["steam_id"]) for (p,) in payloads}) == [SENDER, NAMED]
    assert _seen_by(db, sent) == [SENDER]


def test_an_erased_sender_takes_the_demo_with_them(
    db: psycopg.Connection[Any], store: LocalStore, parse: Any
) -> None:
    match_id = _sent_match(db, store, parse, _user(db, SENDER))
    _user(db, NAMED)
    # The named player is a registered player of the match, but it was never theirs.
    assert erase_player(db, store, SENDER).matches == 1
    assert db.execute("SELECT id FROM match WHERE id = %s", (match_id,)).fetchone() is None


def test_an_erased_sender_vouches_for_nobody(
    db: psycopg.Connection[Any], store: LocalStore, parse: Any
) -> None:
    # Two senders: the match stays for the one who remains, never for the player they named.
    first = _user(db, SENDER)
    match_id = _sent_match(db, store, parse, first)
    second = _match(db)
    _sent(db, second, _user(db, THIRD))
    _run_parse(db, store, parse, second)
    _user(db, NAMED)
    assert erase_player(db, store, SENDER).matches == 0
    assert db.execute("SELECT id FROM match WHERE id = %s", (match_id,)).fetchone() is not None
    assert not _counts_for(db, match_id, SENDER)
    assert _counts_for(db, match_id, THIRD)
    assert not _counts_for(db, match_id, NAMED)


def test_a_named_player_erased_leaves_the_senders_match(
    db: psycopg.Connection[Any], store: LocalStore, parse: Any
) -> None:
    match_id = _sent_match(db, store, parse, _user(db, SENDER))
    _user(db, NAMED)
    assert erase_player(db, store, NAMED).matches == 0
    assert db.execute("SELECT id FROM match WHERE id = %s", (match_id,)).fetchone() is not None
