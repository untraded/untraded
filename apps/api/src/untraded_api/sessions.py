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
from untraded_api.matches import SUMMARY, MatchSummary, summary_fields

router = APIRouter(prefix="/sessions", tags=["sessions"])

HEADLINES = ("rating.hltv1", "base.adr", "base.kast", "trade.untraded_deaths")
"""The metrics shown first, in this order."""


class Comparison(BaseModel):
    metric_id: str
    version: str
    name: str
    unit: str
    basis: str
    """`value`, or `per_round` for totals compared per round played."""
    session: float | None
    reference: float | None
    """Null when the reference is not shown (too little history)."""
    delta: float | None


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


class SessionList(BaseModel):
    items: list[SessionSummary]
    limit: int
    offset: int


class Reference(BaseModel):
    since: dt.date
    until: dt.date
    """Inclusive: the day before the session."""
    matches: int
    rounds: int
    enough: bool
    min_matches: int
    min_rounds: int


class SessionReport(SessionSummary):
    reference: Reference
    match_list: list[MatchSummary]
    metrics: list[Comparison]


SESSION = """
SELECT s.id, s.started_at, s.ended_at, s.matches, s.rounds, s.enough,
       count(*) FILTER (WHERE r.result = 'win'),
       count(*) FILTER (WHERE r.result = 'loss'),
       count(*) FILTER (WHERE r.result = 'tie')
FROM play_session s
LEFT JOIN LATERAL (
    SELECT CASE
        WHEN m.score_a IS NULL THEN NULL
        WHEN (mp.team = 'A') = (m.score_a > m.score_b) AND m.score_a <> m.score_b THEN 'win'
        WHEN m.score_a = m.score_b THEN 'tie'
        ELSE 'loss' END AS result
    FROM play_session_match sm
    JOIN match m ON m.id = sm.match_id
    JOIN match_player mp ON mp.match_id = m.id AND mp.steam_id = s.steam_id
    WHERE sm.session_id = s.id
) r ON true
WHERE s.steam_id = (SELECT steam_id FROM app_user WHERE id = %(user)s)
"""

COMPARISONS = """
SELECT m.session_id, m.metric_id, m.version, d.name, d.unit, m.basis, m.session, m.reference,
       m.delta
FROM play_session_metric m
JOIN metric_definition d USING (metric_id, version)
WHERE m.session_id = ANY(%(sessions)s)
"""


def _comparison(row: tuple[Any, ...]) -> Comparison:
    return Comparison(
        metric_id=row[1],
        version=row[2],
        name=row[3],
        unit=row[4],
        basis=row[5],
        session=row[6],
        reference=row[7],
        delta=row[8],
    )


def _summary(row: tuple[Any, ...], comparisons: list[Comparison]) -> dict[str, Any]:
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
    }


def _comparisons(conn: ConnDep, sessions: list[uuid.UUID]) -> dict[uuid.UUID, list[Comparison]]:
    found: dict[uuid.UUID, list[Comparison]] = {s: [] for s in sessions}
    for row in conn.execute(f"{COMPARISONS} ORDER BY m.metric_id", {"sessions": sessions}):
        found[row[0]].append(_comparison(row))
    return found


@router.get("")
def list_sessions(
    conn: ConnDep,
    user: UserDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SessionList:
    """The user's own sessions, most recent first, with their headline comparisons."""
    rows = conn.execute(
        f"{SESSION} GROUP BY s.id ORDER BY s.started_at DESC LIMIT %(limit)s OFFSET %(offset)s",
        {"user": user, "limit": limit, "offset": offset},
    ).fetchall()
    comparisons = _comparisons(conn, [row[0] for row in rows])
    return SessionList(
        items=[SessionSummary(**_summary(row, comparisons[row[0]])) for row in rows],
        limit=limit,
        offset=offset,
    )


@router.get("/{session_id}")
def get_session(session_id: uuid.UUID, conn: ConnDep, user: UserDep) -> SessionReport:
    """A session's report: its matches, and every metric against the reference."""
    row = conn.execute(
        f"{SESSION} AND s.id = %(session)s GROUP BY s.id", {"user": user, "session": session_id}
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such session")
    window = conn.execute(
        "SELECT reference_from, reference_to, reference_matches, reference_rounds, params "
        "FROM play_session WHERE id = %s",
        (session_id,),
    ).fetchone()
    assert window is not None
    params = window[4]
    matches = conn.execute(
        f"""{SUMMARY}
        JOIN play_session_match sm ON sm.match_id = m.id AND sm.session_id = %(session)s
        ORDER BY m.played_at""",
        {"user": user, "session": session_id},
    ).fetchall()
    comparisons = _comparisons(conn, [session_id])[session_id]
    return SessionReport(
        **_summary(row, comparisons),
        reference=Reference(
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
    )
