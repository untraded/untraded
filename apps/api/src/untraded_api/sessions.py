# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The user's play sessions and their report, as the worker computed them (`play_session`).

A session groups matches with at most one hour between the end of one and the start of the
next; its report compares it with the player's own 30 days before. Totals (kills, damage...)
are compared per round (`basis = per_round`).
"""

# No `from __future__ import annotations`: FastAPI reads the dependencies from the annotations.

import datetime as dt
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from untraded_api.deps import ConnDep, UserDep
from untraded_api.matches import LINE, MatchSummary, summary_fields

ROUNDS = "rounds"
"""In `metric_definition.cases`: the metric stands on the rounds played."""

router = APIRouter(prefix="/sessions", tags=["sessions"])

HEADLINES = ("rating.untraded", "rating.hltv1", "base.adr", "base.kast", "trade.untraded_deaths")
"""The metrics shown first, in this order."""


class Comparison(BaseModel):
    metric_id: str
    version: str
    name: str
    unit: str
    better: str
    """`higher`, `lower` or `neutral`: which way is an improvement."""
    basis: str
    """`value`, or `per_round` for totals compared per round played."""
    session: float | None
    reference: float | None
    """Null when the reference is not shown (too little history)."""
    delta: float | None
    cases: int | None
    """What a rate or an average stands on in this session: the rounds played, or its cases
    (the opening duels for the opening success). A rate over 2 cases says little. Null for
    totals, and when a count it rests on is missing."""
    signed: bool
    """The value can be negative (K-D): a gap in % of the reference means nothing for it."""


class PlayedMap(BaseModel):
    """A match of the session, as a list of sessions shows it."""

    match_id: uuid.UUID
    map: str | None
    result: str | None
    """`win`, `loss` or `tie`, for the player; null when the score is unknown."""
    my_score: int | None
    their_score: int | None


class TopPriority(BaseModel):
    """The session's first priority, as a list of sessions shows it (the report has them all)."""

    rule_id: str
    message_key: str
    args: dict[str, Any]
    cost: float
    rounds_touched: int
    rounds_lost: int


class SessionSummary(BaseModel):
    id: uuid.UUID
    started_at: dt.datetime
    ended_at: dt.datetime
    matches: int
    rounds: int
    wins: int
    losses: int
    ties: int
    enough: bool
    """Whether the player had enough history for a reference."""
    headlines: list[Comparison]
    maps: list[PlayedMap]
    """Its matches in the order played."""
    top_priority: TopPriority | None
    """Null when no rule fired on the session."""


class SessionList(BaseModel):
    items: list[SessionSummary]
    limit: int
    offset: int


class Reference(BaseModel):
    kind: str
    """`self` (the player's own days before), `level` (players of the same rating band, pooled
    anonymously) or `none` (too little history, no level published)."""
    level_low: int | None
    level_high: int | None
    """The ratings pooled, for `level`."""
    since: dt.date
    until: dt.date
    """Inclusive: the day before the session."""
    matches: int
    rounds: int
    enough: bool
    min_matches: int
    min_rounds: int


class Advice(BaseModel):
    """A priority: a rule that fired on the session, proved by its events."""

    id: uuid.UUID
    rule_id: str
    rule_version: str
    priority: int
    message_key: str
    """i18n key of the finding; the clients render it in the user's language and tone."""
    args: dict[str, Any]
    """The message's values: metric, unit, basis, session, reference, events, rounds touched
    and lost, actions, indicator, and details such as a zone."""
    evidence: list[dict[str, Any]]
    """The events: match, round, tick, `goto_tick` (for `demo_gototick`), map, side, details."""
    cost: float
    my_vote: int | None
    """The user's 👍 (1) or 👎 (-1), if any."""


class Point(BaseModel):
    session_id: uuid.UUID
    started_at: dt.datetime
    value: float | None


class FollowUp(BaseModel):
    """A priority of the previous session, and how its indicator moved since."""

    rule_id: str
    indicator: str
    name: str
    unit: str
    basis: str
    better: str
    then: float | None
    """The indicator in the session that raised the priority."""
    now: float | None
    """The indicator in this session."""
    reference: float | None
    """This session's reference for it."""
    history: list[Point]
    """The indicator over the player's last sessions, oldest first, this one last."""


class SessionReport(SessionSummary):
    reference: Reference
    match_list: list[MatchSummary]
    metrics: list[Comparison]
    advice: list[Advice]
    """Up to three priorities, most costly first."""
    follow_up: list[FollowUp]
    """The previous session's priorities and their indicators since (vision § 5)."""


# The results are counted per session inside the lateral subquery (no GROUP BY on the outer
# query), so a list ordered by `play_session_recent` and cut by LIMIT counts only the sessions
# it returns, not every session of the player.
SESSION = """
SELECT s.id, s.started_at, s.ended_at, s.matches, s.rounds, s.enough, r.wins, r.losses, r.ties
FROM play_session s
CROSS JOIN LATERAL (
    SELECT count(*) FILTER (WHERE x.result = 'win') AS wins,
           count(*) FILTER (WHERE x.result = 'loss') AS losses,
           count(*) FILTER (WHERE x.result = 'tie') AS ties
    FROM (
        SELECT CASE
            WHEN m.score_a IS NULL THEN NULL
            WHEN (mp.team = 'A') = (m.score_a > m.score_b) AND m.score_a <> m.score_b THEN 'win'
            WHEN m.score_a = m.score_b THEN 'tie'
            ELSE 'loss' END AS result
        FROM play_session_match sm
        JOIN match m ON m.id = sm.match_id
        JOIN match_player mp ON mp.match_id = m.id AND mp.steam_id = s.steam_id
        WHERE sm.session_id = s.id
    ) x
) r
WHERE s.steam_id = (SELECT steam_id FROM app_user WHERE id = %(user)s)
"""

# The session's matches, as the list of matches shows them (`matches.SUMMARY`, same columns).
# SUMMARY joins the view `metric_wide_current`, which aggregates `metric_value` per match and
# player: filtered on a match id (a match page), PostgreSQL pushes the filter into the view;
# joined to the session's matches, it cannot, and aggregates every value of every match in the
# database (each row also checked by the row-level security of metric_value) before the join.
# Here the same pivot runs per match in a lateral subquery, through the primary key of
# metric_value (match_id, steam_id, scope, ...): the cost follows the session, not the database.
# The pivot must stay that of the view (migrations 0001 and 0012); GROUP BY keeps "no row" when
# the player has no value, as the view's LEFT JOIN did.
SESSION_MATCHES = f"""
SELECT m.id, m.played_at, m.ended_at, m.mode::text, m.status::text, m.map, m.score_a,
       m.score_b, m.rounds_played, mp.team, w.match_id IS NOT NULL, {LINE}
FROM play_session_match sm
JOIN match m ON m.id = sm.match_id
LEFT JOIN match_player mp
       ON mp.match_id = m.id
      AND mp.steam_id = (SELECT steam_id FROM app_user WHERE id = %(user)s)
LEFT JOIN LATERAL (
    SELECT v.match_id,
           max(v.value) FILTER (WHERE v.metric_id = 'base.kills') AS kills,
           max(v.value) FILTER (WHERE v.metric_id = 'base.deaths') AS deaths,
           max(v.value) FILTER (WHERE v.metric_id = 'base.adr') AS adr,
           max(v.value) FILTER (WHERE v.metric_id = 'base.kast') AS kast,
           max(v.value) FILTER (WHERE v.metric_id = 'rating.hltv1') AS hltv1,
           max(v.value) FILTER (WHERE v.metric_id = 'trade.untraded_deaths') AS untraded_deaths,
           max(v.value) FILTER (WHERE v.metric_id = 'rating.untraded') AS untraded
    FROM metric_value v
    JOIN metric_current c USING (metric_id, version)
    WHERE v.match_id = m.id AND v.steam_id = mp.steam_id AND v.scope = 'match'
      AND v.params_hash = 'default'
    GROUP BY v.match_id
) w ON true
WHERE sm.session_id = %(session)s
ORDER BY m.played_at, m.id
"""

COMPARISONS = """
SELECT m.session_id, m.metric_id, m.version, d.name, d.unit, d.better, m.basis, m.session,
       m.reference, m.delta, d.signed, d.cases, s.rounds
FROM play_session_metric m
JOIN metric_definition d USING (metric_id, version)
JOIN play_session s ON s.id = m.session_id
WHERE m.session_id = ANY(%(sessions)s)
"""


def _comparison(row: tuple[Any, ...], cases: int | None) -> Comparison:
    return Comparison(
        metric_id=row[1],
        version=row[2],
        name=row[3],
        unit=row[4],
        better=row[5],
        basis=row[6],
        session=row[7],
        reference=row[8],
        delta=row[9],
        cases=cases,
        signed=row[10],
    )


def _cases(of: list[str], rounds: int, per_round: dict[str, float | None]) -> int | None:
    """The number of cases a rate stands on: the rounds, or the sum of its count metrics (stored
    per round in a session)."""
    if not of:
        return None
    if of == [ROUNDS]:
        return rounds
    counts = [per_round.get(metric) for metric in of]
    if any(c is None for c in counts):
        return None
    return round(sum(c for c in counts if c is not None) * rounds)


PLAYED = """
SELECT sm.session_id, m.id, m.map,
       CASE WHEN m.score_a IS NULL THEN NULL
            WHEN m.score_a = m.score_b THEN 'tie'
            WHEN (mp.team = 'A') = (m.score_a > m.score_b) THEN 'win'
            ELSE 'loss' END,
       CASE WHEN mp.team = 'A' THEN m.score_a ELSE m.score_b END,
       CASE WHEN mp.team = 'A' THEN m.score_b ELSE m.score_a END
FROM play_session_match sm
JOIN play_session s ON s.id = sm.session_id
JOIN match m ON m.id = sm.match_id
JOIN match_player mp ON mp.match_id = m.id AND mp.steam_id = s.steam_id
WHERE sm.session_id = ANY(%(sessions)s)
ORDER BY m.played_at, m.id
"""

TOP = """
SELECT session_id, rule_id, message_key, message_args, cost, rounds_touched, rounds_lost
FROM advice WHERE session_id = ANY(%(sessions)s) AND priority = 1
"""


def _extras(
    conn: ConnDep, sessions: list[uuid.UUID]
) -> tuple[dict[uuid.UUID, list[PlayedMap]], dict[uuid.UUID, TopPriority]]:
    """The matches and the first priority of each session, in one query each."""
    played: dict[uuid.UUID, list[PlayedMap]] = {s: [] for s in sessions}
    for r in conn.execute(PLAYED, {"sessions": sessions}):
        played[r[0]].append(
            PlayedMap(match_id=r[1], map=r[2], result=r[3], my_score=r[4], their_score=r[5])
        )
    top = {
        r[0]: TopPriority(
            rule_id=r[1],
            message_key=r[2],
            args=r[3],
            cost=r[4],
            rounds_touched=r[5],
            rounds_lost=r[6],
        )
        for r in conn.execute(TOP, {"sessions": sessions})
    }
    return played, top


def _summary(
    row: tuple[Any, ...],
    comparisons: list[Comparison],
    extras: tuple[dict[uuid.UUID, list[PlayedMap]], dict[uuid.UUID, TopPriority]],
) -> dict[str, Any]:
    by_id = {c.metric_id: c for c in comparisons}
    return {
        "id": row[0],
        "started_at": row[1],
        "ended_at": row[2],
        "matches": row[3],
        "rounds": row[4],
        "enough": row[5],
        "wins": row[6],
        "losses": row[7],
        "ties": row[8],
        "headlines": [by_id[m] for m in HEADLINES if m in by_id],
        "maps": extras[0].get(row[0], []),
        "top_priority": extras[1].get(row[0]),
    }


def _comparisons(conn: ConnDep, sessions: list[uuid.UUID]) -> dict[uuid.UUID, list[Comparison]]:
    found: dict[uuid.UUID, list[Comparison]] = {s: [] for s in sessions}
    rows = conn.execute(f"{COMPARISONS} ORDER BY m.metric_id", {"sessions": sessions}).fetchall()
    per_round: dict[uuid.UUID, dict[str, float | None]] = {s: {} for s in sessions}
    for row in rows:
        per_round[row[0]][row[1]] = row[7]
    for row in rows:
        found[row[0]].append(_comparison(row, _cases(row[11], row[12], per_round[row[0]])))
    return found


@router.get("")
def list_sessions(
    conn: ConnDep,
    user: UserDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SessionList:
    """The user's own sessions, most recent first, with their headline comparisons, their
    maps and their first priority."""
    rows = conn.execute(
        f"{SESSION} ORDER BY s.started_at DESC LIMIT %(limit)s OFFSET %(offset)s",
        {"user": user, "limit": limit, "offset": offset},
    ).fetchall()
    ids = [row[0] for row in rows]
    comparisons = _comparisons(conn, ids)
    extras = _extras(conn, ids)
    return SessionList(
        items=[SessionSummary(**_summary(row, comparisons[row[0]], extras)) for row in rows],
        limit=limit,
        offset=offset,
    )


@router.get("/{session_id}")
def get_session(session_id: uuid.UUID, conn: ConnDep, user: UserDep) -> SessionReport:
    """A session's report: its matches, and every metric against the reference."""
    row = conn.execute(
        f"{SESSION} AND s.id = %(session)s", {"user": user, "session": session_id}
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such session")
    window = conn.execute(
        "SELECT reference_from, reference_to, reference_matches, reference_rounds, params, "
        "reference_kind, reference_level_low, reference_level_high, steam_id, started_at "
        "FROM play_session WHERE id = %s",
        (session_id,),
    ).fetchone()
    assert window is not None
    params = window[4]
    matches = conn.execute(SESSION_MATCHES, {"user": user, "session": session_id}).fetchall()
    comparisons = _comparisons(conn, [session_id])[session_id]
    advice = conn.execute(
        """
        SELECT a.id, a.rule_id, a.rule_version, a.priority, a.message_key, a.message_args,
               a.evidence, a.cost, f.vote
        FROM advice a
        LEFT JOIN advice_feedback f ON f.advice_id = a.id AND f.user_id = %(user)s
        WHERE a.session_id = %(session)s
        ORDER BY a.priority
        """,
        {"user": user, "session": session_id},
    ).fetchall()
    return SessionReport(
        **_summary(row, comparisons, _extras(conn, [session_id])),
        reference=Reference(
            kind=window[5],
            level_low=window[6],
            level_high=window[7],
            since=window[0],
            until=window[1],
            matches=window[2],
            rounds=window[3],
            enough=row[5],
            min_matches=int(params.get("min_matches", 0)),
            min_rounds=int(params.get("min_rounds", 0)),
        ),
        match_list=[MatchSummary(**summary_fields(m)) for m in matches],
        metrics=comparisons,
        advice=[
            Advice(
                id=a[0],
                rule_id=a[1],
                rule_version=a[2],
                priority=a[3],
                message_key=a[4],
                args=a[5],
                evidence=a[6],
                cost=a[7],
                my_vote=a[8],
            )
            for a in advice
        ],
        follow_up=_follow_up(conn, session_id, window[8], window[9]),
    )


HISTORY = 5
"""Sessions shown in an indicator's history."""


def _follow_up(
    conn: ConnDep, session_id: uuid.UUID, steam_id: int, started_at: dt.datetime
) -> list[FollowUp]:
    previous = conn.execute(
        "SELECT id FROM play_session WHERE steam_id = %s AND started_at < %s "
        "ORDER BY started_at DESC LIMIT 1",
        (steam_id, started_at),
    ).fetchone()
    if previous is None:
        return []
    raised = conn.execute(
        "SELECT rule_id, message_args->>'indicator' FROM advice "
        "WHERE session_id = %s ORDER BY priority",
        (previous[0],),
    ).fetchall()
    found = []
    for rule_id, indicator in raised:
        definition = conn.execute(
            "SELECT d.name, d.unit, d.better FROM metric_current c "
            "JOIN metric_definition d USING (metric_id, version) WHERE c.metric_id = %s",
            (indicator,),
        ).fetchone()
        if definition is None:
            continue
        rows = conn.execute(
            """
            SELECT ps.id, ps.started_at, m.session, m.reference, m.basis
            FROM play_session ps
            JOIN play_session_metric m ON m.session_id = ps.id AND m.metric_id = %(metric)s
            JOIN metric_current c ON c.metric_id = m.metric_id AND c.version = m.version
            WHERE ps.steam_id = %(steam)s AND ps.started_at <= %(start)s
            ORDER BY ps.started_at DESC
            LIMIT %(limit)s
            """,
            {"metric": indicator, "steam": steam_id, "start": started_at, "limit": HISTORY},
        ).fetchall()
        by_session = {r[0]: r for r in rows}
        current, then = by_session.get(session_id), by_session.get(previous[0])
        found.append(
            FollowUp(
                rule_id=rule_id,
                indicator=indicator,
                name=definition[0],
                unit=definition[1],
                basis=(current or then or (None, None, None, None, "value"))[4],
                better=definition[2],
                then=then[2] if then else None,
                now=current[2] if current else None,
                reference=current[3] if current else None,
                history=[
                    Point(session_id=r[0], started_at=r[1], value=r[2]) for r in reversed(rows)
                ],
            )
        )
    return found
