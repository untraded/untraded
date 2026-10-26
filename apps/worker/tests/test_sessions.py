# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import dataclasses
import datetime as dt
import uuid
from pathlib import Path
from typing import Any

import polars as pl
import psycopg
import pytest

from untraded.metrics import REGISTRY
from untraded_worker import queue
from untraded_worker.analysis import Analysis
from untraded_worker.load import load_match
from untraded_worker.sessions import (
    PlayedMatch,
    SessionJob,
    later_sessions,
    queue_sessions,
    session_of,
)
from untraded_worker.store import LocalStore

DAY = dt.datetime(2026, 10, 19, tzinfo=dt.UTC)
ME = 1  # a player of the fixture


def at(hours: float, minutes: float = 40, days: int = 0) -> tuple[dt.datetime, dt.datetime]:
    start = DAY + dt.timedelta(days=days, hours=hours)
    return start, start + dt.timedelta(minutes=minutes)


def played(*spans: tuple[dt.datetime, dt.datetime]) -> list[PlayedMatch]:
    return [PlayedMatch(uuid.uuid4(), f"{i:064x}", s, e, "") for i, (s, e) in enumerate(spans)]


def test_a_session_runs_while_breaks_last_at_most_an_hour() -> None:
    matches = played(at(18), at(19.5), at(20.5), at(22.5), at(0, days=1))
    # 18:40 -> 19:30 (50 min) and 20:10 -> 20:30 (20 min): one session; 21:10 -> 22:30 is more
    # than an hour; 23:10 -> 00:00 the next day stays within it.
    assert session_of(matches, matches[1].id) == matches[:3]
    assert session_of(matches, matches[4].id) == matches[3:]
    assert session_of(matches, uuid.uuid4()) == []


def test_exactly_one_hour_still_counts() -> None:
    first = at(18)  # ends at 18:40
    matches = played(first, at(19 + 40 / 60))  # starts at 19:40
    assert session_of(matches, matches[1].id) == matches


def test_a_late_match_is_in_the_reference_of_the_next_30_days() -> None:
    # Sessions on day 0, day 2, day 2 later, day 31; then a match of day -1 arrives late.
    matches = played(at(20), at(20, days=2), at(23.5, days=2), at(20, days=31))
    late = played(at(20, days=-1))[0]
    everything = sorted([late, *matches], key=lambda m: m.started_at)
    following = later_sessions(everything, [late], window_days=30)
    # Day 31's reference runs from day 1: the late match of day -1 is not in it.
    assert [s[0] for s in following] == matches[:3]
    # The newest session changes no one's reference.
    assert later_sessions(everything, [matches[3]], window_days=30) == []
    # Nor does a session for the sessions of its own day (their reference stops the day before).
    assert later_sessions(everything, [matches[1]], window_days=30) == [[matches[3]]]


# ------------------------------------------------------------------------------------------
# Against PostgreSQL: the fixture stands for every match (same tables, other ids and times).


@pytest.fixture
def db(conn: psycopg.Connection[Any]) -> psycopg.Connection[Any]:
    conn.execute("TRUNCATE match, player, app_user, metric_definition CASCADE")
    conn.execute("INSERT INTO app_user (steam_id, display_name) VALUES (%s, 'me')", (ME,))
    return conn


def add_match(
    db: psycopg.Connection[Any],
    store: LocalStore,
    analysis: Analysis,
    span: tuple[dt.datetime, dt.datetime],
) -> uuid.UUID:
    row = db.execute(
        "INSERT INTO match (mode, status, played_at, ended_at) VALUES ('premier', 'ready', %s, %s) "
        "RETURNING id",
        span,
    ).fetchone()
    assert row is not None
    match_id = uuid.UUID(str(row[0]))
    tables = dict(analysis.tables)
    tables["match"] = tables["match"].with_columns(pl.lit(match_id.hex * 2).alias("match_id"))
    load_match(db, match_id, dataclasses.replace(analysis, tables=tables))
    prefix = f"matches/{match_id}"
    store.write_tables(prefix, tables)
    db.execute("UPDATE match SET parquet_prefix = %s WHERE id = %s", (prefix, match_id))
    return match_id


def run(job: SessionJob, db: psycopg.Connection[Any], match_id: uuid.UUID) -> None:
    job(db, queue.Job(1, "session", {"steam_id": str(ME), "match_id": str(match_id)}, 1, 5))


def sessions(db: psycopg.Connection[Any]) -> list[tuple[Any, ...]]:
    return db.execute(
        "SELECT s.matches, s.reference_matches, s.enough, count(sm.match_id) "
        "FROM play_session s JOIN play_session_match sm ON sm.session_id = s.id "
        "GROUP BY s.id ORDER BY s.started_at"
    ).fetchall()


@pytest.mark.db
def test_session_report_against_the_days_before(
    db: psycopg.Connection[Any], tmp_path: Path, analysis: Analysis
) -> None:
    store = LocalStore(tmp_path)
    for days in (-5, -4, -3):  # the reference: three earlier days
        add_match(db, store, analysis, at(20, days=days))
    first = add_match(db, store, analysis, at(20))
    add_match(db, store, analysis, at(21.2))  # 30 min after the first one ended
    late = add_match(db, store, analysis, at(23.5))  # 1 h 40 later: another session
    job = SessionJob(store, min_matches=2, min_rounds=5)

    run(job, db, first)
    run(job, db, late)
    assert sessions(db) == [(2, 3, True, 2), (1, 3, True, 1)]

    # The same tables everywhere: the session equals its reference, every delta is 0.
    deltas = db.execute(
        "SELECT basis, delta FROM play_session_metric m JOIN play_session s ON s.id = m.session_id "
        "WHERE s.matches = 2"
    ).fetchall()
    assert len(deltas) == sum(1 for m in REGISTRY.values() if m.kind == "value")
    assert {basis for basis, _ in deltas} == {"value", "per_round"}
    assert all(delta is None or abs(delta) < 1e-9 for _, delta in deltas)

    # A match played in between joins the two sessions into one.
    bridge = add_match(db, store, analysis, at(22.4))
    run(job, db, bridge)
    assert sessions(db) == [(4, 3, True, 4)]


@pytest.mark.db
def test_a_late_match_queues_the_sessions_whose_reference_it_joins(
    db: psycopg.Connection[Any], tmp_path: Path, analysis: Analysis
) -> None:
    store = LocalStore(tmp_path)
    today = add_match(db, store, analysis, at(20))
    job = SessionJob(store)
    run(job, db, today)
    assert db.execute("SELECT count(*) FROM job WHERE kind = 'session'").fetchone() == (0,)

    late = add_match(db, store, analysis, at(20, days=-3))  # sent days after it was played
    run(job, db, late)
    queued = db.execute("SELECT payload FROM job WHERE kind = 'session'").fetchall()
    assert [p for (p,) in queued] == [
        {"steam_id": str(ME), "match_id": str(today), "follow": False}
    ]
    # That job recomputes today's session with the late match in its reference, and stops.
    job(db, queue.Job(2, "session", queued[0][0], 1, 5))
    assert sessions(db) == [(1, 0, False, 1), (1, 1, False, 1)]
    assert db.execute("SELECT count(*) FROM job WHERE kind = 'session'").fetchone() == (1,)


@pytest.mark.db
def test_without_enough_history_the_reference_is_not_shown(
    db: psycopg.Connection[Any], tmp_path: Path, analysis: Analysis
) -> None:
    store = LocalStore(tmp_path)
    match_id = add_match(db, store, analysis, at(20))
    run(SessionJob(store), db, match_id)
    assert sessions(db) == [(1, 0, False, 1)]
    kind = db.execute("SELECT reference_kind FROM play_session").fetchone()
    assert kind == ("none",)  # no level reference published either
    references = db.execute("SELECT count(reference) FROM play_session_metric").fetchone()
    assert references == (0,)


@pytest.mark.db
def test_parsed_matches_queue_a_session_per_invited_player(
    db: psycopg.Connection[Any], tmp_path: Path, analysis: Analysis
) -> None:
    match_id = add_match(db, LocalStore(tmp_path), analysis, at(20))
    assert queue_sessions(db, match_id) == 1  # player 1 is invited, the 9 others are not
    job = queue.claim(db, ["session"], "test")
    assert job is not None
    assert job.payload == {"steam_id": "1", "match_id": str(match_id)}


@pytest.mark.db
def test_the_end_comes_from_the_demo_when_missing(
    db: psycopg.Connection[Any], analysis: Analysis
) -> None:
    row = db.execute(
        "INSERT INTO match (mode, played_at) VALUES ('premier', %s) RETURNING id", (DAY,)
    ).fetchone()
    assert row is not None
    load_match(db, row[0], analysis)
    ended = db.execute("SELECT ended_at FROM match WHERE id = %s", (row[0],)).fetchone()
    match = analysis.tables["match"].row(0, named=True)
    assert ended == (DAY + dt.timedelta(seconds=match["ticks"] / match["tickrate"]),)


@pytest.mark.db
def test_without_history_the_level_reference_steps_in(
    db: psycopg.Connection[Any], tmp_path: Path, analysis: Analysis
) -> None:
    store = LocalStore(tmp_path)
    match_id = add_match(db, store, analysis, at(20))
    db.execute("UPDATE match_player SET rank = 18200 WHERE steam_id = %s", (ME,))
    kills, kast = REGISTRY["base.kills"], REGISTRY["base.kast"]
    db.execute(
        """
        INSERT INTO level_reference (mode, band_low, band_high, used_low, used_high, metric_id,
            version, basis, value, player_matches, players, rounds)
        VALUES ('premier', 17500, 20000, 15000, 22500, %s, %s, 'per_round', 0.5, 812, 140, 17000),
               ('premier', 17500, 20000, 15000, 22500, %s, %s, 'value', 60.0, 812, 140, 17000)
        """,
        (kills.id, kills.version, kast.id, kast.version),
    )
    run(SessionJob(store), db, match_id)
    row = db.execute(
        "SELECT reference_kind, reference_level_low, reference_level_high, reference_matches, "
        "enough FROM play_session"
    ).fetchone()
    assert row == ("level", 15000, 22500, 812, True)
    metrics = {
        r[0]: r[1:]
        for r in db.execute(
            "SELECT metric_id, basis, session, reference, delta FROM play_session_metric"
        ).fetchall()
    }
    basis, session, reference, delta = metrics["base.kills"]
    assert (basis, reference) == ("per_round", 0.5)
    assert delta == pytest.approx(session - 0.5)
    assert metrics["base.kast"][2] == 60.0
    assert metrics["base.adr"][2] is None  # no level value for it: no reference


@pytest.mark.db
def test_the_session_gets_its_priorities_with_their_evidence(
    db: psycopg.Connection[Any], tmp_path: Path, analysis: Analysis
) -> None:
    store = LocalStore(tmp_path)
    match_id = add_match(db, store, analysis, at(20))
    user = db.execute("SELECT id FROM app_user WHERE steam_id = %s", (ME,)).fetchone()
    assert user is not None
    db.execute(
        "INSERT INTO workspace (kind, name, slug, created_by) VALUES ('personal', 'me', 'me', %s)",
        (user[0],),
    )
    db.execute("UPDATE match_player SET rank = 18200 WHERE steam_id = %s", (ME,))
    untraded = REGISTRY["trade.untraded_deaths"]
    # Players of this level never die untraded: player 1's 4 untraded deaths stand out.
    db.execute(
        """
        INSERT INTO level_reference (mode, band_low, band_high, used_low, used_high, metric_id,
            version, basis, value, player_matches, players, rounds)
        VALUES ('premier', 17500, 20000, 17500, 20000, %s, %s, 'per_round', 0.0, 400, 30, 9000)
        """,
        (untraded.id, untraded.version),
    )
    run(SessionJob(store), db, match_id)
    rows = db.execute(
        "SELECT rule_id, priority, message_key, events, rounds_touched, rounds_lost, "
        "message_args, evidence FROM advice ORDER BY priority"
    ).fetchall()
    assert [r[0] for r in rows] == ["trade.untraded_deaths"]
    _, priority, key, events, touched, lost, args, evidence = rows[0]
    assert (priority, key, events) == (1, "advice.trade.untraded_deaths", 4)
    assert 0 <= lost <= touched <= events
    assert args["reference_kind"] == "level"
    assert args["reference"] == 0.0
    assert args["actions"]
    assert len(evidence) == 4
    first = evidence[0]
    assert first["match_id"] == str(match_id)
    tickrate = analysis.tables["match"]["tickrate"][0]
    assert first["goto_tick"] == max(0, first["tick"] - int(5 * tickrate))
    assert {"round", "map", "side", "killer"} <= set(first)

    # Recomputing the session replaces its priorities.
    run(SessionJob(store), db, match_id)
    assert db.execute("SELECT count(*) FROM advice").fetchone() == (1,)
