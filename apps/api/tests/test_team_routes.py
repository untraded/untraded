# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Teams, against PostgreSQL (UNTRADED_TEST_DATABASE_URL; skipped otherwise): the routes, and
the database's own guards under row-level security, as the API role (no BYPASSRLS)."""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient
from helpers import add_user
from psycopg.types.json import Jsonb

from untraded_api.app import COOKIE, create_app
from untraded_api.deps import token_hash
from untraded_api.settings import Settings

URL = os.environ.get("UNTRADED_TEST_DATABASE_URL", "").replace(
    "postgresql+psycopg://", "postgresql://", 1
)
pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(not URL, reason="UNTRADED_TEST_DATABASE_URL is not set"),
]
ADMIN, OWNER, MEMBER, OTHER, NEWCOMER, LATECOMER = (76561198000000100 + n for n in range(6))


@pytest.fixture
def db() -> Iterator[psycopg.Connection[Any]]:
    with psycopg.connect(URL, autocommit=True) as conn:
        conn.execute(
            "TRUNCATE match, app_user, player, invitation, invitation_request, job, workspace, "
            "metric_definition CASCADE"
        )
        yield conn


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(
        database_url=URL,
        public_url="http://testserver",
        web_url="http://web",
        cookie_secure=False,
        admins=frozenset({ADMIN}),
        consent_version="2",
        backups_dir=str(tmp_path),
    )
    steam = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(500)))
    with TestClient(create_app(settings, steam_client=steam)) as test_client:
        yield test_client


class People:
    """Signed-in users by Steam ID, and requests made as one of them."""

    def __init__(self, db: psycopg.Connection[Any], client: TestClient) -> None:
        self.db = db
        self.client = client
        self.tokens: dict[int, str] = {}

    def add(self, steam_id: int, *, consents: bool = True) -> None:
        self.tokens[steam_id] = add_user(self.db, steam_id)
        if consents:
            self.db.execute(
                "INSERT INTO consent (user_id, text_version, analysis, research_corpus, "
                "recorded_by) SELECT id, '2', true, false, 'test' FROM app_user "
                "WHERE steam_id = %s",
                (steam_id,),
            )

    def call(self, steam_id: int, method: str, url: str, **kwargs: Any) -> httpx.Response:
        self.client.cookies.clear()
        self.client.cookies.set(COOKIE, self.tokens[steam_id])
        response: httpx.Response = self.client.request(method, url, **kwargs)
        return response

    def user_id(self, steam_id: int) -> str:
        row = self.db.execute("SELECT id FROM app_user WHERE steam_id = %s", (steam_id,)).fetchone()
        assert row is not None
        return str(row[0])


@pytest.fixture
def people(db: psycopg.Connection[Any], client: TestClient) -> People:
    found = People(db, client)
    for steam_id in (ADMIN, OWNER, MEMBER, OTHER):
        found.add(steam_id)
    return found


def make_team(people: People) -> dict[str, Any]:
    created = people.call(
        ADMIN,
        "POST",
        "/admin/teams",
        json={"name": " Team  One ", "slug": "Team-One", "owner_steam_id": str(OWNER)},
    )
    assert created.status_code == 201, created.text
    return team_of(people, OWNER)


def team_of(people: People, steam_id: int) -> dict[str, Any]:
    found = people.call(steam_id, "GET", "/teams/team-one")
    assert found.status_code == 200, found.text
    body: dict[str, Any] = found.json()
    return body


def role(team: dict[str, Any], name: str) -> str:
    return str(next(r["id"] for r in team["roles"] if r["name"] == name))


def invite(people: People, team: dict[str, Any], role_name: str, uses: int = 1) -> str:
    invited = people.call(
        OWNER,
        "POST",
        "/teams/team-one/invitations",
        json={"role_id": role(team, role_name), "max_uses": uses},
    )
    assert invited.status_code == 201, invited.text
    return str(invited.json()["token"])


def join(people: People, steam_id: int, team: dict[str, Any], role_name: str) -> None:
    token = invite(people, team, role_name)
    accepted = people.call(steam_id, "POST", f"/team-invitations/{token}/accept")
    assert accepted.status_code == 200, accepted.text


@contextmanager
def as_api(user_id: str | None) -> Iterator[psycopg.Connection[Any]]:
    """One transaction as the API role, seen as `user_id`; rolled back at the end."""
    with psycopg.connect(URL) as conn:
        conn.execute("SET LOCAL ROLE untraded_api")
        if user_id is not None:
            conn.execute("SELECT set_config('app.user_id', %s, true)", (user_id,))
        try:
            yield conn
        finally:
            conn.rollback()


def outcome(user_id: str, sql: str, params: tuple[Any, ...] = ()) -> str:
    """`ok`, `denied` (no privilege) or the database's refusal code, as the API role."""
    with as_api(user_id) as conn:
        try:
            conn.execute(sql, params)
        except psycopg.errors.InsufficientPrivilege:
            return "denied"
        except psycopg.Error as error:
            if error.sqlstate != "UT001":
                raise
            return str(error.diag.message_primary)
    return "ok"


# ===========================================================================================
# Creating a team
# ===========================================================================================


def test_the_admin_creates_a_team_with_its_owner_and_default_roles(people: People) -> None:
    team = make_team(people)
    assert (team["name"], team["slug"]) == ("Team One", "team-one")
    assert team["my_role"]["name"] == "owner"
    assert team["my_role"]["permissions"] == ["*"]
    assert {r["name"]: r["permissions"] for r in team["roles"]} == {
        "owner": ["*"],
        "coach": [
            "matches.read",
            "matches.upload",
            "review.comment",
            "review.manage",
            "roster.edit",
            "members.manage",
        ],
        "player": ["matches.read", "matches.upload", "review.comment"],
        "viewer": ["matches.read"],
    }
    assert [r["name"] for r in team["roles"]] == ["owner", "coach", "player", "viewer"]
    assert [m["steam_id"] for m in team["members"]] == [str(OWNER)]
    listed = people.call(ADMIN, "GET", "/admin/teams").json()
    assert [(t["slug"], t["members"]) for t in listed] == [("team-one", 1)]
    created_by = people.db.execute("SELECT created_by FROM workspace WHERE kind = 'team'")
    assert created_by.fetchall() == [(None,)]  # the admin can still be erased
    me = people.call(OWNER, "GET", "/me").json()
    assert [(w["kind"], w["slug"], w["role"]) for w in me["workspaces"]] == [
        ("personal", f"u-{OWNER}", "owner"),
        ("team", "team-one", "owner"),
    ]


@pytest.mark.parametrize(
    ("slug", "owner", "status", "code"),
    [
        ("u-76561198000000101", OWNER, 422, "slug_invalid"),
        ("ab", OWNER, 422, "slug_invalid"),
        ("bad slug", OWNER, 422, "slug_invalid"),
        ("team-one", OWNER, 409, "slug_taken"),
        ("TEAM-ONE", OWNER, 409, "slug_taken"),
        ("team-two", 76561198000000999, 422, "owner_unknown"),
    ],
)
def test_a_team_needs_a_free_valid_slug_and_a_registered_owner(
    people: People, slug: str, owner: int, status: int, code: str
) -> None:
    make_team(people)
    refused = people.call(
        ADMIN,
        "POST",
        "/admin/teams",
        json={"name": "T", "slug": slug, "owner_steam_id": str(owner)},
    )
    assert (refused.status_code, refused.json()["detail"]) == (status, code)


def test_only_an_admin_creates_or_lists_teams(people: People) -> None:
    assert people.call(OWNER, "GET", "/admin/teams").status_code == 403
    body = {"name": "T", "slug": "mine", "owner_steam_id": str(OWNER)}
    assert people.call(OWNER, "POST", "/admin/teams", json=body).status_code == 403
    assert outcome(people.user_id(OWNER), "SELECT create_team('T', 'mine', %s)", (OWNER,)) == (
        "denied"
    )


def test_a_non_member_does_not_see_the_team(people: People) -> None:
    make_team(people)
    found = people.call(OTHER, "GET", "/teams/team-one")
    assert (found.status_code, found.json()["detail"]) == (404, "team_not_found")
    with as_api(people.user_id(OTHER)) as conn:
        assert conn.execute("SELECT count(*) FROM workspace WHERE kind = 'team'").fetchone() == (0,)


# ===========================================================================================
# Invitation links
# ===========================================================================================


def test_a_member_joins_by_link_after_confirming(people: People) -> None:
    team = make_team(people)
    token = invite(people, team, "viewer", uses=2)
    assert people.db.execute("SELECT count(*) FROM membership").fetchone() == (5,)  # 4 + owner
    preview = people.client.get(f"/team-invitations/{token}")  # signed out: nothing is joined
    assert preview.status_code == 200
    assert {k: preview.json()[k] for k in ("team_name", "role")} == {
        "team_name": "Team One",
        "role": "viewer",
    }
    assert people.db.execute("SELECT count(*) FROM membership").fetchone() == (5,)
    stored = people.db.execute("SELECT token_hash, uses FROM team_invitation").fetchone()
    assert stored == (token_hash(token), 0)  # only the hash is kept

    joined = people.call(MEMBER, "POST", f"/team-invitations/{token}/accept")
    assert joined.json() == {"slug": "team-one"}
    again = people.call(MEMBER, "POST", f"/team-invitations/{token}/accept")
    assert (again.status_code, again.json()["detail"]) == (409, "already_member")
    me = people.call(MEMBER, "GET", "/me").json()
    assert [(w["slug"], w["role"], w["permissions"]) for w in me["workspaces"]][1] == (
        "team-one",
        "viewer",
        ["matches.read"],
    )
    listed = people.call(OWNER, "GET", "/teams/team-one/invitations").json()
    assert [(i["uses"], i["max_uses"], i.get("token")) for i in listed] == [(1, 2, None)]


def test_consent_comes_before_joining(people: People) -> None:
    team = make_team(people)
    people.add(NEWCOMER, consents=False)
    token = invite(people, team, "player")
    refused = people.call(NEWCOMER, "POST", f"/team-invitations/{token}/accept")
    assert (refused.status_code, refused.json()["detail"]) == (403, "consent_required")
    assert people.client.get(f"/team-invitations/{token}").status_code == 200  # not used up
    people.db.execute(
        "INSERT INTO consent (user_id, text_version, analysis, research_corpus, recorded_by) "
        "SELECT id, '1', true, false, 'test' FROM app_user WHERE steam_id = %s",
        (NEWCOMER,),
    )
    refused = people.call(NEWCOMER, "POST", f"/team-invitations/{token}/accept")
    assert refused.json()["detail"] == "consent_required"  # an older text
    agreed = people.call(
        NEWCOMER,
        "POST",
        "/me/consent",
        json={"text_version": "2", "analysis": True, "research_corpus": False},
    )
    assert agreed.status_code == 204
    assert people.call(NEWCOMER, "POST", f"/team-invitations/{token}/accept").status_code == 200


def test_expired_used_up_and_revoked_links_are_refused(people: People) -> None:
    team = make_team(people)
    people.add(NEWCOMER)
    expired, used, revoked = (invite(people, team, "player") for _ in range(3))
    people.db.execute(
        "UPDATE team_invitation SET expires_at = now() - interval '1 second' WHERE token_hash = %s",
        (token_hash(expired),),
    )
    assert people.call(MEMBER, "POST", f"/team-invitations/{used}/accept").status_code == 200
    listed = people.call(OWNER, "GET", "/teams/team-one/invitations").json()
    revoked_id = next(
        i["id"]
        for i in listed
        if people.db.execute(
            "SELECT token_hash = %s FROM team_invitation WHERE id = %s",
            (token_hash(revoked), i["id"]),
        ).fetchone()
        == (True,)
    )
    assert (
        people.call(OWNER, "DELETE", f"/teams/team-one/invitations/{revoked_id}").status_code == 204
    )
    for token in (expired, used, revoked, "x" * 43):
        preview = people.client.get(f"/team-invitations/{token}")
        assert (preview.status_code, preview.json()["detail"]) == (404, "invitation_invalid")
        accepted = people.call(NEWCOMER, "POST", f"/team-invitations/{token}/accept")
        assert (accepted.status_code, accepted.json()["detail"]) == (404, "invitation_invalid")
    assert people.call(OWNER, "GET", "/teams/team-one/invitations").json() == []


def test_the_last_use_of_a_link_goes_to_one_person_only(people: People) -> None:
    team = make_team(people)
    people.add(NEWCOMER)
    token = invite(people, team, "player")
    first, second = people.user_id(MEMBER), people.user_id(NEWCOMER)
    results: dict[str, str] = {}

    def accept_second() -> None:
        results["second"] = outcome(
            second, "SELECT accept_team_invitation(%s, '2')", (token_hash(token),)
        )

    with as_api(first) as conn:
        conn.execute("SELECT accept_team_invitation(%s, '2')", (token_hash(token),))
        racer = threading.Thread(target=accept_second)
        racer.start()
        time.sleep(0.5)
        assert racer.is_alive()  # waits on the link's lock
        conn.commit()  # `as_api` rolls back what is left: nothing
    racer.join(timeout=10)
    assert results == {"second": "invitation_invalid"}
    assert people.db.execute("SELECT uses FROM team_invitation").fetchone() == (1,)


def test_a_link_lets_new_accounts_in_within_its_uses(people: People) -> None:
    team = make_team(people)
    token = invite(people, team, "player", uses=1)
    digest = token_hash(token)
    opened = people.db.execute(
        "SELECT open_auth_session(%s, %s, interval '1 day', %s, %s)",
        (NEWCOMER, token_hash("s1"), digest, "  New Comer  "),
    ).fetchone()
    assert opened is not None
    assert opened[0] is not None
    assert people.db.execute(
        "SELECT display_name FROM app_user WHERE steam_id = %s", (NEWCOMER,)
    ).fetchone() == ("New Comer",)
    assert people.db.execute("SELECT uses, signups FROM team_invitation").fetchone() == (0, 1)
    # Its one account is used: another new account is not let in, an existing one signs in.
    refused = people.db.execute(
        "SELECT open_auth_session(%s, %s, interval '1 day', %s, NULL)",
        (LATECOMER, token_hash("s2"), digest),
    ).fetchone()
    assert refused == (None,)
    again = people.db.execute(
        "SELECT open_auth_session(%s, %s, interval '1 day', %s, NULL)",
        (NEWCOMER, token_hash("s3"), digest),
    ).fetchone()
    assert again is not None
    assert again[0] == opened[0]
    assert people.db.execute("SELECT signups FROM team_invitation").fetchone() == (1,)


def test_sign_in_carries_the_link_in_the_sign_in_cookie(people: People) -> None:
    token = "a" * 43
    sent = people.client.get(f"/auth/steam?team_invite={token}", follow_redirects=False)
    assert sent.status_code == 303
    state = sent.cookies.get("untraded_signin")
    assert state is not None
    assert state.endswith(f".{token}")
    plain = people.client.get("/auth/steam?team_invite=bad.token", follow_redirects=False)
    assert "." not in (plain.cookies.get("untraded_signin") or "")


# ===========================================================================================
# Roles and members: no escalation, an owner always
# ===========================================================================================


def test_a_viewer_neither_promotes_themselves_nor_changes_someone_elses_sharing(
    people: People,
) -> None:
    team = make_team(people)
    join(people, MEMBER, team, "viewer")
    member = people.user_id(MEMBER)
    for owner_like in ("owner", "coach"):
        changed = people.call(
            MEMBER,
            "PATCH",
            f"/teams/team-one/members/{member}",
            json={"role_id": role(team, owner_like)},
        )
        assert (changed.status_code, changed.json()["detail"]) == (403, "forbidden")
    for method, url, body in (
        ("POST", "/teams/team-one/invitations", {"role_id": role(team, "viewer"), "max_uses": 1}),
        ("GET", "/teams/team-one/invitations", None),
        ("PUT", f"/teams/team-one/roster/{MEMBER}", {"role": "starter"}),
        ("PATCH", "/teams/team-one", {"name": "Mine"}),
        ("DELETE", "/teams/team-one", None),
        ("POST", "/teams/team-one/owner", {"user_id": member}),
        ("DELETE", f"/teams/team-one/members/{people.user_id(OWNER)}", None),
    ):
        refused = people.call(MEMBER, method, url, json=body)
        assert (refused.status_code, refused.json()["detail"]) == (403, "forbidden"), url

    # The database refuses the same, whatever a route would do.
    team_id, owner_role = team["id"], role(team, "owner")
    for sql in (
        "UPDATE membership SET role_id = %(r)s WHERE workspace_id = %(t)s",
        "INSERT INTO membership (workspace_id, user_id, role_id) VALUES (%(t)s, %(u)s, %(r)s)",
        "UPDATE workspace_role SET permissions = '{*}' WHERE workspace_id = %(t)s",
        "UPDATE workspace_player SET share_solo = true WHERE workspace_id = %(t)s",
        "INSERT INTO team_invitation (id, workspace_id, token_hash, role_id, max_uses, "
        "expires_at) VALUES (gen_random_uuid(), %(t)s, sha256('x'), %(r)s, 1, now())",
    ):
        with as_api(member) as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(sql, {"t": team_id, "u": member, "r": owner_role})
    assert outcome(member, "SELECT set_member_role(%s, %s, %s)", (team_id, member, owner_role)) == (
        "forbidden"
    )

    # The owner shares nothing for the member: `share-solo` is the caller's own choice.
    people.call(OWNER, "PUT", "/teams/team-one/share-solo", json={"share": True})
    shares = dict(
        people.db.execute(
            "SELECT steam_id, share_solo FROM workspace_player WHERE workspace_id = %s",
            (team_id,),
        ).fetchall()
    )
    assert shares == {OWNER: True, MEMBER: False}
    assert (
        people.call(MEMBER, "PUT", "/teams/team-one/share-solo", json={"share": True}).status_code
        == 204
    )
    seen = {m["steam_id"]: m["share_solo"] for m in team_of(people, MEMBER)["members"]}
    assert seen == {str(OWNER): None, str(MEMBER): True}  # only their own


def test_a_coach_gives_no_role_stronger_than_theirs(people: People) -> None:
    team = make_team(people)
    join(people, MEMBER, team, "coach")
    join(people, OTHER, team, "player")
    owner, member, other = (people.user_id(s) for s in (OWNER, MEMBER, OTHER))

    def set_role(target: str, name: str) -> httpx.Response:
        return people.call(
            MEMBER, "PATCH", f"/teams/team-one/members/{target}", json={"role_id": role(team, name)}
        )

    assert (set_role(member, "owner").status_code, set_role(member, "owner").json()["detail"]) == (
        403,
        "role_too_high",
    )
    assert set_role(other, "owner").json()["detail"] == "role_too_high"
    assert set_role(owner, "viewer").json()["detail"] == "forbidden"  # the owner is stronger
    made = set_role(other, "coach")
    assert made.status_code == 200
    assert made.json()["role"]["name"] == "coach"
    invited = people.call(
        MEMBER,
        "POST",
        "/teams/team-one/invitations",
        json={"role_id": role(team, "owner"), "max_uses": 1},
    )
    assert (invited.status_code, invited.json()["detail"]) == (403, "role_too_high")
    for uses in (0, 21):
        bad = people.call(
            MEMBER,
            "POST",
            "/teams/team-one/invitations",
            json={"role_id": role(team, "player"), "max_uses": uses},
        )
        assert bad.status_code == 422
    removed = people.call(MEMBER, "DELETE", f"/teams/team-one/members/{owner}")
    assert (removed.status_code, removed.json()["detail"]) == (403, "forbidden")
    assert people.call(MEMBER, "DELETE", f"/teams/team-one/members/{other}").status_code == 204


def test_the_last_owner_stays_until_they_hand_over(people: People) -> None:
    team = make_team(people)
    join(people, MEMBER, team, "player")
    owner, member = people.user_id(OWNER), people.user_id(MEMBER)
    left = people.call(OWNER, "DELETE", f"/teams/team-one/members/{owner}")
    assert (left.status_code, left.json()["detail"]) == (409, "last_owner")
    demoted = people.call(
        OWNER, "PATCH", f"/teams/team-one/members/{owner}", json={"role_id": role(team, "coach")}
    )
    assert (demoted.status_code, demoted.json()["detail"]) == (409, "last_owner")
    stranger = people.call(
        OWNER, "POST", "/teams/team-one/owner", json={"user_id": people.user_id(OTHER)}
    )
    assert (stranger.status_code, stranger.json()["detail"]) == (409, "not_a_member")

    handed = people.call(OWNER, "POST", "/teams/team-one/owner", json={"user_id": member})
    assert handed.status_code == 200
    roles = {m["steam_id"]: m["role"]["name"] for m in handed.json()["members"]}
    assert roles == {str(OWNER): "player", str(MEMBER): "owner"}  # they swap roles
    assert people.call(OWNER, "DELETE", f"/teams/team-one/members/{owner}").status_code == 204
    assert people.call(OWNER, "GET", "/teams/team-one").status_code == 404


def test_an_owner_is_not_erased_before_handing_over(people: People) -> None:
    make_team(people)
    erased = people.call(OWNER, "POST", "/me/erase", json={"confirm": True})
    assert (erased.status_code, erased.json()["detail"]) == (409, "owner_must_hand_over")
    by_admin = people.call(ADMIN, "DELETE", f"/admin/players/{OWNER}")
    assert (by_admin.status_code, by_admin.json()["detail"]) == (409, "owner_must_hand_over")
    # Nothing closed: still signed in, still followed, no erasure queued.
    assert people.call(OWNER, "GET", "/me").status_code == 200
    assert people.db.execute(
        "SELECT deleted_at FROM app_user WHERE steam_id = %s", (OWNER,)
    ).fetchone() == (None,)
    assert people.db.execute("SELECT count(*) FROM job WHERE kind = 'erase_player'").fetchone() == (
        0,
    )
    # Another member is erased as before.
    assert people.call(MEMBER, "POST", "/me/erase", json={"confirm": True}).status_code == 202


def test_deleting_a_team_keeps_its_members_accounts(people: People) -> None:
    team = make_team(people)
    join(people, MEMBER, team, "coach")
    refused = people.call(MEMBER, "DELETE", "/teams/team-one")
    assert (refused.status_code, refused.json()["detail"]) == (403, "forbidden")
    assert people.call(OWNER, "DELETE", "/teams/team-one").status_code == 202
    assert people.db.execute("SELECT count(*) FROM workspace WHERE kind = 'team'").fetchone() == (
        0,
    )
    assert people.call(MEMBER, "GET", "/me").json()["workspaces"][0]["kind"] == "personal"


# ===========================================================================================
# Roster
# ===========================================================================================


def test_the_roster_holds_members_only_and_queues_the_access(people: People) -> None:
    team = make_team(people)
    join(people, MEMBER, team, "player")
    outsider = people.call(
        OWNER, "PUT", f"/teams/team-one/roster/{OTHER}", json={"role": "starter"}
    )
    assert (outsider.status_code, outsider.json()["detail"]) == (409, "not_a_member")
    put = people.call(OWNER, "PUT", f"/teams/team-one/roster/{MEMBER}", json={"role": "starter"})
    assert put.status_code == 200
    assert put.json()["roster"] == "starter"
    jobs = people.db.execute("SELECT kind, payload->>'steam_id' FROM job").fetchall()
    assert jobs == [("refresh_team_access", str(MEMBER))]
    standin = people.call(
        OWNER, "PUT", f"/teams/team-one/roster/{MEMBER}", json={"role": "standin"}
    )
    assert standin.json()["roster"] == "standin"
    put_owner = people.call(
        OWNER, "PUT", f"/teams/team-one/roster/{OWNER}", json={"role": "starter"}
    )
    assert put_owner.status_code == 200
    members = team_of(people, OWNER)["members"]
    assert [(m["steam_id"], m["roster"]) for m in members] == [
        (str(OWNER), "starter"),
        (str(MEMBER), "standin"),
    ]
    assert people.call(OWNER, "DELETE", f"/teams/team-one/roster/{MEMBER}").status_code == 204
    rows = people.db.execute(
        "SELECT valid_to IS NOT NULL FROM roster_member WHERE steam_id = %s", (MEMBER,)
    ).fetchall()
    assert rows == [(True,)]  # an end date, the history stays
    back = people.call(OWNER, "PUT", f"/teams/team-one/roster/{MEMBER}", json={"role": "starter"})
    assert back.json()["roster"] == "starter"  # the same day: the same row opens again
    # Leaving the team ends the roster row and the sharing.
    people.call(MEMBER, "PUT", "/teams/team-one/share-solo", json={"share": True})
    assert (
        people.call(
            MEMBER, "DELETE", f"/teams/team-one/members/{people.user_id(MEMBER)}"
        ).status_code
        == 204
    )
    assert people.db.execute(
        "SELECT count(*) FROM roster_member WHERE steam_id = %s AND valid_to IS NULL", (MEMBER,)
    ).fetchone() == (0,)
    assert people.db.execute(
        "SELECT count(*) FROM workspace_player WHERE steam_id = %s", (MEMBER,)
    ).fetchone() == (0,)


# ===========================================================================================
# What a team does not read, and what stays personal
# ===========================================================================================


def test_a_teammate_reads_neither_sessions_nor_advice_nor_aggregates_of_a_followed_player(
    people: People,
) -> None:
    team = make_team(people)
    join(people, MEMBER, team, "viewer")
    people.call(OWNER, "PUT", f"/teams/team-one/roster/{OWNER}", json={"role": "starter"})
    people.call(OWNER, "PUT", "/teams/team-one/share-solo", json={"share": True})
    db = people.db
    db.execute(
        "INSERT INTO metric_definition (metric_id, version, name, unit, kind, params, doc) "
        "VALUES ('base.kills', '1.0.0', 'Kills', 'count', 'value', '{}', '')"
    )
    db.execute(
        "INSERT INTO play_session (steam_id, started_at, ended_at, matches, rounds, "
        "reference_from, reference_to, reference_matches, reference_rounds, enough, params) "
        "VALUES (%s, now(), now(), 1, 5, current_date, current_date, 0, 0, false, %s)",
        (OWNER, Jsonb({})),
    )
    db.execute(
        "INSERT INTO metric_aggregate (steam_id, selection_hash, selection, metric_id, version, "
        "params_hash, value, matches, rounds) "
        "VALUES (%s, 'h', '{}', 'base.kills', '1.0.0', 'default', 1, 1, 5)",
        (OWNER,),
    )
    db.execute(
        "INSERT INTO advice (steam_id, workspace_id, session_from, session_to, rule_id, "
        "rule_version, priority, message_key, evidence) "
        "SELECT %s, id, now(), now(), 'r', '1', 1, 'k', '{}' FROM workspace WHERE slug = %s",
        (OWNER, f"u-{OWNER}"),
    )
    counts = (
        "SELECT (SELECT count(*) FROM play_session), (SELECT count(*) FROM metric_aggregate), "
        "(SELECT count(*) FROM advice), (SELECT count(*) FROM player WHERE steam_id = %s)"
    )
    with as_api(people.user_id(MEMBER)) as conn:
        assert conn.execute(counts, (OWNER,)).fetchone() == (0, 0, 0, 1)  # followed, not coached
    with as_api(people.user_id(OWNER)) as conn:
        assert conn.execute(counts, (OWNER,)).fetchone() == (1, 1, 1, 1)
    sessions = people.call(MEMBER, "GET", "/sessions").json()
    assert sessions["items"] == []


def test_a_team_members_own_list_is_unchanged(people: People) -> None:
    team = make_team(people)
    join(people, MEMBER, team, "viewer")
    db = people.db
    row = db.execute(
        "INSERT INTO match (mode, status, played_at) VALUES ('premier', 'ready', now()) "
        "RETURNING id"
    ).fetchone()
    assert row is not None
    match_id = row[0]
    db.execute(
        "INSERT INTO player (steam_id, last_name) VALUES (%s, 'o') ON CONFLICT DO NOTHING", (OWNER,)
    )
    db.execute(
        "INSERT INTO match_player (match_id, steam_id, team, name, rounds_on_team) "
        "VALUES (%s, %s, 'A', 'o', 5)",
        (match_id, OWNER),
    )
    db.execute(
        "INSERT INTO workspace_match (workspace_id, match_id, reason) "
        "SELECT id, %s, 'own'::access_reason FROM workspace WHERE slug = %s "
        "UNION ALL SELECT %s, %s, 'roster'::access_reason",
        (match_id, f"u-{OWNER}", team["id"], match_id),
    )
    # The viewer may open the team's match, but it is not in their own list.
    assert people.call(MEMBER, "GET", f"/matches/{match_id}").status_code == 200
    assert people.call(MEMBER, "GET", "/matches").json()["items"] == []
    mine = people.call(OWNER, "GET", "/matches").json()["items"]
    assert [m["id"] for m in mine] == [str(match_id)]


def test_withdrawing_the_consent_leaves_every_team(people: People) -> None:
    team = make_team(people)
    join(people, MEMBER, team, "player")
    people.call(OWNER, "PUT", f"/teams/team-one/roster/{MEMBER}", json={"role": "starter"})
    people.call(MEMBER, "PUT", "/teams/team-one/share-solo", json={"share": True})
    people.db.execute("TRUNCATE job")
    withdraw = {"text_version": "2", "analysis": False, "research_corpus": False}

    refused = people.call(OWNER, "POST", "/me/consent", json=withdraw)
    assert (refused.status_code, refused.json()["detail"]) == (409, "owner_must_hand_over")
    assert people.db.execute(
        "SELECT analysis FROM consent_current c JOIN app_user u ON u.id = c.user_id "
        "WHERE u.steam_id = %s",
        (OWNER,),
    ).fetchone() == (True,)  # nothing recorded

    assert people.call(MEMBER, "POST", "/me/consent", json=withdraw).status_code == 204
    assert [m["steam_id"] for m in team_of(people, OWNER)["members"]] == [str(OWNER)]
    assert people.db.execute(
        "SELECT count(*) FROM roster_member WHERE steam_id = %s AND valid_to IS NULL", (MEMBER,)
    ).fetchone() == (0,)
    assert people.db.execute(
        "SELECT count(*) FROM workspace_player WHERE steam_id = %s", (MEMBER,)
    ).fetchone() == (0,)
    assert people.db.execute("SELECT kind, payload->>'steam_id' FROM job").fetchall() == [
        ("refresh_team_access", str(MEMBER))
    ]


def test_a_removed_coachs_links_stop_working(people: People) -> None:
    team = make_team(people)
    join(people, MEMBER, team, "coach")
    made = people.call(
        MEMBER,
        "POST",
        "/teams/team-one/invitations",
        json={"role_id": role(team, "coach"), "max_uses": 5},
    )
    assert made.status_code == 201
    assert made.headers["cache-control"] == "no-store"
    token = made.json()["token"]
    assert people.client.get(f"/team-invitations/{token}").status_code == 200
    removed = people.call(OWNER, "DELETE", f"/teams/team-one/members/{people.user_id(MEMBER)}")
    assert removed.status_code == 204
    assert people.client.get(f"/team-invitations/{token}").status_code == 404
    again = people.call(MEMBER, "POST", f"/team-invitations/{token}/accept")
    assert (again.status_code, again.json()["detail"]) == (404, "invitation_invalid")


def test_a_teams_links_open_twenty_accounts_at_most(people: People) -> None:
    team = make_team(people)
    tokens = [invite(people, team, "player", uses=20), invite(people, team, "player", uses=20)]
    opened = 0
    for n in range(25):
        row = people.db.execute(
            "SELECT open_auth_session(%s, %s, interval '1 day', %s, NULL)",
            (76561198000100000 + n, token_hash(f"s{n}"), token_hash(tokens[n % 2])),
        ).fetchone()
        opened += row is not None and row[0] is not None
    assert opened == 20
