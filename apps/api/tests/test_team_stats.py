# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""A team's tactical numbers against PostgreSQL (UNTRADED_TEST_DATABASE_URL; skipped otherwise),
read through the API as the API role (row-level security, no BYPASSRLS). The matches and the
team's access are those of the team's matches tests; the team metrics are written as the worker
writes them, per side of a match."""

from __future__ import annotations

import json
from typing import Any

import psycopg
import pytest
import test_team_matches as matches
from test_team_matches import STRANGERS, VIEWER, add_match, setup_team
from test_team_routes import MEMBER, NEWCOMER, OTHER, OWNER, URL, People

# The teams' fixtures: a clean database, the API, and signed-in people.
client, db, people = matches.client, matches.db, matches.people

pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(not URL, reason="UNTRADED_TEST_DATABASE_URL is not set"),
]
ROSTER = [OWNER, MEMBER, NEWCOMER]
METRICS = ("team.buy", "team.post_plant", "team.retake", "team.site_t", "team.trades")


def register(db: psycopg.Connection[Any]) -> None:
    for metric in METRICS:
        params = {"trade.window_s": 5.0} if metric == "team.trades" else {}
        db.execute(
            "INSERT INTO metric_definition (metric_id, version, name, unit, kind, params, doc) "
            "VALUES (%s, '1.0.0', %s, 'table', 'team', %s, '') ON CONFLICT DO NOTHING",
            (metric, metric, json.dumps(params)),
        )
        db.execute(
            "INSERT INTO metric_current (metric_id, version) VALUES (%s, '1.0.0') "
            "ON CONFLICT DO NOTHING",
            (metric,),
        )


def put(
    db: psycopg.Connection[Any],
    match: str,
    team: str,
    rows: list[tuple[str, str | int, str | int, int, int]],
) -> None:
    """Team rows of one side: (metric, key, sub_key, cases, hits)."""
    for metric, key, sub_key, cases, hits in rows:
        db.execute(
            "INSERT INTO team_metric_value (match_id, team, metric_id, version, params_hash, key, "
            "sub_key, cases, hits) VALUES (%s, %s, %s, '1.0.0', 'default', %s, %s, %s, %s)",
            (match, team, metric, str(key), str(sub_key), cases, hits),
        )


def name(steam_id: int) -> str:
    return f"n{steam_id % 1000}"


def stats(people: People, query: str = "", who: int = MEMBER) -> dict[str, Any]:
    response = people.call(who, "GET", f"/teams/team-one/stats{query}")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def two_matches(people: People) -> tuple[str, str]:
    """A Nuke match where we are B, and a Mirage match where we are A."""
    setup_team(people)
    db = people.db
    register(db)
    nuke = add_match(db, {"A": [], "B": ROSTER}, days_ago=1, score=(7, 13))
    stand_in = STRANGERS[5]  # our fifth player on Nuke, not registered
    put(db, nuke, "B", [
        ("team.site_t", "A", "", 4, 3),
        ("team.site_t", "none", "", 6, 2),
        ("team.post_plant", "A", "3v2", 2, 2),
        ("team.post_plant", "A", "2v3", 2, 0),
        ("team.retake", "B", "1v2", 3, 1),
        ("team.buy", "pistol", "pistol", 2, 1),
        ("team.buy", "full", "eco", 8, 4),
        ("team.trades", OWNER, "", 3, 2),
        ("team.trades", OWNER, MEMBER, 3, 1),
        ("team.trades", OWNER, stand_in, 3, 1),
        ("team.trades", MEMBER, "", 2, 0),
        ("team.trades", stand_in, "", 4, 1),
        ("team.trades", stand_in, OWNER, 4, 1),
    ])  # fmt: skip
    # The other side's rows are the opponents': never ours.
    put(db, nuke, "A", [("team.site_t", "A", "", 5, 5), ("team.buy", "full", "", 10, 10)])
    mirage = add_match(db, {"A": ROSTER, "B": []}, days_ago=3, score=(13, 4))
    db.execute("UPDATE match SET map = 'de_mirage' WHERE id = %s", (mirage,))
    put(db, mirage, "A", [
        ("team.site_t", "B", "", 3, 1),
        ("team.post_plant", "B", "3v2", 1, 1),
        ("team.buy", "eco", "full", 3, 1),
        ("team.trades", OWNER, "", 1, 1),
        ("team.trades", OWNER, NEWCOMER, 1, 1),
    ])  # fmt: skip
    return nuke, mirage


def test_the_team_reads_its_side_of_its_matches_added_up(people: People) -> None:
    two_matches(people)
    body = stats(people)
    assert (body["map"], body["days"], body["type"]) == (None, 30, "all")
    assert body["maps"] == ["de_mirage", "de_nuke"]
    assert (body["matches"], body["rounds"], body["pending"]) == (2, 13, 0)
    assert body["trade_window_s"] == 5.0
    assert [m["id"] for m in body["metrics"]] == sorted(METRICS)
    assert body["sites"] == [
        {"map": "de_mirage", "site": "B", "rounds": 3, "won": 1},
        {"map": "de_nuke", "site": "A", "rounds": 4, "won": 3},
        {"map": "de_nuke", "site": "none", "rounds": 6, "won": 2},
    ]
    assert body["post_plant"] == {
        "rounds": 5,
        "won": 3,
        "by_site": [{"site": "A", "rounds": 4, "won": 2}, {"site": "B", "rounds": 1, "won": 1}],
        "by_situation": [
            {"us": 3, "them": 2, "rounds": 3, "won": 3},
            {"us": 2, "them": 3, "rounds": 2, "won": 0},
        ],
    }
    assert body["retakes"]["rounds"] == 3
    assert body["retakes"]["by_site"] == [
        {"site": "A", "rounds": 0, "won": 0},
        {"site": "B", "rounds": 3, "won": 1},
    ]
    assert body["retakes"]["by_situation"] == [{"us": 1, "them": 2, "rounds": 3, "won": 1}]
    assert body["economy"] == [
        {"buy": "pistol", "rounds": 2, "won": 1},
        {"buy": "eco", "rounds": 3, "won": 1},
        {"buy": "semi", "rounds": 0, "won": 0},
        {"buy": "force", "rounds": 0, "won": 0},
        {"buy": "full", "rounds": 8, "won": 4},
    ]


def test_the_trade_network_names_the_teams_players_only(people: People) -> None:
    two_matches(people)
    trades = stats(people)["trades"]
    # The stand-in is neither named nor counted, and their links go nowhere; OWNER's death they
    # traded still counts in OWNER's total. NEWCOMER only traded: no deaths.
    assert trades["players"] == [
        {"steam_id": str(OWNER), "name": name(OWNER), "deaths": 4, "traded": 3},
        {"steam_id": str(MEMBER), "name": name(MEMBER), "deaths": 2, "traded": 0},
        {"steam_id": str(NEWCOMER), "name": name(NEWCOMER), "deaths": 0, "traded": 0},
    ]
    assert trades["links"] == sorted(
        [
            {"trader": str(MEMBER), "victim": str(OWNER), "count": 1},
            {"trader": str(NEWCOMER), "victim": str(OWNER), "count": 1},
        ],
        key=lambda link: (link["trader"], link["victim"]),
    )
    assert str(STRANGERS[5]) not in json.dumps(trades)


def test_filters_by_map_period_and_type(people: People) -> None:
    nuke, mirage = two_matches(people)
    db = people.db
    old = add_match(db, {"A": ROSTER, "B": []}, days_ago=40, score=(13, 4))
    put(db, old, "A", [("team.buy", "full", "full", 20, 10)])
    # A match that would count but whose team metrics are not written yet.
    add_match(db, {"A": ROSTER, "B": []}, days_ago=2, score=(13, 4))
    # A shared solo match: no side of ours, never counted.
    shared = add_match(db, {"A": [VIEWER], "B": []}, days_ago=1, score=(13, 4))
    put(db, shared, "A", [("team.buy", "full", "full", 30, 30)])

    body = stats(people)
    assert (body["matches"], body["rounds"], body["pending"]) == (2, 13, 1)
    longer = stats(people, "?days=60")
    assert (longer["matches"], longer["rounds"]) == (3, 33)

    nuke_only = stats(people, "?map=de_nuke")
    assert (nuke_only["matches"], nuke_only["rounds"], nuke_only["pending"]) == (1, 10, 1)
    assert nuke_only["maps"] == ["de_mirage", "de_nuke"]  # the choices stay
    assert {s["map"] for s in nuke_only["sites"]} == {"de_nuke"}

    db.execute("UPDATE match SET mode = 'scrim' WHERE id = %s", (mirage,))
    scrims = stats(people, "?type=scrim")
    assert (scrims["matches"], scrims["rounds"], scrims["maps"]) == (1, 3, ["de_mirage"])
    official = stats(people, "?type=official")
    assert (official["matches"], official["rounds"]) == (1, 10)
    assert stats(people, "?map=de_inferno")["matches"] == 0

    for query in ("?days=0", "?days=366", "?type=premier", "?map=de_nuke%27", "?map=DE_NUKE"):
        refused = people.call(MEMBER, "GET", f"/teams/team-one/stats{query}")
        assert refused.status_code == 422, query
    assert nuke  # used above through the team's rows


def test_only_members_who_may_read_matches_see_the_stats(people: People) -> None:
    team = setup_team(people)
    refused = people.call(OTHER, "GET", "/teams/team-one/stats")
    assert (refused.status_code, refused.json()["detail"]) == (404, "team_not_found")
    people.db.execute(
        "WITH r AS (INSERT INTO workspace_role (workspace_id, name, permissions) "
        "VALUES (%s, 'commenter', '{review.comment}') RETURNING id) "
        "UPDATE membership SET role_id = (SELECT id FROM r) "
        "WHERE workspace_id = %s AND user_id = %s",
        (team["id"], team["id"], people.user_id(VIEWER)),
    )
    forbidden = people.call(VIEWER, "GET", "/teams/team-one/stats")
    assert (forbidden.status_code, forbidden.json()["detail"]) == (403, "forbidden")
    # Without any match, the numbers are empty, not missing.
    empty = stats(people, who=OWNER)
    assert (empty["matches"], empty["rounds"], empty["sites"]) == (0, 0, [])
    assert empty["trades"] == {"players": [], "links": []}


def test_the_team_reads_its_matches_only(people: People) -> None:
    """A match with our side, which OWNER sees through their personal space and the team does
    not, never counts."""
    team = setup_team(people)
    db = people.db
    register(db)
    mine = add_match(db, {"A": ROSTER, "B": []}, days_ago=1, score=(13, 4))
    put(db, mine, "A", [("team.buy", "full", "full", 17, 13)])
    assert stats(people, who=OWNER)["matches"] == 1
    db.execute(
        "DELETE FROM workspace_match WHERE workspace_id = %s AND match_id = %s", (team["id"], mine)
    )
    assert people.call(OWNER, "GET", f"/matches/{mine}").status_code == 200
    body = stats(people, who=OWNER)
    assert (body["matches"], body["rounds"], body["pending"], body["maps"]) == (0, 0, 0, [])


def test_a_match_with_an_older_version_waits_for_the_backfill(people: People) -> None:
    nuke, _ = two_matches(people)
    db = people.db
    # A new formula of `team.trades`: the Nuke match still holds 1.0.0 until it is filled again.
    db.execute(
        "INSERT INTO metric_definition (metric_id, version, name, unit, kind, params, doc) "
        "VALUES ('team.trades', '1.1.0', 'team.trades', 'table', 'team', '{}', '')"
    )
    db.execute("UPDATE metric_current SET version = '1.1.0' WHERE metric_id = 'team.trades'")
    db.execute(
        "UPDATE team_metric_value SET version = '1.1.0' WHERE metric_id = 'team.trades' "
        "AND match_id <> %s",
        (nuke,),
    )
    body = stats(people)
    assert (body["matches"], body["rounds"], body["pending"]) == (1, 3, 1)
    assert [p["steam_id"] for p in body["trades"]["players"]] == [str(OWNER), str(NEWCOMER)]
