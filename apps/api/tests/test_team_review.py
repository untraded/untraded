# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""A team's review (comments, tags, playlists) against PostgreSQL (UNTRADED_TEST_DATABASE_URL;
skipped otherwise), through the API as the API role (row-level security, no BYPASSRLS), and
the database's own guards called directly as that role."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import psycopg
import pytest
import test_team_routes as base
from test_team_matches import VIEWER, add_match, roster_since, setup_team
from test_team_routes import (
    ADMIN,
    LATECOMER,
    MEMBER,
    NEWCOMER,
    OTHER,
    OWNER,
    URL,
    People,
    as_api,
    outcome,
    role,
)

from untraded_worker.erase import erase_player
from untraded_worker.store import LocalStore

client, db, people = base.client, base.db, base.people

pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(not URL, reason="UNTRADED_TEST_DATABASE_URL is not set"),
]
THIRD = 76561198000000111
"""A player of the second team."""
ONE = "/teams/team-one"
TWO = "/teams/team-two"


def add_rounds(db: psycopg.Connection[Any], match_id: str, count: int = 3) -> None:
    """Rounds 1 to `count`; round n runs from tick 1000n to 1000n + 900."""
    for n in range(1, count + 1):
        db.execute(
            "INSERT INTO round (match_id, round, start_tick, freeze_end_tick, end_tick, "
            "winner_side, winner_team, reason, ct_team, score_a, score_b, is_overtime) "
            "VALUES (%s, %s, %s, %s, %s, 'CT', 'A', 'ct_killed', 'A', %s, 0, false)",
            (match_id, n, 1000 * n, 1000 * n + 100, 1000 * n + 900, n),
        )


def name(db: psycopg.Connection[Any], steam_id: int, display_name: str) -> None:
    db.execute(
        "UPDATE app_user SET display_name = %s WHERE steam_id = %s", (display_name, steam_id)
    )


def team_two(people: People) -> dict[str, Any]:
    """`team-two`: OTHER (owner), LATECOMER and THIRD on its roster for a year, VIEWER a viewer
    (also a member of team one)."""
    people.add(LATECOMER)
    people.add(THIRD)
    created = people.call(
        ADMIN,
        "POST",
        "/admin/teams",
        json={"name": "Team Two", "slug": "team-two", "owner_steam_id": str(OTHER)},
    )
    assert created.status_code == 201, created.text
    team: dict[str, Any] = people.call(OTHER, "GET", TWO).json()
    for steam_id, role_name in ((LATECOMER, "player"), (THIRD, "player"), (VIEWER, "viewer")):
        invited = people.call(
            OTHER,
            "POST",
            f"{TWO}/invitations",
            json={"role_id": role(team, role_name), "max_uses": 1},
        )
        token = invited.json()["token"]
        assert people.call(steam_id, "POST", f"/team-invitations/{token}/accept").status_code == 200
    for steam_id in (OTHER, LATECOMER, THIRD):
        put = people.call(OTHER, "PUT", f"{TWO}/roster/{steam_id}", json={"role": "starter"})
        assert put.status_code == 200, put.text
        roster_since(people.db, steam_id, 365)
    return team


def comment(
    people: People, steam_id: int, base_url: str, match_id: str, round_number: int, body: str
) -> dict[str, Any]:
    posted = people.call(
        steam_id,
        "POST",
        f"{base_url}/matches/{match_id}/rounds/{round_number}/comments",
        json={"body": body},
    )
    assert posted.status_code == 201, posted.text
    found: dict[str, Any] = posted.json()
    return found


def review(people: People, steam_id: int, base_url: str, match_id: str) -> dict[str, Any]:
    got = people.call(steam_id, "GET", f"{base_url}/matches/{match_id}/review")
    assert got.status_code == 200, got.text
    found: dict[str, Any] = got.json()
    return found


def detail(response: Any) -> tuple[int, Any]:
    return response.status_code, response.json().get("detail")


# ===========================================================================================
# Comments
# ===========================================================================================


def test_a_player_comments_a_round_and_the_team_reads_it(people: People) -> None:
    setup_team(people)
    name(people.db, MEMBER, "Member")
    match = add_match(
        people.db, {"A": [OWNER, MEMBER, NEWCOMER], "B": []}, days_ago=1, score=(13, 5)
    )
    add_rounds(people.db, match)

    posted = people.call(
        MEMBER,
        "POST",
        f"{ONE}/matches/{match}/rounds/2/comments",
        json={"body": "  late push B\r\n<b>not bold</b>  ", "tick": 2100},
    )
    assert posted.status_code == 201, posted.text
    said = posted.json()
    assert (said["body"], said["tick"], said["round"]) == ("late push B\n<b>not bold</b>", 2100, 2)
    assert (said["author_name"], said["mine"], said["can_edit"], said["can_delete"]) == (
        "Member",
        True,
        True,
        True,
    )
    assert said["edited_at"] is None

    seen = review(people, VIEWER, ONE, match)
    assert seen["permissions"] == {"comment": False, "manage": False}
    [theirs] = seen["comments"]
    assert (theirs["mine"], theirs["can_edit"], theirs["can_delete"]) == (False, False, False)
    by_owner = review(people, OWNER, ONE, match)["comments"][0]
    assert (by_owner["can_edit"], by_owner["can_delete"]) == (False, True)

    # The author edits it; nobody else can, not even the owner.
    edited = people.call(MEMBER, "PATCH", f"{ONE}/comments/{said['id']}", json={"body": "B late"})
    assert edited.status_code == 200, edited.text
    assert edited.json()["body"] == "B late"
    assert edited.json()["edited_at"] is not None
    for steam_id in (OWNER, VIEWER):
        refused = people.call(steam_id, "PATCH", f"{ONE}/comments/{said['id']}", json={"body": "x"})
        assert detail(refused) == (403, "forbidden")

    # An observer neither comments nor deletes; a manager deletes someone else's.
    refused = people.call(
        VIEWER, "POST", f"{ONE}/matches/{match}/rounds/1/comments", json={"body": "hi"}
    )
    assert detail(refused) == (403, "forbidden")
    assert detail(people.call(VIEWER, "DELETE", f"{ONE}/comments/{said['id']}")) == (
        403,
        "forbidden",
    )
    assert people.call(OWNER, "DELETE", f"{ONE}/comments/{said['id']}").status_code == 204
    assert review(people, MEMBER, ONE, match)["comments"] == []
    assert detail(people.call(MEMBER, "DELETE", f"{ONE}/comments/{said['id']}")) == (
        404,
        "comment_not_found",
    )


def test_a_comment_is_checked_against_the_match_and_its_round(people: People) -> None:
    setup_team(people)
    match = add_match(
        people.db, {"A": [OWNER, MEMBER, NEWCOMER], "B": []}, days_ago=1, score=(13, 5)
    )
    elsewhere = add_match(people.db, {"A": [OTHER], "B": []}, days_ago=2, score=(13, 5))
    add_rounds(people.db, match)
    add_rounds(people.db, elsewhere)
    url = f"{ONE}/matches/{match}/rounds"

    def post(path: str, body: dict[str, Any]) -> tuple[int, Any]:
        return detail(people.call(MEMBER, "POST", path, json=body))

    assert post(f"{url}/9/comments", {"body": "x"}) == (404, "round_not_found")
    assert post(f"{url}/1/comments", {"body": "x", "tick": 50}) == (422, "tick_invalid")
    assert post(f"{url}/1/comments", {"body": " \n\t "}) == (422, "comment_invalid")
    assert post(f"{url}/1/comments", {"body": "x" * 2001}) == (422, "comment_invalid")
    assert post(f"{url}/1/comments", {"body": "evil ‮ txt"}) == (422, "comment_invalid")
    assert post(f"{url}/1/comments", {"body": "bell \x07"}) == (422, "comment_invalid")
    assert post(f"{url}/1/comments", {"body": "x" * 2000})[0] == 201
    # A match the team does not see, though its author may (no one on the roster played it).
    assert post(f"{ONE}/matches/{elsewhere}/rounds/1/comments", {"body": "x"}) == (
        404,
        "match_not_found",
    )
    assert detail(people.call(MEMBER, "GET", f"{ONE}/matches/{elsewhere}/review")) == (
        404,
        "match_not_found",
    )
    # 200 comments per round at most.
    team_id = people.db.execute("SELECT id FROM workspace WHERE slug = 'team-one'").fetchone()
    assert team_id is not None
    people.db.execute(
        "INSERT INTO review_comment (workspace_id, match_id, round, body) "
        "SELECT %s, %s, 2, 'x' FROM generate_series(1, 200)",
        (team_id[0], match),
    )
    assert post(f"{url}/2/comments", {"body": "one more"}) == (409, "comment_limit")
    assert post(f"{url}/1/comments", {"body": "zero\u200bwidth"}) == (422, "comment_invalid")


# ===========================================================================================
# Two teams on one match
# ===========================================================================================


def test_two_teams_on_one_match_never_read_each_others_review(people: People) -> None:
    one = setup_team(people)
    two = team_two(people)
    scrim = add_match(
        people.db,
        {"A": [OWNER, MEMBER, NEWCOMER], "B": [OTHER, LATECOMER, THIRD]},
        days_ago=1,
        score=(13, 11),
    )
    add_rounds(people.db, scrim)
    ours = comment(people, MEMBER, ONE, scrim, 1, "their A exec is slow")
    theirs = comment(people, LATECOMER, TWO, scrim, 1, "we were slow on A")
    tagged = people.call(
        OWNER, "PUT", f"{ONE}/matches/{scrim}/rounds/1/tags", json={"tags": ["anti-exec"]}
    )
    assert tagged.status_code == 200, tagged.text
    playlist = people.call(OWNER, "POST", f"{ONE}/playlists", json={"name": "Their execs"}).json()
    added = people.call(
        OWNER,
        "POST",
        f"{ONE}/playlists/{playlist['id']}/rounds",
        json={"match_id": scrim, "round": 1},
    )
    assert added.status_code == 200, added.text

    # Each team reads its own review of the shared match, and nothing of the other's.
    two_review = review(people, OTHER, TWO, scrim)
    assert [c["id"] for c in two_review["comments"]] == [theirs["id"]]
    assert (two_review["tags"], two_review["playlists"]) == ([], [])
    assert people.call(OTHER, "GET", f"{TWO}/playlists").json() == []
    assert people.call(OTHER, "GET", f"{TWO}/review/tags").json() == []
    assert [c["id"] for c in review(people, MEMBER, ONE, scrim)["comments"]] == [ours["id"]]
    # A member of both teams sees each team's review in its own space only.
    assert [c["id"] for c in review(people, VIEWER, TWO, scrim)["comments"]] == [theirs["id"]]
    assert [c["id"] for c in review(people, VIEWER, ONE, scrim)["comments"]] == [ours["id"]]
    assert detail(people.call(VIEWER, "GET", f"{TWO}/playlists/{playlist['id']}")) == (
        404,
        "playlist_not_found",
    )
    # The other team's routes are closed, and so are its ids through one's own team.
    assert detail(people.call(OTHER, "GET", f"{ONE}/matches/{scrim}/review")) == (
        404,
        "team_not_found",
    )
    assert detail(people.call(OTHER, "DELETE", f"{TWO}/comments/{ours['id']}")) == (
        404,
        "comment_not_found",
    )
    assert detail(
        people.call(OTHER, "PATCH", f"{TWO}/comments/{ours['id']}", json={"body": "x"})
    ) == (404, "comment_not_found")
    assert detail(people.call(OTHER, "DELETE", f"{TWO}/playlists/{playlist['id']}")) == (
        404,
        "playlist_not_found",
    )

    # Row-level security itself: the API role reads only its own team's rows, whatever the query.
    other = people.user_id(OTHER)
    with as_api(other) as conn:
        for table, expected in (
            ("review_comment", 1),
            ("review_tag", 0),
            ("review_playlist", 0),
            ("review_playlist_round", 0),
        ):
            row = conn.execute(f"SELECT count(*) FROM {table}").fetchone()
            assert row == (expected,), table
    # The database functions refuse the other team's rows, and the API role writes no table.
    assert (
        outcome(
            other,
            "SELECT add_review_comment(%s, %s, 1, NULL, 'x')",
            (one["id"], scrim),
        )
        == "team_not_found"
    )
    assert (
        outcome(other, "SELECT delete_review_comment(%s, %s)", (two["id"], ours["id"]))
        == "comment_not_found"
    )
    assert (
        outcome(
            other,
            "SELECT set_review_tags(%s, %s, 1, ARRAY['x'])",
            (one["id"], scrim),
        )
        == "team_not_found"
    )
    assert (
        outcome(
            other,
            "INSERT INTO review_comment (workspace_id, match_id, round, body) "
            "VALUES (%s, %s, 1, 'x')",
            (two["id"], scrim),
        )
        == "denied"
    )
    assert (
        outcome(people.user_id(MEMBER), "DELETE FROM review_comment WHERE id = %s", (ours["id"],))
        == "denied"
    )


def test_an_observer_and_a_player_are_held_by_the_database_too(people: People) -> None:
    team = setup_team(people)
    match = add_match(
        people.db, {"A": [OWNER, MEMBER, NEWCOMER], "B": []}, days_ago=1, score=(13, 5)
    )
    add_rounds(people.db, match)
    said = comment(people, NEWCOMER, ONE, match, 1, "mine")
    viewer, member = people.user_id(VIEWER), people.user_id(MEMBER)
    assert (
        outcome(viewer, "SELECT add_review_comment(%s, %s, 1, NULL, 'x')", (team["id"], match))
        == "forbidden"
    )
    assert outcome(member, "SELECT edit_review_comment(%s, %s, 'x')", (team["id"], said["id"])) == (
        "forbidden"
    )
    assert outcome(member, "SELECT delete_review_comment(%s, %s)", (team["id"], said["id"])) == (
        "forbidden"
    )
    assert (
        outcome(member, "SELECT create_review_playlist(%s, 'mine', '')", (team["id"],))
        == "forbidden"
    )
    assert (
        outcome(member, "SELECT set_review_tags(%s, %s, 1, ARRAY['x'])", (team["id"], match))
        == "forbidden"
    )


# ===========================================================================================
# Tags
# ===========================================================================================


def test_tags_are_cleaned_bounded_and_set_by_a_manager(people: People) -> None:
    setup_team(people)
    match = add_match(
        people.db, {"A": [OWNER, MEMBER, NEWCOMER], "B": []}, days_ago=1, score=(13, 5)
    )
    add_rounds(people.db, match)
    url = f"{ONE}/matches/{match}/rounds/2/tags"

    put = people.call(OWNER, "PUT", url, json={"tags": ["Retake", " eco   round ", "retake"]})
    assert put.status_code == 200, put.text
    assert put.json() == {"round": 2, "tags": ["eco round", "Retake"]}
    assert review(people, VIEWER, ONE, match)["tags"] == [
        {"round": 2, "tags": ["eco round", "Retake"]}
    ]
    assert people.call(VIEWER, "GET", f"{ONE}/review/tags").json() == [
        {"label": "eco round", "rounds": 1},
        {"label": "Retake", "rounds": 1},
    ]
    assert detail(people.call(MEMBER, "PUT", url, json={"tags": ["x"]})) == (403, "forbidden")
    assert detail(people.call(OWNER, "PUT", url, json={"tags": ["x" * 33]})) == (
        422,
        "tag_invalid",
    )
    assert detail(people.call(OWNER, "PUT", url, json={"tags": [" "]})) == (422, "tag_invalid")
    eleven = [f"t{n}" for n in range(11)]
    assert detail(people.call(OWNER, "PUT", url, json={"tags": eleven})) == (409, "tag_limit")
    assert people.call(OWNER, "PUT", url, json={"tags": []}).json() == {"round": 2, "tags": []}
    assert review(people, OWNER, ONE, match)["tags"] == []


# ===========================================================================================
# Playlists
# ===========================================================================================


def test_a_manager_keeps_ordered_playlists_of_rounds(people: People) -> None:
    team = setup_team(people)
    match = add_match(
        people.db, {"A": [OWNER, MEMBER, NEWCOMER], "B": []}, days_ago=1, score=(13, 5)
    )
    other = add_match(
        people.db, {"A": [], "B": [OWNER, MEMBER, NEWCOMER]}, days_ago=2, score=(4, 13)
    )
    add_rounds(people.db, match)
    add_rounds(people.db, other)

    assert detail(people.call(MEMBER, "POST", f"{ONE}/playlists", json={"name": "x"})) == (
        403,
        "forbidden",
    )
    assert detail(people.call(OWNER, "POST", f"{ONE}/playlists", json={"name": "  "})) == (
        422,
        "name_invalid",
    )
    created = people.call(
        OWNER,
        "POST",
        f"{ONE}/playlists",
        json={"name": " Failed   retakes ", "description": "Nuke, this week"},
    )
    assert created.status_code == 201, created.text
    playlist = created.json()
    assert (playlist["name"], playlist["description"], playlist["items"]) == (
        "Failed retakes",
        "Nuke, this week",
        [],
    )
    url = f"{ONE}/playlists/{playlist['id']}"
    for match_id, n in ((match, 3), (other, 1), (match, 1), (match, 3)):  # the last one is in
        added = people.call(OWNER, "POST", f"{url}/rounds", json={"match_id": match_id, "round": n})
        assert added.status_code == 200, added.text
    items = added.json()["items"]
    assert [(i["match_id"], i["round"]) for i in items] == [(match, 3), (other, 1), (match, 1)]
    assert (items[0]["our_team"], items[0]["winner_team"], items[1]["our_team"]) == ("A", "A", "B")
    assert (items[0]["map"], items[0]["score_a"], items[0]["score_b"]) == ("de_nuke", 13, 5)

    missing = people.call(OWNER, "POST", f"{url}/rounds", json={"match_id": match, "round": 7})
    assert detail(missing) == (404, "round_not_found")

    ordered = people.call(
        OWNER,
        "PUT",
        f"{url}/order",
        json={
            "rounds": [
                {"match_id": match, "round": 1},
                {"match_id": match, "round": 3},
                {"match_id": other, "round": 1},
            ]
        },
    )
    assert ordered.status_code == 200, ordered.text
    assert [(i["match_id"], i["round"]) for i in ordered.json()["items"]] == [
        (match, 1),
        (match, 3),
        (other, 1),
    ]
    incomplete = people.call(
        OWNER, "PUT", f"{url}/order", json={"rounds": [{"match_id": match, "round": 1}]}
    )
    assert detail(incomplete) == (422, "order_invalid")
    twice = [{"match_id": match, "round": 1}] * 3
    assert detail(people.call(OWNER, "PUT", f"{url}/order", json={"rounds": twice})) == (
        422,
        "order_invalid",
    )

    # The match page knows which of its rounds each playlist holds.
    assert review(people, VIEWER, ONE, match)["playlists"] == [
        {"id": playlist["id"], "name": "Failed retakes", "rounds": [1, 3]}
    ]

    assert people.call(OWNER, "DELETE", f"{url}/rounds/{match}/3").status_code == 204
    renamed = people.call(OWNER, "PATCH", url, json={"name": "Retakes"})
    assert (renamed.json()["name"], renamed.json()["description"]) == ("Retakes", "Nuke, this week")
    assert [p["rounds"] for p in people.call(VIEWER, "GET", f"{ONE}/playlists").json()] == [2]

    # Limits: 100 rounds per playlist, 50 playlists per team.
    people.db.execute(
        "INSERT INTO review_playlist_round (playlist_id, workspace_id, match_id, round, seq) "
        "SELECT %s, %s, m, n, 100 + n FROM generate_series(10, 58) n, "
        "unnest(ARRAY[%s, %s]::uuid[]) m",
        (playlist["id"], team["id"], match, other),
    )
    full = people.call(OWNER, "POST", f"{url}/rounds", json={"match_id": match, "round": 2})
    assert detail(full) == (409, "playlist_full")
    people.db.execute(
        "INSERT INTO review_playlist (workspace_id, name) "
        "SELECT %s, 'p' || n FROM generate_series(1, 49) n",
        (team["id"],),
    )
    assert detail(people.call(OWNER, "POST", f"{ONE}/playlists", json={"name": "51st"})) == (
        409,
        "playlist_limit",
    )

    assert people.call(OWNER, "DELETE", url).status_code == 204
    assert detail(people.call(OWNER, "GET", url)) == (404, "playlist_not_found")


def test_a_playlist_shows_only_the_rounds_of_matches_the_team_sees(people: People) -> None:
    team = setup_team(people)
    roster = add_match(
        people.db, {"A": [OWNER, MEMBER, NEWCOMER], "B": []}, days_ago=1, score=(13, 5)
    )
    shared = add_match(people.db, {"A": [VIEWER], "B": []}, days_ago=2, score=(13, 5))
    add_rounds(people.db, roster)
    add_rounds(people.db, shared)
    playlist = people.call(OWNER, "POST", f"{ONE}/playlists", json={"name": "Mixed"}).json()
    url = f"{ONE}/playlists/{playlist['id']}"
    for match_id in (shared, roster):
        people.call(OWNER, "POST", f"{url}/rounds", json={"match_id": match_id, "round": 1})
    people.call(OWNER, "PUT", f"{ONE}/matches/{shared}/rounds/1/tags", json={"tags": ["solo"]})
    comment(people, MEMBER, ONE, shared, 1, "on the shared match")

    # The team no longer sees the shared match (as when its player stops sharing it).
    people.db.execute(
        "DELETE FROM workspace_match WHERE workspace_id = %s AND match_id = %s",
        (team["id"], shared),
    )
    got = people.call(MEMBER, "GET", url).json()
    assert ([i["match_id"] for i in got["items"]], got["rounds"]) == ([roster], 1)
    assert people.call(MEMBER, "GET", f"{ONE}/review/tags").json() == []
    assert detail(people.call(MEMBER, "GET", f"{ONE}/matches/{shared}/review")) == (
        404,
        "match_not_found",
    )
    hidden = people.call(
        OWNER,
        "PUT",
        f"{url}/order",
        json={"rounds": [{"match_id": shared, "round": 1}, {"match_id": roster, "round": 1}]},
    )
    assert detail(hidden) == (422, "order_invalid")
    assert (
        people.call(
            OWNER, "PUT", f"{url}/order", json={"rounds": [{"match_id": roster, "round": 1}]}
        ).status_code
        == 200
    )

    # Hidden, not deleted: the access back, the round is back, after the ones ordered meanwhile.
    people.db.execute(
        "INSERT INTO workspace_match (workspace_id, match_id, reason) VALUES (%s, %s, 'shared')",
        (team["id"], shared),
    )
    back = people.call(MEMBER, "GET", url).json()
    assert [i["match_id"] for i in back["items"]] == [roster, shared]
    assert back["items"][1]["tags"] == ["solo"]
    assert back["items"][1]["comments"] == 1


# ===========================================================================================
# Leaving, erasure, deletion
# ===========================================================================================


def test_a_comment_stays_signed_after_its_author_leaves_then_anonymous_once_erased(
    people: People, tmp_path: Path
) -> None:
    setup_team(people)
    name(people.db, MEMBER, "Member")
    # VIEWER on the roster too: the match stays the team's without MEMBER.
    people.call(OWNER, "PUT", f"{ONE}/roster/{VIEWER}", json={"role": "standin"})
    roster_since(people.db, VIEWER, 365)
    match = add_match(
        people.db, {"A": [OWNER, MEMBER, NEWCOMER, VIEWER], "B": []}, days_ago=1, score=(13, 5)
    )
    add_rounds(people.db, match)
    said = comment(people, MEMBER, ONE, match, 1, "Member here: I should have traded")

    left = people.call(MEMBER, "DELETE", f"{ONE}/members/{people.user_id(MEMBER)}")
    assert left.status_code == 204
    [kept] = review(people, OWNER, ONE, match)["comments"]
    assert (kept["author_name"], kept["body"]) == ("Member", "Member here: I should have traded")
    # The account is out of the team's sight, yet the comment is still signed.
    with as_api(people.user_id(OWNER)) as conn:
        assert conn.execute(
            "SELECT count(*) FROM app_user WHERE steam_id = %s", (MEMBER,)
        ).fetchone() == (0,)
    # The former member can no longer edit it.
    gone = people.call(MEMBER, "PATCH", f"{ONE}/comments/{said['id']}", json={"body": "x"})
    assert detail(gone) == (404, "team_not_found")

    assert people.call(MEMBER, "POST", "/me/erase", json={"confirm": True}).status_code == 202
    erase_player(people.db, LocalStore(tmp_path), MEMBER)
    [anonymous] = review(people, OWNER, ONE, match)["comments"]
    assert (anonymous["author_name"], anonymous["body"], anonymous["mine"]) == (
        None,
        "Member here: I should have traded",
        False,
    )
    assert anonymous["can_delete"] is True  # the owner manages the review
    assert people.db.execute(
        "SELECT author_id, author_name FROM review_comment WHERE id = %s", (said["id"],)
    ).fetchone() == (None, None)
    # A former member's comment is the managers' to delete, not any commenter's.
    refused = people.call(NEWCOMER, "DELETE", f"{ONE}/comments/{said['id']}")
    assert detail(refused) == (403, "forbidden")
    assert review(people, NEWCOMER, ONE, match)["comments"][0]["can_delete"] is False
    assert people.call(OWNER, "DELETE", f"{ONE}/comments/{said['id']}").status_code == 204


def test_deleting_the_team_deletes_its_review(people: People) -> None:
    setup_team(people)
    match = add_match(
        people.db, {"A": [OWNER, MEMBER, NEWCOMER], "B": []}, days_ago=1, score=(13, 5)
    )
    add_rounds(people.db, match)
    comment(people, MEMBER, ONE, match, 1, "x")
    people.call(OWNER, "PUT", f"{ONE}/matches/{match}/rounds/1/tags", json={"tags": ["x"]})
    playlist = people.call(OWNER, "POST", f"{ONE}/playlists", json={"name": "x"}).json()
    people.call(
        OWNER,
        "POST",
        f"{ONE}/playlists/{playlist['id']}/rounds",
        json={"match_id": match, "round": 1},
    )
    assert people.call(OWNER, "DELETE", ONE).status_code == 202
    for table in ("review_comment", "review_tag", "review_playlist", "review_playlist_round"):
        assert people.db.execute(f"SELECT count(*) FROM {table}").fetchone() == (0,), table
    assert people.db.execute("SELECT count(*) FROM match WHERE id = %s", (match,)).fetchone() == (
        1,
    )


def test_a_reanalysis_keeps_the_review(people: People) -> None:
    setup_team(people)
    match = add_match(
        people.db, {"A": [OWNER, MEMBER, NEWCOMER], "B": []}, days_ago=1, score=(13, 5)
    )
    add_rounds(people.db, match)
    comment(people, MEMBER, ONE, match, 2, "kept")
    # A reanalysis rewrites the match's rows (`load.load_match`).
    people.db.execute("DELETE FROM round WHERE match_id = %s", (match,))
    add_rounds(people.db, match)
    assert [c["body"] for c in review(people, OWNER, ONE, match)["comments"]] == ["kept"]
