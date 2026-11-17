# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""A team's tactical numbers over its matches: sites, post-plants and retakes, economy, and who
trades whom (`untraded.metrics.team`, docs/metrics-v1.md § 6b).

The worker stores team metrics per side of a match (`team_metric_value`): counts, not rates, so
that a rate over many matches is recomputed over all their rounds. The team's side is "our side"
(`team_matches.OUR_TEAM`), computed when read; a match without it (a shared solo match, a match
inside the team) does not count. Only the current version of each metric is read, with its
default parameters.

Reading takes being a member (404 `team_not_found`) and `matches.read` (403 `forbidden`), as for
the team's matches. The trade network names the team's players only: those who were on its roster
on the match's date or are members now (`team_matches.MEMBER`). Anyone else on our side (a
stand-in who is not registered, an erased player) is neither named nor counted: added up over
matches, even without a name, a regular stand-in's numbers would follow them from match to match,
and a player who is not registered is only ever seen inside a match.
"""

# No `from __future__ import annotations`: FastAPI reads the dependencies from the annotations.

import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Annotated, Any, Literal

import psycopg
from fastapi import APIRouter, Query
from pydantic import BaseModel

from untraded_api.deps import ConnDep
from untraded_api.team_matches import MEMBER, OUR_TEAM, readable_team, team_matches
from untraded_api.teams import Slug

router = APIRouter(tags=["teams"])

MatchType = Literal["all", "scrim", "official"]
BUYS = ("pistol", "eco", "semi", "force", "full")
SITES = ("A", "B")
SITE_ORDER = {"A": 0, "B": 1, "none": 2, "unknown": 3}
DEFAULT_DAYS = 30
MAX_DAYS = 365
MAP = r"^[a-z0-9_]{1,40}$"


class TeamStatsMetric(BaseModel):
    id: str
    version: str


class SiteRow(BaseModel):
    map: str
    site: Literal["A", "B", "none", "unknown"]
    """`none`: T rounds without a plant; `unknown`: a plant on no named site."""
    rounds: int
    won: int


class SituationRow(BaseModel):
    us: int
    """Our players alive at the plant."""
    them: int
    rounds: int
    won: int


class PlantSiteRow(BaseModel):
    site: Literal["A", "B"]
    rounds: int
    won: int


class PlantBlock(BaseModel):
    rounds: int
    """Every round with a plant, those on no named site included."""
    won: int
    by_site: list[PlantSiteRow]
    by_situation: list[SituationRow]
    """By advantage (us - them), largest first, then by our players alive."""


class BuyRow(BaseModel):
    buy: Literal["pistol", "eco", "semi", "force", "full"]
    rounds: int
    won: int


class TradePlayer(BaseModel):
    steam_id: str
    name: str
    """The name in their most recent match of the selection."""
    deaths: int
    traded: int
    """Deaths traded within the window, by anyone (a teammate who is not named included)."""


class TradeLink(BaseModel):
    trader: str
    victim: str
    count: int


class TradeNetwork(BaseModel):
    players: list[TradePlayer]
    """The team's players, most deaths first."""
    links: list[TradeLink]
    """Between named players; a player may trade their own death (their grenade or fire)."""


class TeamStats(BaseModel):
    map: str | None
    days: int
    type: MatchType
    maps: list[str]
    """The maps of the matches of the period and type, for the map filter."""
    matches: int
    rounds: int
    pending: int
    """Matches that would count but whose team metrics are missing or of an older version (until
    `untraded-worker backfill-team-stats`)."""
    trade_window_s: float | None
    metrics: list[TeamStatsMetric]
    sites: list[SiteRow]
    post_plant: PlantBlock
    retakes: PlantBlock
    economy: list[BuyRow]
    trades: TradeNetwork


# The team's matches that can count: parsed, our side known, in the period, of the type.
CHOSEN = f"""
SELECT m.id, m.map, m.played_at, ours.team AS our
FROM {team_matches()} m
CROSS JOIN LATERAL ({OUR_TEAM}) ours
WHERE m.status = 'ready' AND ours.team IS NOT NULL
  AND m.played_at >= now() - make_interval(days => %(days)s)
  AND (%(type)s = 'all' OR (m.mode = 'scrim') = (%(type)s = 'scrim'))
"""

# `fresh`: the match's team metrics are all of their current version. A match parsed before them,
# or holding a version that is no longer current (a new formula, until the backfill), waits.
FILTERED = f"""
SELECT c.*,
       EXISTS (SELECT 1 FROM team_metric_value v
               JOIN metric_current cur ON cur.metric_id = v.metric_id AND cur.version = v.version
               WHERE v.match_id = c.id AND v.metric_id = 'team.buy')
       AND NOT EXISTS (SELECT 1 FROM team_metric_value v
               JOIN metric_current cur ON cur.metric_id = v.metric_id AND cur.version <> v.version
               WHERE v.match_id = c.id) AS fresh
FROM ({CHOSEN}) c
WHERE %(map)s::text IS NULL OR c.map = %(map)s
"""

VALUES = f"""
SELECT c.id, c.map, v.metric_id, v.key, v.sub_key, v.cases, v.hits
FROM ({FILTERED}) c
JOIN team_metric_value v ON v.match_id = c.id AND v.team = c.our
JOIN metric_current cur ON cur.metric_id = v.metric_id AND cur.version = v.version
WHERE c.fresh AND v.params_hash = 'default' AND starts_with(v.metric_id, 'team.')
"""

# Our side's players in each match, and whether the network may name them.
OUR_PLAYERS = f"""
SELECT c.id, mp.steam_id::text, mp.name, {MEMBER}
FROM ({FILTERED}) c
JOIN match m ON m.id = c.id AND c.fresh
JOIN match_player mp ON mp.match_id = c.id AND mp.team = c.our
ORDER BY m.played_at DESC, m.id
"""

METRICS = """
SELECT c.metric_id, c.version, d.params->>'trade.window_s'
FROM metric_current c JOIN metric_definition d USING (metric_id, version)
WHERE d.kind = 'team'
ORDER BY c.metric_id
"""


@dataclass
class Count:
    rounds: int = 0
    won: int = 0

    def add(self, cases: int, hits: int) -> None:
        self.rounds += cases
        self.won += hits


def _situation(sub_key: str) -> tuple[int, int] | None:
    us, sep, them = sub_key.partition("v")
    return (int(us), int(them)) if sep and us.isdigit() and them.isdigit() else None


def _plants(rows: list[tuple[str, str, int, int]]) -> PlantBlock:
    total, sites = Count(), {s: Count() for s in SITES}
    situations: dict[tuple[int, int], Count] = defaultdict(Count)
    for key, sub_key, cases, hits in rows:
        total.add(cases, hits)
        if key in sites:
            sites[key].add(cases, hits)
        situation = _situation(sub_key)
        if situation is not None:
            situations[situation].add(cases, hits)
    order = sorted(situations, key=lambda s: (s[1] - s[0], -s[0]))
    return PlantBlock(
        rounds=total.rounds,
        won=total.won,
        by_site=[
            PlantSiteRow.model_validate({"site": s, "rounds": c.rounds, "won": c.won})
            for s, c in sites.items()
        ],
        by_situation=[
            SituationRow(us=s[0], them=s[1], rounds=situations[s].rounds, won=situations[s].won)
            for s in order
        ],
    )


def _trades(
    rows: list[tuple[uuid.UUID, str, str, int, int]], players: list[tuple[Any, ...]]
) -> TradeNetwork:
    named: dict[tuple[uuid.UUID, str], bool] = {}
    names: dict[str, str] = {}
    for match_id, steam_id, name, member in players:  # most recent match first
        named[(match_id, steam_id)] = bool(member)
        if member:
            names.setdefault(steam_id, name)
    deaths: dict[str, Count] = defaultdict(Count)
    links: dict[tuple[str, str], int] = defaultdict(int)
    for match_id, victim, trader, cases, hits in rows:
        victim_named = named.get((match_id, victim), False)
        if trader == "":
            if victim_named:
                deaths[victim].add(cases, hits)
        elif victim_named and named.get((match_id, trader), False) and hits > 0:
            links[(trader, victim)] += hits
            deaths[trader].add(0, 0)  # a player who only traded is in the network too
    order = sorted(deaths, key=lambda s: (-deaths[s].rounds, names[s].lower(), s))
    return TradeNetwork(
        players=[
            TradePlayer(steam_id=s, name=names[s], deaths=deaths[s].rounds, traded=deaths[s].won)
            for s in order
        ],
        links=[
            TradeLink(trader=t, victim=v, count=n) for (t, v), n in sorted(links.items()) if n > 0
        ],
    )


def team_stats(
    conn: psycopg.Connection[Any], team: uuid.UUID, map_: str | None, days: int, type_: MatchType
) -> TeamStats:
    params = {"team": team, "days": days, "type": type_, "map": map_}
    maps = [
        r[0]
        for r in conn.execute(
            f"SELECT DISTINCT map FROM ({CHOSEN}) c WHERE map IS NOT NULL ORDER BY map", params
        )
    ]
    fresh = [r[0] for r in conn.execute(f"SELECT fresh FROM ({FILTERED}) c", params)]
    values = conn.execute(VALUES, params).fetchall()

    sites: dict[tuple[str, str], Count] = defaultdict(Count)
    plants: dict[str, list[tuple[str, str, int, int]]] = defaultdict(list)
    buys = {b: Count() for b in BUYS}
    trades: list[tuple[uuid.UUID, str, str, int, int]] = []
    rounds = 0
    for match_id, map_name, metric, key, sub_key, cases, hits in values:
        if metric == "team.site_t" and map_name is not None and key in SITE_ORDER:
            sites[(map_name, key)].add(cases, hits)
        elif metric in ("team.post_plant", "team.retake"):
            plants[metric].append((key, sub_key, cases, hits))
        elif metric == "team.buy":
            rounds += cases
            if key in buys:
                buys[key].add(cases, hits)
        elif metric == "team.trades":
            trades.append((match_id, key, sub_key, cases, hits))
    metrics = conn.execute(METRICS).fetchall()
    window = next((float(w) for m, _, w in metrics if m == "team.trades" and w is not None), None)
    players = conn.execute(OUR_PLAYERS, params).fetchall() if trades else []
    return TeamStats(
        map=map_,
        days=days,
        type=type_,
        maps=maps,
        matches=sum(fresh),
        rounds=rounds,
        pending=len(fresh) - sum(fresh),
        trade_window_s=window,
        metrics=[TeamStatsMetric(id=m, version=v) for m, v, _ in metrics],
        sites=[
            SiteRow.model_validate({"map": m, "site": s, "rounds": c.rounds, "won": c.won})
            for (m, s), c in sorted(sites.items(), key=lambda i: (i[0][0], SITE_ORDER[i[0][1]]))
            if c.rounds > 0
        ],
        post_plant=_plants(plants["team.post_plant"]),
        retakes=_plants(plants["team.retake"]),
        economy=[
            BuyRow.model_validate({"buy": b, "rounds": c.rounds, "won": c.won})
            for b, c in buys.items()
        ],
        trades=_trades(trades, players),
    )


@router.get("/teams/{slug}/stats")
def get_team_stats(
    slug: Slug,
    conn: ConnDep,
    map_: Annotated[str | None, Query(alias="map", pattern=MAP)] = None,
    days: Annotated[int, Query(ge=1, le=MAX_DAYS)] = DEFAULT_DAYS,
    type_: Annotated[MatchType, Query(alias="type")] = "all",
) -> TeamStats:
    """The team's tactical numbers over its matches of the last `days` days, of one map or all,
    of one type (`scrim`, `official`: any other mode) or all."""
    team = readable_team(conn, slug)
    return team_stats(conn, team, map_, days, type_)
