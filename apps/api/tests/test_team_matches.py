# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""A team's matches against PostgreSQL (UNTRADED_TEST_DATABASE_URL; skipped otherwise), read
through the API as the API role (row-level security, no BYPASSRLS). The team's access is the
worker's own (`refresh_access`), on matches served by Valve, which count for all their players."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

import psycopg
import pytest
import test_team_routes as base
from test_team_routes import MEMBER, NEWCOMER, OTHER, OWNER, URL, People, join, make_team

from untraded_worker.load import refresh_access

# The teams' fixtures: a clean database, the API, and signed-in people.
client, db, people = base.client, base.db, base.people

pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(not URL, reason="UNTRADED_TEST_DATABASE_URL is not set"),
]
VIEWER = 76561198000000110
"""A member of the team who is not on its roster."""
STRANGERS = [76561198000000200 + n for n in range(10)]
"""Players who are not users."""


def add_match(
    db: psycopg.Connection[Any],
    sides: dict[str, list[int]],
    *,
    days_ago: int,
    score: tuple[int, int],
) -> str:
    """A parsed Valve match played `days_ago` days ago, its sides filled up with strangers, and the
    workspaces that see it as the worker computes them."""
    played_at = dt.datetime.now(dt.UTC) - dt.timedelta(days=days_ago)
    row = db.execute(
        "INSERT INTO match (mode, status, played_at, map, score_a, score_b, rounds_played) "
        "VALUES ('premier', 'ready', %s, 'de_nuke', %s, %s, %s) RETURNING id",
        (played_at, score[0], score[1], score[0] + score[1]),
    ).fetchone()
    assert row is not None
    match_id = uuid.UUID(str(row[0]))
    db.execute(
        "INSERT INTO match_source (match_id, kind, external_id) VALUES (%s, 'valve_bot', %s)",
        (match_id, str(match_id)),
    )
    strangers = iter(STRANGERS)
    for team, steam_ids in sides.items():
        full = steam_ids + [next(strangers) for _ in range(5 - len(steam_ids))]
        for steam_id in full:
            db.execute(
                "INSERT INTO player (steam_id, last_name) VALUES (%s, 'p') ON CONFLICT DO NOTHING",
                (steam_id,),
            )
            db.execute(
                "INSERT INTO match_player (match_id, steam_id, team, name, rounds_on_team) "
                "VALUES (%s, %s, %s, %s, %s)",
                (match_id, steam_id, team, f"n{steam_id % 1000}", score[0] + score[1]),
            )
    refresh_access(db, match_id)
    return str(match_id)


def roster_since(db: psycopg.Connection[Any], steam_id: int, days_ago: int) -> None:
    db.execute(
        "UPDATE roster_member SET valid_from = current_date - %s WHERE steam_id = %s",
        (days_ago, steam_id),
    )


def setup_team(people: People) -> dict[str, Any]:
    """`team-one`: OWNER, MEMBER and NEWCOMER on its roster for a year, VIEWER a member who is
    not on it and shares their solo matches; OTHER is not a member."""
    people.add(NEWCOMER)
    people.add(VIEWER)
    team = make_team(people)
    join(people, MEMBER, team, "player")
    join(people, NEWCOMER, team, "player")
    join(people, VIEWER, team, "viewer")
    for steam_id in (OWNER, MEMBER, NEWCOMER):
        put = people.call(
            OWNER, "PUT", f"/teams/team-one/roster/{steam_id}", json={"role": "starter"}
        )
        assert put.status_code == 200, put.text
        roster_since(people.db, steam_id, 365)
    shared = people.call(VIEWER, "PUT", "/teams/team-one/share-solo", json={"share": True})
    assert shared.status_code == 204
    return team


def ids(body: dict[str, Any]) -> list[str]:
    return [m["id"] for m in body["items"]]


def test_the_team_lists_its_matches_from_our_side(people: People) -> None:
    setup_team(people)
    db = people.db
    together = add_match(db, {"A": [], "B": [OWNER, MEMBER, NEWCOMER]}, days_ago=1, score=(7, 13))
    shared = add_match(db, {"A": [VIEWER], "B": []}, days_ago=2, score=(13, 5))
    met = add_match(db, {"A": [OWNER, MEMBER], "B": [NEWCOMER]}, days_ago=3, score=(13, 11))
    elsewhere = add_match(db, {"A": [OTHER], "B": []}, days_ago=4, score=(13, 2))

    body = people.call(VIEWER, "GET", "/teams/team-one/matches").json()
    assert ids(body) == [together, shared]  # 2 on one side and 1 on the other is not a team match
    first, second = body["items"]
    assert (first["reason"], first["our_team"], first["our_result"]) == ("roster", "B", "win")
    assert [(p["steam_id"], p["team"]) for p in first["team_players"]] == sorted(
        [(str(s), "B") for s in (OWNER, MEMBER, NEWCOMER)],
        key=lambda p: f"n{int(p[0]) % 1000}",
    )
    assert (second["reason"], second["our_team"], second["our_result"]) == ("shared", None, None)
    assert [p["steam_id"] for p in second["team_players"]] == [str(VIEWER)]
    paged = people.call(VIEWER, "GET", "/teams/team-one/matches?limit=1&offset=1").json()
    assert ids(paged) == [shared]

    # Each member's own list is still their personal space's.
    assert ids(people.call(OWNER, "GET", "/matches").json()) == [together, met]
    assert ids(people.call(VIEWER, "GET", "/matches").json()) == [shared]
    assert ids(people.call(OTHER, "GET", "/matches").json()) == [elsewhere]


def test_our_side_is_the_rosters_on_the_matchs_date(people: People) -> None:
    team = setup_team(people)
    db = people.db
    # MEMBER left the team 100 days ago; VIEWER joined the roster 50 days ago.
    left = people.call(MEMBER, "DELETE", f"/teams/team-one/members/{people.user_id(MEMBER)}")
    assert left.status_code == 204
    db.execute(
        "UPDATE roster_member SET valid_to = current_date - 100 WHERE steam_id = %s", (MEMBER,)
    )
    people.call(OWNER, "PUT", f"/teams/team-one/roster/{VIEWER}", json={"role": "standin"})
    roster_since(db, VIEWER, 50)

    before = add_match(db, {"A": [OWNER, MEMBER, NEWCOMER], "B": []}, days_ago=200, score=(13, 9))
    after = add_match(db, {"A": [OWNER, MEMBER, NEWCOMER], "B": []}, days_ago=20, score=(13, 9))
    now = add_match(db, {"A": [], "B": [OWNER, NEWCOMER, VIEWER]}, days_ago=10, score=(13, 9))
    # After MEMBER left, two of the roster are not a team match: the team sees it only because
    # it was shared (the worker's other reason), and has no side in it.
    assert ids(people.call(OWNER, "GET", "/teams/team-one/matches").json()) == [now, before]
    db.execute(
        "INSERT INTO workspace_match (workspace_id, match_id, reason) VALUES (%s, %s, 'shared')",
        (team["id"], after),
    )

    items = {
        m["id"]: m for m in people.call(OWNER, "GET", "/teams/team-one/matches").json()["items"]
    }
    assert items[before]["our_team"] == "A"  # MEMBER still counts for a match played before
    assert items[before]["our_result"] == "win"
    assert {p["steam_id"] for p in items[before]["team_players"]} == {
        str(OWNER),
        str(MEMBER),
        str(NEWCOMER),
    }
    assert items[after]["our_team"] is None
    assert {p["steam_id"] for p in items[after]["team_players"]} == {str(OWNER), str(NEWCOMER)}
    assert items[now]["our_team"] == "B"
    assert items[now]["our_result"] == "loss"


def test_the_team_match_page_reads_from_our_side(people: People) -> None:
    setup_team(people)
    together = add_match(
        people.db, {"A": [], "B": [OWNER, MEMBER, NEWCOMER]}, days_ago=1, score=(7, 13)
    )
    response = people.call(VIEWER, "GET", f"/teams/team-one/matches/{together}")
    assert response.status_code == 200, response.text
    detail = response.json()
    assert (detail["our_team"], detail["our_result"], detail["reason"]) == ("B", "win", "roster")
    assert "my_team" not in detail
    assert len(detail["players"]) == 10
    assert {p["steam_id"] for p in detail["players"] if p["member"]} == {
        str(OWNER),
        str(MEMBER),
        str(NEWCOMER),
    }
    assert detail["rounds"] == []
    assert (detail["map"], detail["score_a"], detail["score_b"]) == ("de_nuke", 7, 13)


def test_the_overview_counts_the_last_30_days_from_our_side(people: People) -> None:
    setup_team(people)
    db = people.db
    roster = [OWNER, MEMBER, NEWCOMER]
    won = add_match(db, {"A": roster, "B": []}, days_ago=1, score=(13, 4))
    lost = add_match(db, {"A": [], "B": roster}, days_ago=5, score=(13, 4))
    tied = add_match(db, {"A": roster, "B": []}, days_ago=6, score=(15, 15))
    shared = add_match(db, {"A": [VIEWER], "B": []}, days_ago=7, score=(13, 0))  # no side
    old = add_match(db, {"A": roster, "B": []}, days_ago=60, score=(13, 0))
    for n in range(2):
        add_match(db, {"A": roster, "B": []}, days_ago=70 + n, score=(13, 0))

    overview = people.call(MEMBER, "GET", "/teams/team-one/overview").json()
    assert overview["matches"] == 7
    assert [m["id"] for m in overview["recent"]] == [won, lost, tied, shared, old]
    assert overview["record"] == {"days": 30, "wins": 1, "losses": 1, "ties": 1}


def test_only_members_who_may_read_matches_see_the_teams_matches(people: People) -> None:
    team = setup_team(people)
    together = add_match(
        people.db, {"A": [OWNER, MEMBER, NEWCOMER], "B": []}, days_ago=1, score=(13, 4)
    )
    mine_only = add_match(people.db, {"A": [OWNER], "B": []}, days_ago=2, score=(13, 4))
    paths = [
        "/teams/team-one/matches",
        "/teams/team-one/overview",
        f"/teams/team-one/matches/{together}",
    ]
    for path in paths:
        refused = people.call(OTHER, "GET", path)
        assert (refused.status_code, refused.json()["detail"]) == (404, "team_not_found")
    unknown = people.call(OWNER, "GET", "/teams/nobody/matches")
    assert (unknown.status_code, unknown.json()["detail"]) == (404, "team_not_found")

    # A match the team does not see is not found in its space, even for a user who sees it.
    assert people.call(OWNER, "GET", f"/matches/{mine_only}").status_code == 200
    missing = people.call(OWNER, "GET", f"/teams/team-one/matches/{mine_only}")
    assert (missing.status_code, missing.json()["detail"]) == (404, "match_not_found")
    gone = people.call(OWNER, "GET", f"/teams/team-one/matches/{uuid.uuid4()}")
    assert (gone.status_code, gone.json()["detail"]) == (404, "match_not_found")

    # A role without `matches.read` (a team's own role, as configurable roles will allow).
    people.db.execute(
        "WITH r AS (INSERT INTO workspace_role (workspace_id, name, permissions) "
        "VALUES (%s, 'commenter', '{review.comment}') RETURNING id) "
        "UPDATE membership SET role_id = (SELECT id FROM r) "
        "WHERE workspace_id = %s AND user_id = %s",
        (team["id"], team["id"], people.user_id(VIEWER)),
    )
    for path in paths:
        forbidden = people.call(VIEWER, "GET", path)
        assert (forbidden.status_code, forbidden.json()["detail"]) == (403, "forbidden")
