# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""A team's matches: the list, a match page read from the team's side, and the team's overview.

A team sees the matches of its `workspace_match` rows, whatever the reason (`roster`, `shared`,
and later the team's own uploads), as the worker keeps them (ADR 0012). Reading them takes being
a member (404 `team_not_found` otherwise, as for the team itself) and `matches.read` (403
`forbidden`). A match the team does not see is a 404 here, even when the user sees it through
their personal workspace: the team's space shows the team's matches only.

"Our side" is computed when read, not stored: the side where at least 3 players of the team's
active roster on the match's date played (the worker's rule for `roster`, without its credit and
consent conditions, which decide whether the team sees the match, not on which side it played).
A player who has left the roster since still counts for the matches played before. It is null
when no side has 3 of them (a shared solo match) or both have (a match inside the team).

These routes read match data only: a player's sessions, advice, votes and aggregates are closed to
a team by row-level security (migration 0016), and nothing here reads them.
"""

# No `from __future__ import annotations`: FastAPI reads the dependencies from the annotations.

import datetime as dt
import uuid
from typing import Annotated, Any, Literal

import psycopg
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from untraded_api.deps import ConnDep
from untraded_api.matches import LINE, PlayerLine, Round, line, match_rounds, result, wide_line
from untraded_api.teams import Slug, team_id

router = APIRouter(tags=["teams"])

Side = Literal["A", "B"]
RECORD_DAYS = 30
RECENT = 5


class TeamPlayerRef(BaseModel):
    steam_id: str
    name: str
    """The name in that match."""
    team: Side


class TeamMatchSummary(BaseModel):
    id: uuid.UUID
    played_at: dt.datetime | None
    ended_at: dt.datetime | None
    mode: str
    status: str
    map: str | None
    score_a: int | None
    score_b: int | None
    rounds_played: int | None
    reason: str
    """Why the team sees it: `roster`, `shared` (and later `team`, its own uploads)."""
    our_team: Side | None
    """The side of 3 or more of the team's roster players on the match's date."""
    our_result: str | None
    """`win`, `loss` or `tie` from our side, when it is known and the match is parsed."""
    team_players: list[TeamPlayerRef]
    """The match's players who are members of the team now, or were on its roster on the match's
    date; by side, then name."""


class TeamMatchList(BaseModel):
    items: list[TeamMatchSummary]
    limit: int
    offset: int


class TeamMatchPlayer(BaseModel):
    steam_id: str
    name: str
    team: Side
    rank: int | None
    rounds_on_team: int
    line: PlayerLine
    member: bool
    """A member of the team now, or on its roster on the match's date."""


class TeamMatchDetail(TeamMatchSummary):
    team_a_name: str | None
    team_b_name: str | None
    tickrate: float | None
    unavailable: list[str]
    error: str | None
    rounds: list[Round]
    players: list[TeamMatchPlayer]


class TeamRecord(BaseModel):
    days: int
    wins: int
    losses: int
    ties: int


class TeamOverview(BaseModel):
    matches: int
    """Every match the team sees."""
    recent: list[TeamMatchSummary]
    record: TeamRecord
    """The parsed matches of the last `days` days whose side is known, from our side."""


# The match's date, as the worker reads it to apply the roster rule (`load.refresh_access`).
MATCH_DATE = "coalesce(m.played_at::date, current_date)"

ON_ROSTER = f"""EXISTS (
    SELECT 1 FROM roster_member rm JOIN roster r ON r.id = rm.roster_id AND r.active
    WHERE r.workspace_id = %(team)s AND rm.steam_id = mp.steam_id
      AND rm.valid_from <= {MATCH_DATE}
      AND (rm.valid_to IS NULL OR rm.valid_to >= {MATCH_DATE}))"""
"""A SQL condition: the player `mp` was on the team's roster on the date of the match `m`."""

MEMBER = f"""({ON_ROSTER} OR EXISTS (
    SELECT 1 FROM membership ms JOIN app_user u ON u.id = ms.user_id AND u.deleted_at IS NULL
    WHERE ms.workspace_id = %(team)s AND u.steam_id = mp.steam_id))"""
"""A SQL condition: the player `mp` is a member of the team now, or was on its roster on the date
of the match `m`."""

OUR_TEAM = f"""
SELECT CASE WHEN count(*) = 1 THEN min(sides.side) END AS team
FROM (
    SELECT mp.team AS side
    FROM match_player mp
    WHERE mp.match_id = m.id AND {ON_ROSTER}
    GROUP BY mp.team
    HAVING count(*) >= 3
) sides
"""
"""Our side in the match `m` (one row, its `team` null when no side or both sides qualify)."""

TEAM_PLAYERS = f"""
SELECT coalesce(json_agg(json_build_object(
           'steam_id', mp.steam_id::text, 'name', mp.name, 'team', mp.team)
           ORDER BY mp.team, lower(mp.name), mp.steam_id), '[]'::json) AS players
FROM match_player mp
WHERE mp.match_id = m.id AND {MEMBER}
"""

ORDER = "m.played_at DESC NULLS LAST, m.created_at DESC, m.id"


def team_matches(where: str = "") -> str:
    """The team's matches (`workspace_match`, any reason), aliased `m` with their `reason`."""
    return f"""(SELECT m.*, wm.reason::text AS reason
               FROM match m
               JOIN workspace_match wm ON wm.match_id = m.id AND wm.workspace_id = %(team)s
               {where})"""


def summary_query(matches: str) -> str:
    """The summaries of the matches `matches` selects (aliased `m`, with a `reason`)."""
    return f"""
SELECT m.id, m.played_at, m.ended_at, m.mode::text, m.status::text, m.map, m.score_a,
       m.score_b, m.rounds_played, m.reason, ours.team::text, tp.players
FROM {matches} m
CROSS JOIN LATERAL ({OUR_TEAM}) ours
CROSS JOIN LATERAL ({TEAM_PLAYERS}) tp
"""


def summary_fields(row: tuple[Any, ...]) -> dict[str, Any]:
    (id_, played_at, ended_at, mode, status_, map_, score_a, score_b, rounds, reason, ours) = row[
        :11
    ]
    return {
        "id": id_,
        "played_at": played_at,
        "ended_at": ended_at,
        "mode": mode,
        "status": status_,
        "map": map_,
        "score_a": score_a,
        "score_b": score_b,
        "rounds_played": rounds,
        "reason": reason,
        "our_team": ours,
        "our_result": result(ours, score_a, score_b) if status_ == "ready" else None,
        "team_players": [TeamPlayerRef(**p) for p in row[11]],
    }


def readable_team(conn: psycopg.Connection[Any], slug: str) -> uuid.UUID:
    """The team, by its slug, when the user is a member (404) who may read its matches (403)."""
    team = team_id(conn, slug)
    row = conn.execute("SELECT has_permission(%s, 'matches.read')", (team,)).fetchone()
    if row is None or not row[0]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden")
    return team


def _list(
    conn: psycopg.Connection[Any], team: uuid.UUID, limit: int, offset: int
) -> list[TeamMatchSummary]:
    # The page is cut first, so that the sides and players are only read for the matches it
    # shows; the order is total (the id breaks ties).
    page = team_matches(f"ORDER BY {ORDER} LIMIT %(limit)s OFFSET %(offset)s")
    rows = conn.execute(
        f"{summary_query(page)} ORDER BY {ORDER}",
        {"team": team, "limit": limit, "offset": offset},
    ).fetchall()
    return [TeamMatchSummary(**summary_fields(row)) for row in rows]


@router.get("/teams/{slug}/matches")
def list_team_matches(
    slug: Slug,
    conn: ConnDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TeamMatchList:
    """The matches the team sees, whatever the reason, most recent first."""
    team = readable_team(conn, slug)
    return TeamMatchList(items=_list(conn, team, limit, offset), limit=limit, offset=offset)


@router.get("/teams/{slug}/overview")
def team_overview(slug: Slug, conn: ConnDep) -> TeamOverview:
    """The team's home: how many matches it sees, the latest ones, and its record over the last
    30 days (parsed matches whose side is known)."""
    team = readable_team(conn, slug)
    params = {"team": team, "days": RECORD_DAYS}
    count = conn.execute(f"SELECT count(*) FROM {team_matches()} m", params).fetchone()
    record = conn.execute(
        f"""
        SELECT count(*) FILTER (WHERE diff > 0), count(*) FILTER (WHERE diff < 0),
               count(*) FILTER (WHERE diff = 0)
        FROM (
            SELECT CASE ours.team WHEN 'A' THEN m.score_a - m.score_b
                                  ELSE m.score_b - m.score_a END AS diff
            FROM {team_matches()} m
            CROSS JOIN LATERAL ({OUR_TEAM}) ours
            WHERE m.status = 'ready' AND ours.team IS NOT NULL
              AND m.score_a IS NOT NULL AND m.score_b IS NOT NULL
              AND m.played_at >= now() - make_interval(days => %(days)s)
        ) results
        """,
        params,
    ).fetchone()
    assert count is not None
    assert record is not None
    return TeamOverview(
        matches=count[0],
        recent=_list(conn, team, RECENT, 0),
        record=TeamRecord(days=RECORD_DAYS, wins=record[0], losses=record[1], ties=record[2]),
    )


@router.get("/teams/{slug}/matches/{match_id}")
def get_team_match(slug: Slug, match_id: uuid.UUID, conn: ConnDep) -> TeamMatchDetail:
    """A match the team sees, from our side, with the ten players' lines. 404 `match_not_found`
    for a match the team does not see, whoever else may."""
    team = readable_team(conn, slug)
    params = {"team": team, "match": match_id}
    summary = conn.execute(summary_query(team_matches("WHERE m.id = %(match)s")), params).fetchone()
    if summary is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "match_not_found")
    extra = conn.execute(
        "SELECT team_a_name, team_b_name, tickrate, unavailable, error FROM match WHERE id = %s",
        (match_id,),
    ).fetchone()
    assert extra is not None
    players = conn.execute(
        f"""
        SELECT mp.steam_id::text, mp.name, mp.team::text, mp.rank, mp.rounds_on_team, {LINE},
               {MEMBER}
        FROM match_player mp
        JOIN match m ON m.id = mp.match_id
        LEFT JOIN LATERAL ({wide_line("mp.match_id", "mp.steam_id")}) w ON true
        WHERE mp.match_id = %(match)s
        ORDER BY mp.team, coalesce(w.untraded, w.level) DESC NULLS LAST, mp.name
        """,
        params,
    ).fetchall()
    return TeamMatchDetail(
        **summary_fields(summary),
        team_a_name=extra[0],
        team_b_name=extra[1],
        tickrate=extra[2],
        unavailable=list(extra[3]),
        error=extra[4],
        rounds=match_rounds(conn, match_id),
        players=[
            TeamMatchPlayer(
                steam_id=p[0],
                name=p[1],
                team=p[2],
                rank=p[3],
                rounds_on_team=p[4],
                line=line(p[5:13]),
                member=p[13],
            )
            for p in players
        ],
    )
