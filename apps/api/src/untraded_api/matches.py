# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The matches the signed-in user may see, and their details.

Queries run as the user (row-level security): a match the user may not see does not exist for
them (404), and its players are not visible either. Metric values are those of the current
version of each metric (`metric_current`), with the default parameters.
"""

# No `from __future__ import annotations`: FastAPI reads the dependencies from the annotations.

import datetime as dt
import gzip
import hashlib
import io
import re
import uuid
from pathlib import Path as FilePath
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, Path, Query, Response, status
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
    untraded: float | None
    """The Untraded Rating (beta); null for a match analysed before it existed."""
    level: float | None = None
    """The Untraded Rating level (what the player is worth, on the same scale); HLTV 1.0
    (`hltv1`) is kept for the API's readers but no longer shown on the site."""


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


LINE = "w.kills, w.deaths, w.adr, w.kast, w.hltv1, w.untraded_deaths, w.untraded, w.level"


def _wide_line(match: str, steam_id: str) -> str:
    """The headline numbers of one player in one match, as `metric_wide_current` has them
    (scope `match`, current versions, default parameters), to `LEFT JOIN LATERAL ... ON true`.

    The view is not joined: it groups the whole `metric_value` table, and a join on an
    aggregating view is not pushed down before the grouping, so every read aggregated every
    value of the database. Here the grouping only reads the player's rows, through the primary
    key (match_id, steam_id, scope, ...), under the same row-level security as the view (which
    runs with the reader's rights, 0002). An aggregate without GROUP BY always gives one row:
    `found` tells a player with values from one without, as the view's missing row did."""
    return f"""
    SELECT count(*) > 0 AS found,
           max(v.value) FILTER (WHERE v.metric_id = 'base.kills')  AS kills,
           max(v.value) FILTER (WHERE v.metric_id = 'base.deaths') AS deaths,
           max(v.value) FILTER (WHERE v.metric_id = 'base.adr')    AS adr,
           max(v.value) FILTER (WHERE v.metric_id = 'base.kast')   AS kast,
           max(v.value) FILTER (WHERE v.metric_id = 'rating.hltv1') AS hltv1,
           max(v.value) FILTER (WHERE v.metric_id = 'trade.untraded_deaths') AS untraded_deaths,
           max(v.value) FILTER (WHERE v.metric_id = 'rating.untraded') AS untraded,
           max(v.value) FILTER (WHERE v.metric_id = 'rating.untraded_level') AS level
    FROM metric_value v
    JOIN metric_current c USING (metric_id, version)
    WHERE v.match_id = {match} AND v.steam_id = {steam_id}
      AND v.scope = 'match' AND v.params_hash = 'default'
    """


def summary_query(matches: str) -> str:
    """The summary of the matches `matches` selects (a table or a subquery, aliased `m`), with
    the user's team and line."""
    return f"""
SELECT m.id, m.played_at, m.ended_at, m.mode::text, m.status::text, m.map, m.score_a,
       m.score_b, m.rounds_played, mp.team, w.found, {LINE}
FROM {matches} m
LEFT JOIN match_player mp
       ON mp.match_id = m.id
      AND mp.steam_id = (SELECT steam_id FROM app_user WHERE id = %(user)s)
LEFT JOIN LATERAL ({_wide_line("m.id", "mp.steam_id")}) w ON true
"""


# Every match, to filter with WHERE (a match page); the list and the sessions cut their
# matches first (`summary_query` over a subquery).
SUMMARY = summary_query("match")


def _line(values: tuple[Any, ...]) -> PlayerLine:
    kills, deaths, adr, kast, hltv1, untraded_deaths, untraded, level = values
    return PlayerLine(
        kills=kills,
        deaths=deaths,
        adr=adr,
        kast=kast,
        hltv1=hltv1,
        untraded_deaths=untraded_deaths,
        untraded=untraded,
        level=level,
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
        "my_line": _line(row[11:19]) if has_line else None,
    }


@router.get("")
def list_matches(
    conn: ConnDep,
    user: UserDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MatchList:
    """The matches the user may see, most recent first."""
    # The page is cut first, so that the lines are only read for the matches it shows.
    # The order is total (the id breaks ties), so the page is the same as when it was cut
    # after the joins.
    page = """(SELECT * FROM match ORDER BY played_at DESC NULLS LAST, created_at DESC, id
               LIMIT %(limit)s OFFSET %(offset)s)"""
    rows = conn.execute(
        f"{summary_query(page)} ORDER BY m.played_at DESC NULLS LAST, m.created_at DESC, m.id",
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
        LEFT JOIN LATERAL ({_wide_line("mp.match_id", "mp.steam_id")}) w ON true
        WHERE mp.match_id = %s
        ORDER BY mp.team, coalesce(w.untraded, w.level) DESC NULLS LAST, mp.name
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
                line=_line(p[5:13]),
            )
            for p in players
        ],
    )


def _replay_version(gzipped: bytes) -> int | None:
    """The format version of a stored replay: its first key (`untraded.replay.to_json_gz`)."""
    with gzip.GzipFile(fileobj=io.BytesIO(gzipped)) as file:
        head = file.read(32)
    found = re.match(rb'\{"version":(\d+)', head)
    return int(found[1]) if found else None


def replay_etag(content: bytes) -> str:
    """A strong validator of a stored replay: a hash of its bytes. The file is read whole anyway
    (about 40 kB gzipped) to check its version, so hashing it costs little more, and unlike mtime
    and size it changes exactly when the content does: a reanalysis that rewrites the same replay
    keeps the browser's copy, and one that changes it is never mistaken for the old one."""
    return '"' + hashlib.blake2b(content, digest_size=16).hexdigest() + '"'


def none_match(if_none_match: str | None, etag: str) -> bool:
    """Whether `If-None-Match` names `etag` (or is `*`): the weak comparison RFC 9110 asks for, so
    a proxy that weakened the tag (`W/`, the web's relay) still revalidates."""
    if if_none_match is None:
        return False
    tags = [tag.strip() for tag in if_none_match.split(",")]
    return "*" in tags or etag in (tag.removeprefix("W/") for tag in tags)


@router.get(
    "/{match_id}/rounds/{round_number}/replay",
    response_class=Response,
    responses={200: {"content": {"application/json": {}}}, 304: {}},
)
def get_replay(
    match_id: uuid.UUID,
    round_number: Annotated[int, Path(ge=0, le=200)],
    conn: ConnDep,
    settings: SettingsDep,
    v: Annotated[int | None, Query(ge=1)] = None,
    if_none_match: Annotated[str | None, Header()] = None,
) -> Response:
    """A round as the 2D viewer replays it (`untraded.replay`, format `version`), gzipped.
    404 when the match is not one the user may see, or has no replay for that round.

    `v` is the format version the viewer reads, and so part of the address the browser caches
    the replay under: a replay written in another version is a 404 that is not kept, so that a
    viewer newer than the replays never caches an old one under its own version.

    The answer carries an `ETag`, and a matching `If-None-Match` is a 304 without a body. It is
    kept a week but revalidated after (not `immutable`: a reanalysis rewrites the file). The 304
    comes only after the match is found as the user (row-level security): someone who may not
    see the match gets the same 404 with or without the header, never a hint that it exists."""
    row = conn.execute("SELECT parquet_prefix FROM match WHERE id = %s", (match_id,)).fetchone()
    if row is None or row[0] is None or settings.store_dir is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such replay")
    path = FilePath(settings.store_dir, *row[0].split("/"), "replay", f"{round_number}.json.gz")
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such replay")
    content = path.read_bytes()
    if v is not None and _replay_version(content) != v:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "no replay in this version",
            headers={"Cache-Control": "no-store"},
        )
    etag = replay_etag(content)
    headers = {
        "ETag": etag,
        "Cache-Control": "private, max-age=604800",
        # Per account: a browser shared by two players asks again rather than serve one's copy
        # to the other (sign-out also clears the cache, `CLEAR_CACHE`).
        "Vary": "Cookie",
    }
    if none_match(if_none_match, etag):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Encoding": "gzip", **headers},
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


class RatingPart(BaseModel):
    part: str
    """`shooting`, `utility`, `trade`, `objective`, `taken`, `team`, `balance` (the round
    recentring) or `baseline` (1.00): the parts add up to the rating."""
    points: float


class RatingDetail(BaseModel):
    """The Untraded Rating of one player in one match (scope `match`), and where it comes from."""

    value: float | None
    """The match rating: what the player's actions were worth."""
    margin: float | None
    """Half-width of its 95 % interval."""
    rounds: int | None
    parts: list[RatingPart]
    level: float | None = None
    """The level: what the player is worth, on the same scale (closer to 1.00)."""


@router.get("/{match_id}/players/{steam_id}/rating")
def get_player_rating(match_id: uuid.UUID, steam_id: SteamId, conn: ConnDep) -> RatingDetail:
    """The Untraded Rating of a player in a match, its margin and its parts by action. Its
    values are null for a match analysed before the rating existed."""
    played = conn.execute(
        "SELECT rounds_on_team FROM match_player WHERE match_id = %s AND steam_id = %s",
        (match_id, int(steam_id)),
    ).fetchone()
    if played is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such player in a visible match")
    values = dict(
        conn.execute(
            """
            SELECT v.metric_id, v.value
            FROM metric_value v JOIN metric_current c USING (metric_id, version)
            WHERE v.match_id = %s AND v.steam_id = %s AND v.params_hash = 'default'
              AND v.scope = 'match'
              AND v.metric_id IN ('rating.untraded', 'rating.untraded_level')
            """,
            (match_id, int(steam_id)),
        ).fetchall()
    )
    tables = dict(
        conn.execute(
            """
            SELECT t.metric_id, t.rows
            FROM metric_table_value t JOIN metric_current c USING (metric_id, version)
            WHERE t.match_id = %s AND t.steam_id = %s AND t.params_hash = 'default'
              AND t.metric_id IN ('rating.untraded_parts', 'rating.untraded_margin')
            """,
            (match_id, int(steam_id)),
        ).fetchall()
    )
    margin_rows: list[dict[str, Any]] = tables.get("rating.untraded_margin") or []
    margin = margin_rows[0] if margin_rows else {}
    parts: list[dict[str, Any]] = tables.get("rating.untraded_parts") or []
    return RatingDetail(
        value=values.get("rating.untraded"),
        margin=_number(margin.get("margin")),
        rounds=margin.get("rounds") if isinstance(margin.get("rounds"), int) else played[0],
        parts=[
            RatingPart(part=str(r["part"]), points=points)
            for r in parts
            if isinstance(r, dict)
            and "part" in r
            and (points := _number(r.get("points"))) is not None
        ],
        level=_number(values.get("rating.untraded_level")),
    )


def _number(value: Any) -> float | None:
    """A stored number, or None for a null (the worker stores NaN and infinity as null)."""
    return float(value) if isinstance(value, int | float) else None
