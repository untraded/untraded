# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The matches the signed-in user may see, and their details.

Queries run as the user (row-level security): a match the user may not see does not exist for
them (404), and its players are not visible either. Metric values are those of the current
version of each metric (`metric_current`), with the default parameters.
"""

# No `from __future__ import annotations`: FastAPI reads the dependencies from the annotations.

import datetime as dt
import uuid
from pathlib import Path as FilePath
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Query, Response, status
from pydantic import BaseModel

from untraded_api.deps import ConnDep, SettingsDep, UserDep

router = APIRouter(prefix="/matches", tags=["matches"])

SteamId = Annotated[str, Path(pattern=r"^\d{1,20}$")]


class PlayerLine(BaseModel):
    """A player's headline numbers in one match (scope `match`)."""

    kills: float | None
    deaths: float | None
    adr: float | None
    kast: float | None
    hltv1: float | None
    untraded_deaths: float | None


class MatchSummary(BaseModel):
    id: uuid.UUID
    played_at: dt.datetime | None
    ended_at: dt.datetime | None
    mode: str
    status: str
    """`downloading`, `parsing`, `ready`, `failed` or `unavailable`."""
    map: str | None
    score_a: int | None
    score_b: int | None
    rounds_played: int | None
    my_team: str | None
    """`A` (started on CT) or `B`, when the user played the match."""
    my_result: str | None
    """`win`, `loss` or `tie`, when the user played and the match is parsed."""
    my_line: PlayerLine | None


class MatchList(BaseModel):
    items: list[MatchSummary]
    limit: int
    offset: int


class Round(BaseModel):
    round: int
    winner_side: str | None
    winner_team: str | None
    reason: str
    ct_team: str
    score_a: int
    score_b: int
    is_overtime: bool
    bomb_site: str | None
    bomb_planted: bool


class Player(BaseModel):
    steam_id: str
    name: str
    team: str
    rank: int | None
    rounds_on_team: int
    line: PlayerLine


class MatchDetail(MatchSummary):
    team_a_name: str | None
    team_b_name: str | None
    tickrate: float | None
    unavailable: list[str]
    """Data the demo did not have (see the canonical tables' notes)."""
    error: str | None
    rounds: list[Round]
    players: list[Player]


class MetricValue(BaseModel):
    metric_id: str
    version: str
    name: str
    unit: str
    better: str
    """`higher`, `lower` or `neutral`: which way is an improvement."""
    scope: str
    """`match`, or the rounds played on one side: `ct`, `t`."""
    value: float | None


class PlayerMetrics(BaseModel):
    match_id: uuid.UUID
    steam_id: str
    metrics: list[MetricValue]


LINE = "w.kills, w.deaths, w.adr, w.kast, w.hltv1, w.untraded_deaths"

SUMMARY = f"""
SELECT m.id, m.played_at, m.ended_at, m.mode::text, m.status::text, m.map, m.score_a,
       m.score_b, m.rounds_played, mp.team, w.match_id IS NOT NULL, {LINE}
FROM match m
LEFT JOIN match_player mp
       ON mp.match_id = m.id
      AND mp.steam_id = (SELECT steam_id FROM app_user WHERE id = %(user)s)
LEFT JOIN metric_wide_current w
       ON w.match_id = m.id AND w.steam_id = mp.steam_id AND w.scope = 'match'
"""


def _line(values: tuple[Any, ...]) -> PlayerLine:
    kills, deaths, adr, kast, hltv1, untraded = values
    return PlayerLine(
        kills=kills, deaths=deaths, adr=adr, kast=kast, hltv1=hltv1, untraded_deaths=untraded
    )


def _result(team: str | None, score_a: int | None, score_b: int | None) -> str | None:
    if team is None or score_a is None or score_b is None:
        return None
    mine, theirs = (score_a, score_b) if team == "A" else (score_b, score_a)
    return "win" if mine > theirs else "loss" if mine < theirs else "tie"


def summary_fields(row: tuple[Any, ...]) -> dict[str, Any]:
    (id_, played_at, ended_at, mode, status_, map_, score_a, score_b, rounds, team, has_line) = row[
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
        "my_team": team,
        "my_result": _result(team, score_a, score_b) if status_ == "ready" else None,
        "my_line": _line(row[11:17]) if has_line else None,
    }


@router.get("")
def list_matches(
    conn: ConnDep,
    user: UserDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MatchList:
    """The matches the user may see, most recent first."""
    rows = conn.execute(
        f"{SUMMARY} ORDER BY m.played_at DESC NULLS LAST, m.created_at DESC, m.id "
        "LIMIT %(limit)s OFFSET %(offset)s",
        {"user": user, "limit": limit, "offset": offset},
    ).fetchall()
    return MatchList(
        items=[MatchSummary(**summary_fields(row)) for row in rows], limit=limit, offset=offset
    )


@router.get("/{match_id}")
def get_match(match_id: uuid.UUID, conn: ConnDep, user: UserDep) -> MatchDetail:
    row = conn.execute(f"{SUMMARY} WHERE m.id = %(match)s", {"user": user, "match": match_id})
    summary = row.fetchone()
    if summary is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such match")
    extra = conn.execute(
        "SELECT team_a_name, team_b_name, tickrate, unavailable, error FROM match WHERE id = %s",
        (match_id,),
    ).fetchone()
    assert extra is not None
    rounds = conn.execute(
        """
        SELECT round, winner_side, winner_team::text, reason, ct_team::text, score_a, score_b,
               is_overtime, bomb_site::text, bomb_planted_tick IS NOT NULL
        FROM round WHERE match_id = %s ORDER BY round
        """,
        (match_id,),
    ).fetchall()
    players = conn.execute(
        f"""
        SELECT mp.steam_id::text, mp.name, mp.team::text, mp.rank, mp.rounds_on_team, {LINE}
        FROM match_player mp
        LEFT JOIN metric_wide_current w
               ON w.match_id = mp.match_id AND w.steam_id = mp.steam_id AND w.scope = 'match'
        WHERE mp.match_id = %s
        ORDER BY mp.team, w.hltv1 DESC NULLS LAST, mp.name
        """,
        (match_id,),
    ).fetchall()
    return MatchDetail(
        **summary_fields(summary),
        team_a_name=extra[0],
        team_b_name=extra[1],
        tickrate=extra[2],
        unavailable=list(extra[3]),
        error=extra[4],
        rounds=[
            Round(
                round=r[0],
                winner_side=r[1],
                winner_team=r[2],
                reason=r[3],
                ct_team=r[4],
                score_a=r[5],
                score_b=r[6],
                is_overtime=r[7],
                bomb_site=r[8],
                bomb_planted=r[9],
            )
            for r in rounds
        ],
        players=[
            Player(
                steam_id=p[0],
                name=p[1],
                team=p[2],
                rank=p[3],
                rounds_on_team=p[4],
                line=_line(p[5:11]),
            )
            for p in players
        ],
    )


@router.get(
    "/{match_id}/rounds/{round_number}/replay",
    response_class=Response,
    responses={200: {"content": {"application/json": {}}}},
)
def get_replay(
    match_id: uuid.UUID,
    round_number: Annotated[int, Path(ge=0, le=200)],
    conn: ConnDep,
    settings: SettingsDep,
) -> Response:
    """A round as the 2D viewer replays it (`untraded.replay`, format `version`), gzipped.
    404 when the match is not one the user may see, or has no replay for that round."""
    row = conn.execute("SELECT parquet_prefix FROM match WHERE id = %s", (match_id,)).fetchone()
    if row is None or row[0] is None or settings.store_dir is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such replay")
    path = FilePath(settings.store_dir, *row[0].split("/"), "replay", f"{round_number}.json.gz")
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such replay")
    return Response(
        content=path.read_bytes(),
        media_type="application/json",
        # A replay never changes once written (a new format is a new version, rewritten).
        headers={"Content-Encoding": "gzip", "Cache-Control": "private, max-age=86400"},
    )


@router.get("/{match_id}/players/{steam_id}")
def get_player_metrics(match_id: uuid.UUID, steam_id: SteamId, conn: ConnDep) -> PlayerMetrics:
    """Every value metric of one player in one match, on each scope."""
    played = conn.execute(
        "SELECT 1 FROM match_player WHERE match_id = %s AND steam_id = %s",
        (match_id, int(steam_id)),
    ).fetchone()
    if played is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such player in a visible match")
    rows = conn.execute(
        """
        SELECT v.metric_id, v.version, d.name, d.unit, d.better, v.scope::text, v.value
        FROM metric_value v
        JOIN metric_current c USING (metric_id, version)
        JOIN metric_definition d USING (metric_id, version)
        WHERE v.match_id = %s AND v.steam_id = %s AND v.params_hash = 'default'
        ORDER BY v.metric_id, v.scope
        """,
        (match_id, int(steam_id)),
    ).fetchall()
    return PlayerMetrics(
        match_id=match_id,
        steam_id=steam_id,
        metrics=[
            MetricValue(
                metric_id=r[0],
                version=r[1],
                name=r[2],
                unit=r[3],
                better=r[4],
                scope=r[5],
                value=r[6],
            )
            for r in rows
        ],
    )
