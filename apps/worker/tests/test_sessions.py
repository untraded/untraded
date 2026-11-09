# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import dataclasses
import datetime as dt
import shutil
import uuid
from pathlib import Path
from typing import Any

import polars as pl
import psycopg
import pytest

from untraded import reference
from untraded.advice import Finding
from untraded.metrics import REGISTRY
from untraded_worker import advice, queue, spread
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


def fake_finding(rule: str, cost: float, ticks: list[int], match: str = "m") -> Finding:
    return Finding(
        rule=rule,
        rule_version="1.0.0",
        metric="trade.untraded_deaths",
        metric_version=REGISTRY["trade.untraded_deaths"].version,
        basis="per_round",
        session=1.0,
        reference=0.5,
        evidence=pl.DataFrame(
            {"match_id": [match] * len(ticks), "round": [1] * len(ticks), "tick": ticks}
        ),
        rounds_touched=1,
        rounds_lost=1,
        cost=cost,
        message_key=f"advice.{rule}",
        actions=("adjust.trade_distance",),
        indicator="trade.untraded_deaths",
    )


def test_the_other_findings_are_numbered_past_the_priorities() -> None:
    a, b, c, d, e = (fake_finding(r, 1.0, [1]) for r in "abcde")
    assert [(n, f.rule) for n, f in advice.numbered([a, b, c], [d, e])] == [
        (1, "a"),
        (2, "b"),
        (3, "c"),
        (4, "d"),
        (5, "e"),
    ]
    # With fewer priorities too: the numbers up to 3 stay the priorities'.
    assert [(n, f.rule) for n, f in advice.numbered([a, b], [c])] == [
        (1, "a"),
        (2, "b"),
        (4, "c"),
    ]


def test_a_finding_stores_a_bounded_number_of_events() -> None:
    found = fake_finding("a", 1.0, list(range(advice.MAX_EVIDENCE + 50)))
    rows = advice.evidence_rows(found, {"m": uuid.uuid4()}, {"m": 64.0})
    assert len(rows) == advice.MAX_EVIDENCE
    assert found.events == advice.MAX_EVIDENCE + 50


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
    db.execute(
        "INSERT INTO match_source (match_id, kind, external_id) VALUES (%s, 'valve_bot', %s)",
        (match_id, str(match_id)),
    )
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
def test_a_metric_version_no_parse_recorded_yet_is_recorded_by_the_session(
    db: psycopg.Connection[Any],
    tmp_path: Path,
    analysis: Analysis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = LocalStore(tmp_path)
    match_id = add_match(db, store, analysis, at(20))
    # An update bumps a metric after the match was parsed: its new version is in no table yet.
    bumped = dataclasses.replace(REGISTRY["base.kills"], version="9.9.9")
    monkeypatch.setitem(REGISTRY, "base.kills", bumped)
    run(SessionJob(store), db, match_id)
    saved = db.execute(
        "SELECT version FROM play_session_metric WHERE metric_id = 'base.kills'"
    ).fetchone()
    assert saved == ("9.9.9",)


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
@pytest.mark.parametrize(
    "erase",
    [
        pytest.param("UPDATE app_user SET deleted_at = now() WHERE steam_id = %s", id="asked"),
        pytest.param("DELETE FROM app_user WHERE steam_id = %s", id="done"),
    ],
)
def test_a_queued_job_writes_nothing_for_an_erased_player(
    db: psycopg.Connection[Any], tmp_path: Path, analysis: Analysis, erase: str
) -> None:
    store = LocalStore(tmp_path)
    earlier = add_match(db, store, analysis, at(20))
    # The match stays when it counts for someone else; a later session would follow from this job.
    add_match(db, store, analysis, at(20, days=2))
    db.execute(erase, (ME,))
    run(SessionJob(store), db, earlier)
    assert sessions(db) == []
    assert queue.claim(db, ["session"], "test") is None


@pytest.mark.db
def test_a_job_finding_its_player_erased_removes_itself(
    db: psycopg.Connection[Any], tmp_path: Path
) -> None:
    queue.enqueue(db, "session", {"steam_id": str(ME), "match_id": str(uuid.uuid4())})
    claimed = queue.claim(db, ["session"], "test")
    assert claimed is not None
    db.execute("DELETE FROM app_user WHERE steam_id = %s", (ME,))
    SessionJob(LocalStore(tmp_path))(db, claimed)
    queue.complete(db, claimed)  # as the runner does, on a row now gone
    assert db.execute("SELECT count(*) FROM job").fetchone() == (0,)


@pytest.mark.db
def test_a_registered_player_still_gets_a_session(
    db: psycopg.Connection[Any], tmp_path: Path, analysis: Analysis
) -> None:
    store = LocalStore(tmp_path)
    run(SessionJob(store), db, add_match(db, store, analysis, at(20)))
    assert len(sessions(db)) == 1


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


def as_written_before_the_spread(db: psycopg.Connection[Any]) -> None:
    """The sessions as the worker wrote them before migration 0015: no spread, and no
    `min_spread_matches` in their parameters (the session job writes it now)."""
    db.execute("UPDATE play_session SET params = params - 'min_spread_matches'")
    db.execute("UPDATE play_session_metric SET reference_p10 = NULL, reference_p90 = NULL")


def level_references(db: psycopg.Connection[Any], *, spread_of_kills: bool) -> None:
    """A level reference for the band of 18,200, with a spread for the kills only (or none)."""
    kills, kast = REGISTRY["base.kills"], REGISTRY["base.kast"]
    db.execute(
        """
        INSERT INTO level_reference (mode, band_low, band_high, used_low, used_high, metric_id,
            version, basis, value, p10, p90, player_matches, players, rounds)
        VALUES ('premier', 17500, 20000, 15000, 22500, %s, %s, 'per_round', 0.5, %s, %s, 812, 140,
                17000),
               ('premier', 17500, 20000, 15000, 22500, %s, %s, 'value', 60.0, NULL, NULL, 812,
                140, 17000)
        """,
        (
            kills.id,
            kills.version,
            0.2 if spread_of_kills else None,
            0.9 if spread_of_kills else None,
            kast.id,
            kast.version,
        ),
    )


def spreads(db: psycopg.Connection[Any]) -> dict[str, tuple[Any, ...]]:
    return {
        r[0]: r[1:]
        for r in db.execute(
            "SELECT metric_id, reference, reference_p10, reference_p90 FROM play_session_metric"
        ).fetchall()
    }


@pytest.mark.db
def test_the_level_spread_is_stored_with_the_reference(
    db: psycopg.Connection[Any], tmp_path: Path, analysis: Analysis
) -> None:
    store = LocalStore(tmp_path)
    match_id = add_match(db, store, analysis, at(20))
    db.execute("UPDATE match_player SET rank = 18200 WHERE steam_id = %s", (ME,))
    level_references(db, spread_of_kills=True)
    run(SessionJob(store), db, match_id)
    found = spreads(db)
    assert found["base.kills"] == (0.5, 0.2, 0.9)
    assert found["base.kast"] == (60.0, None, None)  # a reference without a spread
    assert found["base.adr"] == (None, None, None)  # no reference: no band


@pytest.mark.db
def test_the_spread_of_the_days_before_is_stored(
    db: psycopg.Connection[Any],
    tmp_path: Path,
    analysis: Analysis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(reference, "MIN_SPREAD_ROUNDS", 5)  # the fixture plays 5 rounds
    store = LocalStore(tmp_path)
    for days in (-5, -4, -3):
        add_match(db, store, analysis, at(20, days=days))
    match_id = add_match(db, store, analysis, at(20))
    # Three matches are not enough for the default minimum (10): the reference, but no band.
    run(SessionJob(store, min_matches=2, min_rounds=5), db, match_id)
    found = spreads(db)["base.kills"]
    assert found[0] is not None
    assert found[1:] == (None, None)
    # With a minimum of 3, the band is there; identical matches: it is the value itself.
    run(SessionJob(store, min_matches=2, min_rounds=5, min_spread_matches=3), db, match_id)
    reference_value, p10, p90 = spreads(db)["base.kills"]
    assert p10 == pytest.approx(reference_value)
    assert p90 == pytest.approx(reference_value)


@pytest.mark.db
def test_backfill_fills_the_spread_of_old_sessions_without_recomputing_them(
    db: psycopg.Connection[Any],
    tmp_path: Path,
    analysis: Analysis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(reference, "MIN_SPREAD_ROUNDS", 5)
    store = LocalStore(tmp_path)
    for days in (-5, -4, -3):
        add_match(db, store, analysis, at(20, days=days))
    match_id = add_match(db, store, analysis, at(20))
    run(SessionJob(store, min_matches=2, min_rounds=5), db, match_id)
    as_written_before_the_spread(db)
    before = db.execute(
        "SELECT s.id, s.computed_at, m.metric_id, m.session, m.reference, m.delta "
        "FROM play_session s JOIN play_session_metric m ON m.session_id = s.id "
        "ORDER BY m.metric_id"
    ).fetchall()
    assert spreads(db)["base.kills"][1:] == (None, None)

    # Too few matches for the default minimum: nothing to fill, nothing touched.
    assert spread.backfill(db, store, refresh_levels=False) == 0
    assert spreads(db)["base.kills"][1:] == (None, None)

    assert spread.backfill(db, store, min_spread_matches=3, refresh_levels=False) == 1
    value, p10, p90 = spreads(db)["base.kills"]
    assert p10 == pytest.approx(value)
    assert p90 == pytest.approx(value)
    # Only the two columns changed: same session, same computation, same numbers.
    after = db.execute(
        "SELECT s.id, s.computed_at, m.metric_id, m.session, m.reference, m.delta "
        "FROM play_session s JOIN play_session_metric m ON m.session_id = s.id "
        "ORDER BY m.metric_id"
    ).fetchall()
    assert after == before
    # Run again: the session is marked as visited, nothing is left to do.
    assert spread.backfill(db, store, min_spread_matches=3, refresh_levels=False) == 0
    # Without the mark, a spread that is there is never overwritten, and a missing one is filled.
    db.execute("UPDATE play_session SET params = params - 'min_spread_matches'")
    db.execute("UPDATE play_session_metric SET reference_p10 = -1 WHERE metric_id = 'base.kills'")
    db.execute(
        "UPDATE play_session_metric SET reference_p10 = NULL, reference_p90 = NULL "
        "WHERE metric_id = 'base.adr'"
    )
    assert spread.backfill(db, store, min_spread_matches=3, refresh_levels=False) == 1
    assert spreads(db)["base.kills"][1] == -1
    assert spreads(db)["base.adr"][1] is not None


@pytest.mark.db
def test_backfill_fills_a_session_against_a_level_from_its_band(
    db: psycopg.Connection[Any], tmp_path: Path, analysis: Analysis
) -> None:
    store = LocalStore(tmp_path)
    match_id = add_match(db, store, analysis, at(20))
    db.execute("UPDATE match_player SET rank = 18200 WHERE steam_id = %s", (ME,))
    level_references(db, spread_of_kills=False)  # the session as written before the migration
    run(SessionJob(store), db, match_id)
    as_written_before_the_spread(db)
    assert spreads(db)["base.kills"] == (0.5, None, None)
    db.execute("UPDATE level_reference SET p10 = 0.2, p90 = 0.9 WHERE basis = 'per_round'")
    assert spread.backfill(db, store, refresh_levels=False) == 1
    assert spreads(db)["base.kills"] == (0.5, 0.2, 0.9)
    assert spreads(db)["base.kast"] == (60.0, None, None)
    assert spread.backfill(db, store, refresh_levels=False) == 0


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


@pytest.mark.db
def test_every_finding_is_stored_past_the_priorities(
    db: psycopg.Connection[Any],
    tmp_path: Path,
    analysis: Analysis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = LocalStore(tmp_path)
    match_id = add_match(db, store, analysis, at(20))
    user = db.execute("SELECT id FROM app_user WHERE steam_id = %s", (ME,)).fetchone()
    assert user is not None
    db.execute(
        "INSERT INTO workspace (kind, name, slug, created_by) VALUES ('personal', 'me', 'me', %s)",
        (user[0],),
    )
    sha = match_id.hex * 2  # as `add_match` names it
    findings = [
        fake_finding("a", 5.0, [1, 2, 3], sha),
        fake_finding("skipped", 4.0, [1, 2, 3], sha),  # the same events as `a`
        fake_finding("b", 3.0, [4], sha),
    ]
    monkeypatch.setattr(advice, "find", lambda *_, **__: findings)
    run(SessionJob(store), db, match_id)
    rows = db.execute("SELECT rule_id, priority, evidence FROM advice ORDER BY priority").fetchall()
    # Two priorities only: the other finding still starts at 4, or a reader would take it for one.
    assert [(r[0], r[1]) for r in rows] == [("a", 1), ("b", 2), ("skipped", 4)]
    assert rows[2][2][0]["match_id"] == str(match_id)


def with_workspace(db: psycopg.Connection[Any]) -> Any:
    user = db.execute("SELECT id FROM app_user WHERE steam_id = %s", (ME,)).fetchone()
    assert user is not None
    db.execute(
        "INSERT INTO workspace (kind, name, slug, created_by) VALUES ('personal', 'me', 'me', %s)",
        (user[0],),
    )
    return user[0]


def vote(
    db: psycopg.Connection[Any],
    user: Any,
    match_id: uuid.UUID,
    value: int,
    at_: dt.datetime = DAY,
    comment: str | None = None,
) -> None:
    db.execute(
        """
        INSERT INTO advice_feedback (advice_id, user_id, vote, comment, created_at)
        SELECT a.id, %s::uuid, %s::smallint, %s::text, %s::timestamptz FROM advice a
        JOIN play_session_match sm ON sm.session_id = a.session_id
        WHERE sm.match_id = %s AND a.rule_id = 'a'
        """,
        (user, value, comment, at_, match_id),
    )


def votes(db: psycopg.Connection[Any]) -> list[tuple[Any, ...]]:
    return db.execute(
        "SELECT a.rule_id, f.vote, f.comment, f.created_at FROM advice_feedback f "
        "JOIN advice a ON a.id = f.advice_id ORDER BY a.rule_id"
    ).fetchall()


def firing(monkeypatch: pytest.MonkeyPatch, *findings: Finding) -> None:
    """`advice.find` gives these findings, on the session's first match."""
    monkeypatch.setattr(
        advice,
        "find",
        lambda ds, *_, **__: [
            dataclasses.replace(
                f,
                evidence=f.evidence.with_columns(
                    pl.lit(ds.played["match_id"][0]).alias("match_id")
                ),
            )
            for f in findings
        ],
    )


@pytest.mark.db
def test_a_recomputed_session_keeps_its_votes(
    db: psycopg.Connection[Any],
    tmp_path: Path,
    analysis: Analysis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = LocalStore(tmp_path)
    user = with_workspace(db)
    match_id = add_match(db, store, analysis, at(20))
    firing(monkeypatch, fake_finding("a", 5.0, [1]), fake_finding("b", 3.0, [2]))
    run(SessionJob(store), db, match_id)
    vote(db, user, match_id, -1, comment="not my fault")
    run(SessionJob(store), db, match_id)
    # On the new row of the finding, as it was; the finding nobody voted on gets no vote.
    assert votes(db) == [("a", -1, "not my fault", DAY)]
    assert db.execute("SELECT count(*) FROM advice").fetchone() == (2,)
    # And again: a forced analysis recomputes a session once per match.
    run(SessionJob(store), db, match_id)
    assert votes(db) == [("a", -1, "not my fault", DAY)]


@pytest.mark.db
@pytest.mark.parametrize(
    "after",
    [
        pytest.param(lambda f: dataclasses.replace(f, rule="other"), id="no-longer-fires"),
        pytest.param(lambda f: dataclasses.replace(f, rule_version="2.0.0"), id="new-version"),
        pytest.param(
            lambda f: dataclasses.replace(f, details={"map": "m", "side": "T", "zone": "A"}),
            id="another-spot",
        ),
    ],
)
def test_a_vote_stays_with_what_it_judged(
    db: psycopg.Connection[Any],
    tmp_path: Path,
    analysis: Analysis,
    monkeypatch: pytest.MonkeyPatch,
    after: Any,
) -> None:
    store = LocalStore(tmp_path)
    user = with_workspace(db)
    match_id = add_match(db, store, analysis, at(20))
    spot = dataclasses.replace(
        fake_finding("a", 5.0, [1]), details={"map": "m", "side": "CT", "zone": "A"}
    )
    firing(monkeypatch, spot)
    run(SessionJob(store), db, match_id)
    vote(db, user, match_id, 1)
    assert len(votes(db)) == 1
    firing(monkeypatch, after(spot))
    run(SessionJob(store), db, match_id)
    assert votes(db) == []


@pytest.mark.db
def test_the_same_spot_keeps_its_vote(
    db: psycopg.Connection[Any],
    tmp_path: Path,
    analysis: Analysis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = LocalStore(tmp_path)
    user = with_workspace(db)
    match_id = add_match(db, store, analysis, at(20))
    firing(
        monkeypatch,
        dataclasses.replace(
            fake_finding("a", 5.0, [1]), details={"map": "m", "side": "CT", "zone": "A"}
        ),
    )
    run(SessionJob(store), db, match_id)
    vote(db, user, match_id, 1)
    run(SessionJob(store), db, match_id)
    assert [v[:2] for v in votes(db)] == [("a", 1)]


@pytest.mark.db
def test_merged_sessions_keep_the_latest_vote(
    db: psycopg.Connection[Any],
    tmp_path: Path,
    analysis: Analysis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = LocalStore(tmp_path)
    user = with_workspace(db)
    firing(monkeypatch, fake_finding("a", 5.0, [1]))
    early = add_match(db, store, analysis, at(18))  # until 18:40
    late = add_match(db, store, analysis, at(20.5))  # from 20:30: two sessions
    run(SessionJob(store), db, early)
    run(SessionJob(store), db, late)
    latest = DAY + dt.timedelta(hours=2)
    vote(db, user, late, -1, latest)
    vote(db, user, early, 1, DAY)  # written last, but the older vote: the date decides
    between = add_match(db, store, analysis, at(19.4))  # 19:24 to 20:04 joins them
    run(SessionJob(store), db, between)
    assert db.execute("SELECT count(*) FROM play_session").fetchone() == (1,)
    assert votes(db) == [("a", -1, None, latest)]


@pytest.mark.db
def test_a_vote_is_only_kept_for_the_player_of_the_session(
    db: psycopg.Connection[Any],
    tmp_path: Path,
    analysis: Analysis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = LocalStore(tmp_path)
    user = with_workspace(db)
    match_id = add_match(db, store, analysis, at(20))
    firing(monkeypatch, fake_finding("a", 5.0, [1]))
    run(SessionJob(store), db, match_id)
    vote(db, user, match_id, 1)
    # Another player of the same match: their session does not read, or take, this vote.
    assert advice.votes_on_sessions_of(db, ME + 1, [match_id]) == []
    assert len(advice.votes_on_sessions_of(db, ME, [match_id])) == 1


def count_match_values(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Counts the matches the spread is computed over (`reference.match_values` calls)."""
    calls: list[int] = []
    original = reference.match_values

    def counting(*args: Any, **kwargs: Any) -> Any:
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(reference, "match_values", counting)
    return calls


@pytest.mark.db
def test_backfill_reads_the_stored_window_and_leaves_the_session_out(
    db: psycopg.Connection[Any],
    tmp_path: Path,
    analysis: Analysis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(reference, "MIN_SPREAD_ROUNDS", 5)
    store = LocalStore(tmp_path)
    for days in (-5, -4, -3):  # in the window
        add_match(db, store, analysis, at(20, days=days))
    add_match(db, store, analysis, at(20, days=-40))  # before the window
    first = add_match(db, store, analysis, at(20))
    add_match(db, store, analysis, at(21.2))  # in the session
    add_match(db, store, analysis, at(20, days=2))  # after it
    run(SessionJob(store, min_matches=2, min_rounds=5), db, first)
    as_written_before_the_spread(db)
    calls = count_match_values(monkeypatch)
    assert spread.backfill(db, store, min_spread_matches=3, refresh_levels=False) == 1
    # The three matches of the window: not the older one, nor the session's, nor the later one.
    assert len(calls) == 3


@pytest.mark.db
def test_backfill_skips_a_session_it_cannot_read_and_fills_the_others(
    db: psycopg.Connection[Any],
    tmp_path: Path,
    analysis: Analysis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(reference, "MIN_SPREAD_ROUNDS", 5)
    store = LocalStore(tmp_path)
    job = SessionJob(store, min_matches=2, min_rounds=5)
    broken = [add_match(db, store, analysis, at(20, days=d)) for d in (-5, -4, -3)]
    run(job, db, add_match(db, store, analysis, at(20)))  # session A, a month and more before B
    for d in (95, 96, 97):
        add_match(db, store, analysis, at(20, days=d))
    run(job, db, add_match(db, store, analysis, at(20, days=100)))  # session B
    as_written_before_the_spread(db)
    shutil.rmtree(tmp_path / f"matches/{broken[0]}")  # A's reference can no longer be read

    assert spread.backfill(db, store, min_spread_matches=3, refresh_levels=False) == 1
    filled = {
        r[0]: r[1:]
        for r in db.execute(
            "SELECT s.started_at, count(m.reference_p10), s.params ? 'min_spread_matches' "
            "FROM play_session s JOIN play_session_metric m ON m.session_id = s.id "
            "GROUP BY s.id ORDER BY s.started_at"
        ).fetchall()
    }
    (a, b) = filled.values()
    assert a[0] == 0  # the unreadable session: rolled back, nothing written
    assert b[0] > 0  # the other one is filled
    # Only the filled one is marked as visited: the next run tries the other again.
    marked = db.execute(
        "SELECT s.params ? 'min_spread_matches' FROM play_session s ORDER BY s.started_at"
    ).fetchall()
    assert marked == [(False,), (True,)]


@pytest.mark.db
def test_backfill_only_fills_the_current_version_of_a_metric(
    db: psycopg.Connection[Any],
    tmp_path: Path,
    analysis: Analysis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(reference, "MIN_SPREAD_ROUNDS", 5)
    store = LocalStore(tmp_path)
    for days in (-5, -4, -3):
        add_match(db, store, analysis, at(20, days=days))
    match_id = add_match(db, store, analysis, at(20))
    run(SessionJob(store, min_matches=2, min_rounds=5), db, match_id)
    as_written_before_the_spread(db)
    # Make the kills row one of an older version of the metric.
    db.execute(
        "INSERT INTO metric_definition (metric_id, version, name, unit, kind, params, doc) "
        "VALUES ('base.kills', '0.9.0', 'Kills', 'count', 'value', '{}', '')"
    )
    db.execute(
        "UPDATE play_session_metric SET version = '0.9.0', reference_p10 = NULL, "
        "reference_p90 = NULL WHERE metric_id = 'base.kills'"
    )
    spread.backfill(db, store, min_spread_matches=3, refresh_levels=False)
    kills = db.execute(
        "SELECT reference_p10 FROM play_session_metric WHERE metric_id = 'base.kills'"
    ).fetchone()
    assert kills == (None,)  # its reference was not computed by today's formula
    other = db.execute(
        "SELECT count(reference_p10) FROM play_session_metric WHERE metric_id <> 'base.kills'"
    ).fetchone()
    assert other is not None
    assert other[0] > 0


@pytest.mark.db
def test_backfill_visits_nothing_the_second_time(
    db: psycopg.Connection[Any],
    tmp_path: Path,
    analysis: Analysis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(reference, "MIN_SPREAD_ROUNDS", 5)
    store = LocalStore(tmp_path)
    for days in (-5, -4, -3):
        add_match(db, store, analysis, at(20, days=days))
    match_id = add_match(db, store, analysis, at(20))
    run(SessionJob(store, min_matches=2, min_rounds=5), db, match_id)
    as_written_before_the_spread(db)
    # A session is visited once, then left alone: a run that has nothing to do reads no match.
    assert spread.backfill(db, store, min_spread_matches=3, refresh_levels=False) == 1
    calls = count_match_values(monkeypatch)
    assert spread.backfill(db, store, min_spread_matches=3, refresh_levels=False) == 0
    assert calls == []
