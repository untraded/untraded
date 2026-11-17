# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Team workspaces: the admin creates a team with its owner; its members join through an
invitation link, hold roles, keep the roster, and each chooses whether to share their solo
matches with it (ADR 0012).

Every write is one database function (migration 0016) that checks the caller's permission
itself: the API role writes no table, so a route cannot hand out more than the database allows.
Reads run as the user under row-level security: a team the user is not a member of does not
exist for them (404 `team_not_found`). Refusals carry a stable code the site translates
(`deps.refusals`).

What a team never reads, whatever the role: a player's play sessions, advice, votes and
aggregates (the policies of migration 0016). Which matches it sees is the worker's
`workspace_match`, recomputed when the roster, the members, a sharing choice or a consent change.
"""

# No `from __future__ import annotations`: FastAPI reads the dependencies from the annotations.

import datetime as dt
import re
import secrets
import uuid
from typing import Annotated, Any, Literal

import psycopg
from fastapi import APIRouter, HTTPException, Path, Response, status
from pydantic import BaseModel

from untraded_api.deps import (
    AdminDep,
    ConnDep,
    DatabaseDep,
    SettingsDep,
    UserDep,
    refusals,
    token_hash,
)

router = APIRouter(tags=["teams"])
admin_router = APIRouter(prefix="/admin", tags=["admin"])

Slug = Annotated[str, Path(min_length=1, max_length=64)]
SteamId = Annotated[str, Path(pattern=r"^\d{1,19}$")]
STEAM_MAX = 2**63 - 1
"""A Steam ID is a bigint: a larger number would reach the database as `numeric`."""
SLUG = re.compile(r"^[a-z0-9-]{3,32}$")
TOKEN = re.compile(r"^[A-Za-z0-9_-]{32,128}$")
"""An invitation token as `create_invitation` draws it (`secrets.token_urlsafe(32)`)."""
NAME_MAX = 64


class Role(BaseModel):
    id: uuid.UUID
    name: str
    """`owner`, `coach`, `player`, `viewer` (translated by the site), or a team's own name."""
    permissions: list[str]


class TeamMember(BaseModel):
    user_id: uuid.UUID
    steam_id: str
    display_name: str
    role: Role
    joined_at: dt.datetime
    roster: Literal["starter", "standin"] | None
    share_solo: bool | None
    """The signed-in user's own choice; null for the other members (it is theirs)."""


class Team(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    created_at: dt.datetime
    my_role: Role
    roles: list[Role]
    members: list[TeamMember]
    """Starters, then stand-ins, then the other members, each by name."""


class TeamInvitation(BaseModel):
    id: uuid.UUID
    role: Role
    max_uses: int
    uses: int
    expires_at: dt.datetime
    created_at: dt.datetime
    token: str | None = None
    """Only in the answer that creates it: the database keeps its hash, never the token."""


class InvitationPreview(BaseModel):
    team_name: str
    role: str
    expires_at: dt.datetime


class Joined(BaseModel):
    slug: str


class AdminTeam(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    members: int
    created_at: dt.datetime


class TeamIn(BaseModel):
    name: str
    slug: str
    owner_steam_id: str


class RenameIn(BaseModel):
    name: str


class MemberRoleIn(BaseModel):
    role_id: uuid.UUID


class OwnerIn(BaseModel):
    user_id: uuid.UUID


class InvitationIn(BaseModel):
    role_id: uuid.UUID
    max_uses: int


class RosterIn(BaseModel):
    role: Literal["starter", "standin"]


class ShareIn(BaseModel):
    share: bool


def clean_name(name: str) -> str:
    cleaned = " ".join(name.split())
    if not 1 <= len(cleaned) <= NAME_MAX:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {"field": "name"})
    return cleaned


# ===========================================================================================
# Admin
# ===========================================================================================

ADMIN_TEAMS = """
SELECT w.id, w.name, w.slug::text, (SELECT count(*) FROM membership m WHERE m.workspace_id = w.id),
       w.created_at
FROM workspace w WHERE w.kind = 'team'
"""


def _admin_team(row: tuple[Any, ...]) -> AdminTeam:
    return AdminTeam(id=row[0], name=row[1], slug=row[2], members=row[3], created_at=row[4])


@admin_router.get("/teams")
def admin_teams(conn: AdminDep) -> list[AdminTeam]:
    rows = conn.execute(f"{ADMIN_TEAMS} ORDER BY w.created_at DESC, w.id").fetchall()
    return [_admin_team(row) for row in rows]


@admin_router.post("/teams", status_code=status.HTTP_201_CREATED)
def admin_create_team(body: TeamIn, conn: AdminDep, settings: SettingsDep) -> AdminTeam:
    """Creates a team with its default roles and its roster; the owner (a registered user)
    becomes its first member. 422 `slug_invalid` or `owner_unknown`, 409 `slug_taken`."""
    name = clean_name(body.name)
    slug = body.slug.strip().lower()
    if not SLUG.match(slug) or re.match(r"^u-\d+$", slug):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "slug_invalid")
    # The public demo account owns nothing: anyone signed in as it would read the team.
    if (
        not re.match(r"^\d{1,19}$", body.owner_steam_id)
        or int(body.owner_steam_id) in (settings.demo_steam_id,)
        or int(body.owner_steam_id) > STEAM_MAX
    ):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "owner_unknown")
    with refusals():
        row = conn.execute(
            "SELECT create_team(%s, %s, %s)", (name, slug, int(body.owner_steam_id))
        ).fetchone()
    assert row is not None
    found = conn.execute(f"{ADMIN_TEAMS} AND w.id = %s", (row[0],)).fetchone()
    assert found is not None
    return _admin_team(found)


# ===========================================================================================
# Reading a team (as the user, under row-level security)
# ===========================================================================================


def team_id(conn: psycopg.Connection[Any], slug: str) -> uuid.UUID:
    """The team the user is a member of, by its slug (any case); 404 otherwise."""
    row = conn.execute(
        "SELECT id FROM workspace WHERE slug = %s AND kind = 'team'", (slug.strip(),)
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "team_not_found")
    return uuid.UUID(str(row[0]))


MEMBERS = """
SELECT u.id, u.steam_id, u.display_name, m.joined_at, r.id, r.name, r.permissions, rm.role::text,
       CASE WHEN u.id = %(me)s THEN coalesce(wp.share_solo, false) END
FROM membership m
JOIN app_user u ON u.id = m.user_id AND u.deleted_at IS NULL
JOIN workspace_role r ON r.id = m.role_id
LEFT JOIN roster ro ON ro.workspace_id = m.workspace_id
LEFT JOIN roster_member rm
       ON rm.roster_id = ro.id AND rm.steam_id = u.steam_id AND rm.valid_to IS NULL
LEFT JOIN workspace_player wp ON wp.workspace_id = m.workspace_id AND wp.steam_id = u.steam_id
WHERE m.workspace_id = %(team)s
"""
MEMBER_ORDER = """
ORDER BY CASE rm.role WHEN 'starter' THEN 0 WHEN 'standin' THEN 1 ELSE 2 END,
         lower(u.display_name), u.id
"""


def _member(row: tuple[Any, ...]) -> TeamMember:
    return TeamMember(
        user_id=row[0],
        steam_id=str(row[1]),
        display_name=row[2],
        joined_at=row[3],
        role=Role(id=row[4], name=row[5], permissions=list(row[6])),
        roster=row[7],
        share_solo=row[8],
    )


def member_by(
    conn: psycopg.Connection[Any], team: uuid.UUID, me: uuid.UUID, where: str, value: object
) -> TeamMember:
    row = conn.execute(
        f"{MEMBERS} AND {where} = %(value)s", {"me": me, "team": team, "value": value}
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "not_a_member")
    return _member(row)


def read_team(conn: psycopg.Connection[Any], team: uuid.UUID, me: uuid.UUID) -> Team:
    row = conn.execute(
        "SELECT id, name, slug::text, created_at FROM workspace WHERE id = %s", (team,)
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "team_not_found")
    roles = [
        Role(id=r[0], name=r[1], permissions=list(r[2]))
        for r in conn.execute(
            "SELECT id, name, permissions FROM workspace_role WHERE workspace_id = %s "
            "ORDER BY '*' = ANY (permissions) DESC, cardinality(permissions) DESC, name",
            (team,),
        ).fetchall()
    ]
    members = [
        _member(m)
        for m in conn.execute(f"{MEMBERS} {MEMBER_ORDER}", {"me": me, "team": team}).fetchall()
    ]
    mine = next((m.role for m in members if m.user_id == me), None)
    if mine is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "team_not_found")
    return Team(
        id=row[0],
        name=row[1],
        slug=row[2],
        created_at=row[3],
        my_role=mine,
        roles=roles,
        members=members,
    )


@router.get("/teams/{slug}")
def get_team(slug: Slug, conn: ConnDep, user: UserDep) -> Team:
    return read_team(conn, team_id(conn, slug), user)


# ===========================================================================================
# Changing a team (each through its database function)
# ===========================================================================================


@router.patch("/teams/{slug}")
def rename_team(slug: Slug, body: RenameIn, conn: ConnDep, user: UserDep) -> Team:
    team = team_id(conn, slug)
    name = clean_name(body.name)
    with refusals():
        conn.execute("SELECT rename_team(%s, %s)", (team, name))
    return read_team(conn, team, user)


@router.delete("/teams/{slug}", status_code=status.HTTP_202_ACCEPTED)
def delete_team(slug: Slug, conn: ConnDep) -> None:
    """Deletes the team (`team.delete`): its roles, members, roster and invitations. The matches
    stay their players', except those the team sent for itself: the worker deletes them, unless
    they count for a registered user or another source brought them too."""
    team = team_id(conn, slug)
    with refusals():
        conn.execute("SELECT delete_team(%s)", (team,))


@router.patch("/teams/{slug}/members/{user_id}")
def set_member_role(
    slug: Slug, user_id: uuid.UUID, body: MemberRoleIn, conn: ConnDep, user: UserDep
) -> TeamMember:
    team = team_id(conn, slug)
    with refusals():
        conn.execute("SELECT set_member_role(%s, %s, %s)", (team, user_id, body.role_id))
    return member_by(conn, team, user, "u.id", user_id)


@router.delete("/teams/{slug}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(slug: Slug, user_id: uuid.UUID, conn: ConnDep) -> None:
    """Removes a member (`members.manage`), or the user leaves (their own id). They leave the
    roster from today; the matches played together before stay the team's."""
    team = team_id(conn, slug)
    with refusals():
        conn.execute("SELECT remove_member(%s, %s)", (team, user_id))


@router.post("/teams/{slug}/owner")
def transfer_ownership(slug: Slug, body: OwnerIn, conn: ConnDep, user: UserDep) -> Team:
    """The owner hands the team over: the member becomes the owner and takes the owner's place,
    the owner takes the member's former role."""
    team = team_id(conn, slug)
    with refusals():
        conn.execute("SELECT transfer_team_ownership(%s, %s)", (team, body.user_id))
    return read_team(conn, team, user)


# ===========================================================================================
# Invitation links
# ===========================================================================================

INVITATIONS = """
SELECT i.id, i.max_uses, i.uses, i.expires_at, i.created_at, r.id, r.name, r.permissions
FROM team_invitation i JOIN workspace_role r ON r.id = i.role_id
WHERE i.workspace_id = %(team)s
"""


def _invitation(row: tuple[Any, ...], token: str | None = None) -> TeamInvitation:
    return TeamInvitation(
        id=row[0],
        max_uses=row[1],
        uses=row[2],
        expires_at=row[3],
        created_at=row[4],
        role=Role(id=row[5], name=row[6], permissions=list(row[7])),
        token=token,
    )


def _may_manage(conn: psycopg.Connection[Any], team: uuid.UUID) -> None:
    row = conn.execute("SELECT has_permission(%s, 'members.manage')", (team,)).fetchone()
    if row is None or not row[0]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden")


@router.get("/teams/{slug}/invitations")
def list_invitations(slug: Slug, conn: ConnDep) -> list[TeamInvitation]:
    """The links still usable (not expired, used up or revoked, and their creator still able to
    give their role), newest first."""
    team = team_id(conn, slug)
    _may_manage(conn, team)
    rows = conn.execute(
        f"""{INVITATIONS} AND i.id IN (SELECT live_team_invitations(%(team)s))
            ORDER BY i.created_at DESC, i.id""",
        {"team": team},
    ).fetchall()
    return [_invitation(row) for row in rows]


@router.post("/teams/{slug}/invitations", status_code=status.HTTP_201_CREATED)
def create_invitation(
    slug: Slug, body: InvitationIn, conn: ConnDep, response: Response
) -> TeamInvitation:
    """A link valid 7 days for `max_uses` people (1 to 20), with a role no stronger than the
    caller's and never the owner's. Its token is in this answer only (never cached). It stops
    working if its creator leaves or no longer manages members with a role covering it."""
    response.headers["Cache-Control"] = "no-store"
    team = team_id(conn, slug)
    if not 1 <= body.max_uses <= 20:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {"field": "max_uses"})
    invitation = uuid.uuid4()
    token = secrets.token_urlsafe(32)
    with refusals():
        conn.execute(
            "SELECT create_team_invitation(%s, %s, %s, %s, %s)",
            (team, invitation, token_hash(token), body.role_id, body.max_uses),
        )
    row = conn.execute(
        f"{INVITATIONS} AND i.id = %(id)s", {"team": team, "id": invitation}
    ).fetchone()
    assert row is not None
    return _invitation(row, token)


@router.delete("/teams/{slug}/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invitation(slug: Slug, invitation_id: uuid.UUID, conn: ConnDep) -> None:
    team = team_id(conn, slug)
    with refusals():
        conn.execute("SELECT revoke_team_invitation(%s, %s)", (team, invitation_id))


def valid_token(token: str) -> str:
    if not TOKEN.match(token):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "invitation_invalid")
    return token


@router.get("/team-invitations/{token}")
def preview_invitation(token: str, db: DatabaseDep) -> InvitationPreview:
    """What a link shows before anyone signs in: the team's name, the role and the end date,
    nothing about its members. It changes nothing; 404 `invitation_invalid` for a link that is
    unknown, expired, used up or revoked alike."""
    with db.transaction(None) as conn:
        row = conn.execute(
            "SELECT team_name, role, expires_at FROM team_invitation_preview(%s)",
            (token_hash(valid_token(token)),),
        ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "invitation_invalid")
    return InvitationPreview(team_name=row[0], role=row[1], expires_at=row[2])


@router.post("/team-invitations/{token}/accept")
def accept_invitation(token: str, conn: ConnDep, settings: SettingsDep) -> Joined:
    """The signed-in user joins the team, once they agreed to the current consent text (403
    `consent_required`). 409 `already_member`."""
    with refusals():
        row = conn.execute(
            "SELECT accept_team_invitation(%s, %s)",
            (token_hash(valid_token(token)), settings.consent_version),
        ).fetchone()
    assert row is not None
    return Joined(slug=row[0])


# ===========================================================================================
# Roster and sharing
# ===========================================================================================


@router.put("/teams/{slug}/roster/{steam_id}")
def set_roster_member(
    slug: Slug, steam_id: SteamId, body: RosterIn, conn: ConnDep, user: UserDep
) -> TeamMember:
    """Puts a member on the roster as a starter or a stand-in (`roster.edit`); only members can
    be on it (409 `not_a_member`)."""
    team = team_id(conn, slug)
    steam = int(steam_id)
    if steam > STEAM_MAX:
        raise HTTPException(status.HTTP_409_CONFLICT, "not_a_member")
    with refusals():
        conn.execute("SELECT set_roster_member(%s, %s, %s::roster_role)", (team, steam, body.role))
    return member_by(conn, team, user, "u.steam_id", steam)


@router.delete("/teams/{slug}/roster/{steam_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_roster_member(slug: Slug, steam_id: SteamId, conn: ConnDep) -> None:
    """Takes a player off the roster from today; who was on it before stays recorded."""
    team = team_id(conn, slug)
    if int(steam_id) > STEAM_MAX:
        return  # nobody is on the roster under it
    with refusals():
        conn.execute("SELECT remove_roster_member(%s, %s)", (team, int(steam_id)))


@router.put("/teams/{slug}/share-solo", status_code=status.HTTP_204_NO_CONTENT)
def set_share_solo(slug: Slug, body: ShareIn, conn: ConnDep) -> None:
    """The user's own choice to share their solo matches with this team (off by default)."""
    team = team_id(conn, slug)
    with refusals():
        conn.execute("SELECT set_my_share_solo(%s, %s)", (team, body.share))
