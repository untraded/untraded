# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""A team's review: comments on a round, tags on a round, and playlists of rounds.

Every row is a team's and a match's (migration 0019). Row-level security shows a member the
team's review of a match only when they may read the team's matches (`matches.read`) and the TEAM
sees that match: a scrim between two teams on Untraded is one match, and neither reads the other's
review. The routes below check membership (404 `team_not_found`) and `matches.read` (403
`forbidden`) first, as the team's match routes do, then read through those policies.

Every write is a database function that checks the caller's permission itself (`review.comment`,
`review.manage`) and the limits, and raises a stable code (`refusals`). The texts are stored and
returned as plain text: the site never renders them as HTML.

A comment's author is the name it was signed with, kept on the comment, so that it stays readable
after the author leaves the team; it is null once the author's account is erased ("former
member" on the site). Who wrote it is never returned, only whether the user did (`mine`).
"""

# No `from __future__ import annotations`: FastAPI reads the dependencies from the annotations.

import datetime as dt
import uuid
from typing import Annotated, Any, Literal

import psycopg
from fastapi import APIRouter, HTTPException, Path, status
from pydantic import BaseModel, Field

from untraded_api.deps import ConnDep, refusals
from untraded_api.team_matches import OUR_TEAM, readable_team
from untraded_api.teams import Slug

router = APIRouter(tags=["teams"])

RoundNumber = Annotated[int, Path(ge=1, le=99)]
Side = Literal["A", "B"]

# Bounds on what a request may carry: the database checks the real limits (2,000 characters for a
# comment, 32 for a tag, 80 for a name, 280 for a description, 10 tags, 100 rounds).
BODY_MAX = 10_000
LINE_MAX = 1_000
TAGS_MAX = 50
ORDER_MAX = 200


class ReviewComment(BaseModel):
    id: uuid.UUID
    match_id: uuid.UUID
    round: int
    tick: int | None
    """The instant of the round, in the demo's ticks."""
    body: str
    """Plain text, line breaks included."""
    author_name: str | None
    """The name the comment is signed with; null once its author's account is erased."""
    mine: bool
    can_edit: bool
    can_delete: bool
    created_at: dt.datetime
    edited_at: dt.datetime | None


class RoundTags(BaseModel):
    round: int
    tags: list[str]


class PlaylistRef(BaseModel):
    id: uuid.UUID
    name: str
    rounds: list[int]
    """The rounds of this match already in the playlist."""


class ReviewPermissions(BaseModel):
    comment: bool
    manage: bool


class MatchReview(BaseModel):
    comments: list[ReviewComment]
    tags: list[RoundTags]
    playlists: list[PlaylistRef]
    permissions: ReviewPermissions


class TeamTag(BaseModel):
    label: str
    rounds: int


class PlaylistSummary(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    rounds: int
    """The rounds of matches the team sees."""
    created_at: dt.datetime
    updated_at: dt.datetime


class PlaylistRound(BaseModel):
    match_id: uuid.UUID
    round: int
    map: str | None
    played_at: dt.datetime | None
    mode: str
    score_a: int | None
    score_b: int | None
    our_team: Side | None
    winner_team: Side | None
    tags: list[str]
    comments: int


class Playlist(PlaylistSummary):
    items: list[PlaylistRound]
    permissions: ReviewPermissions


class CommentIn(BaseModel):
    body: str = Field(max_length=BODY_MAX)
    tick: int | None = Field(default=None, ge=0, le=2**31 - 1)


class CommentEditIn(BaseModel):
    body: str = Field(max_length=BODY_MAX)


class TagsIn(BaseModel):
    tags: list[Annotated[str, Field(max_length=LINE_MAX)]] = Field(max_length=TAGS_MAX)


class PlaylistIn(BaseModel):
    name: str = Field(max_length=LINE_MAX)
    description: str = Field(default="", max_length=LINE_MAX)


class PlaylistEditIn(BaseModel):
    name: str | None = Field(default=None, max_length=LINE_MAX)
    description: str | None = Field(default=None, max_length=LINE_MAX)


class RoundRef(BaseModel):
    match_id: uuid.UUID
    round: int = Field(ge=1, le=99)


class OrderIn(BaseModel):
    rounds: list[RoundRef] = Field(max_length=ORDER_MAX)


# ===========================================================================================
# Reading
# ===========================================================================================


def permissions(conn: psycopg.Connection[Any], team: uuid.UUID) -> ReviewPermissions:
    row = conn.execute(
        "SELECT has_permission(%(t)s, 'review.comment'), has_permission(%(t)s, 'review.manage')",
        {"t": team},
    ).fetchone()
    assert row is not None
    return ReviewPermissions(comment=row[0], manage=row[1])


def team_match(conn: psycopg.Connection[Any], team: uuid.UUID, match_id: uuid.UUID) -> None:
    """404 `match_not_found` unless the team sees the match (whoever else may)."""
    row = conn.execute(
        "SELECT 1 FROM workspace_match WHERE workspace_id = %s AND match_id = %s",
        (team, match_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "match_not_found")


COMMENTS = """
SELECT c.id, c.match_id, c.round, c.tick, c.body,
       CASE WHEN c.author_id IS NOT NULL THEN c.author_name END,
       coalesce(c.author_id = current_app_user(), false),
       c.created_at, c.edited_at
FROM review_comment c
"""
COMMENT_ORDER = "ORDER BY c.round, c.tick NULLS FIRST, c.created_at, c.id"


def _comment(row: tuple[Any, ...], allowed: ReviewPermissions) -> ReviewComment:
    mine = bool(row[6])
    return ReviewComment(
        id=row[0],
        match_id=row[1],
        round=row[2],
        tick=row[3],
        body=row[4],
        author_name=row[5],
        mine=mine,
        can_edit=mine and allowed.comment,
        can_delete=(mine and allowed.comment) or allowed.manage,
        created_at=row[7],
        edited_at=row[8],
    )


def read_comment(
    conn: psycopg.Connection[Any], team: uuid.UUID, comment_id: uuid.UUID
) -> ReviewComment:
    row = conn.execute(
        f"{COMMENTS} WHERE c.id = %s AND c.workspace_id = %s", (comment_id, team)
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "comment_not_found")
    return _comment(row, permissions(conn, team))


def round_tags(
    conn: psycopg.Connection[Any], team: uuid.UUID, match_id: uuid.UUID
) -> list[RoundTags]:
    rows = conn.execute(
        """
        SELECT round, array_agg(label ORDER BY lower(label), label)
        FROM review_tag WHERE workspace_id = %s AND match_id = %s
        GROUP BY round ORDER BY round
        """,
        (team, match_id),
    ).fetchall()
    return [RoundTags(round=r[0], tags=list(r[1])) for r in rows]


@router.get("/teams/{slug}/matches/{match_id}/review")
def match_review(slug: Slug, match_id: uuid.UUID, conn: ConnDep) -> MatchReview:
    """The team's review of a match it sees: comments, tags, and its playlists with the rounds of
    this match in them."""
    team = readable_team(conn, slug)
    team_match(conn, team, match_id)
    allowed = permissions(conn, team)
    comments = conn.execute(
        f"{COMMENTS} WHERE c.workspace_id = %s AND c.match_id = %s {COMMENT_ORDER}",
        (team, match_id),
    ).fetchall()
    playlists = conn.execute(
        """
        SELECT p.id, p.name,
               coalesce(array_agg(pr.round ORDER BY pr.round)
                        FILTER (WHERE pr.round IS NOT NULL), '{}')
        FROM review_playlist p
        LEFT JOIN review_playlist_round pr ON pr.playlist_id = p.id AND pr.match_id = %s
        WHERE p.workspace_id = %s
        GROUP BY p.id ORDER BY lower(p.name), p.id
        """,
        (match_id, team),
    ).fetchall()
    return MatchReview(
        comments=[_comment(row, allowed) for row in comments],
        tags=round_tags(conn, team, match_id),
        playlists=[PlaylistRef(id=p[0], name=p[1], rounds=list(p[2])) for p in playlists],
        permissions=allowed,
    )


@router.get("/teams/{slug}/review/tags")
def team_tags(slug: Slug, conn: ConnDep) -> list[TeamTag]:
    """The team's tags on the matches it sees, most used first (for suggestions), each in its
    most used case."""
    team = readable_team(conn, slug)
    rows = conn.execute(
        """
        SELECT mode() WITHIN GROUP (ORDER BY label), count(*)
        FROM review_tag WHERE workspace_id = %s
        GROUP BY lower(label) ORDER BY count(*) DESC, lower(label)
        """,
        (team,),
    ).fetchall()
    return [TeamTag(label=r[0], rounds=r[1]) for r in rows]


PLAYLISTS = """
SELECT p.id, p.name, p.description,
       (SELECT count(*) FROM review_playlist_round pr WHERE pr.playlist_id = p.id),
       p.created_at, p.updated_at
FROM review_playlist p
"""


def _summary(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "id": row[0],
        "name": row[1],
        "description": row[2],
        "rounds": row[3],
        "created_at": row[4],
        "updated_at": row[5],
    }


@router.get("/teams/{slug}/playlists")
def list_playlists(slug: Slug, conn: ConnDep) -> list[PlaylistSummary]:
    team = readable_team(conn, slug)
    rows = conn.execute(
        f"{PLAYLISTS} WHERE p.workspace_id = %s ORDER BY lower(p.name), p.id", (team,)
    ).fetchall()
    return [PlaylistSummary(**_summary(row)) for row in rows]


ITEMS = f"""
SELECT pr.match_id, pr.round, m.map, m.played_at, m.mode::text, m.score_a, m.score_b,
       ours.team::text, r.winner_team::text,
       coalesce((SELECT array_agg(t.label ORDER BY lower(t.label), t.label) FROM review_tag t
                 WHERE t.workspace_id = %(team)s AND t.match_id = pr.match_id
                   AND t.round = pr.round), '{{}}'),
       (SELECT count(*) FROM review_comment c
        WHERE c.workspace_id = %(team)s AND c.match_id = pr.match_id AND c.round = pr.round)
FROM review_playlist_round pr
JOIN match m ON m.id = pr.match_id
LEFT JOIN round r ON r.match_id = pr.match_id AND r.round = pr.round
CROSS JOIN LATERAL ({OUR_TEAM}) ours
WHERE pr.playlist_id = %(playlist)s
ORDER BY pr.seq, pr.added_at, pr.match_id, pr.round
"""
"""A playlist's rounds the team sees (row-level security leaves out the others), in its order."""


def read_playlist(conn: psycopg.Connection[Any], team: uuid.UUID, playlist: uuid.UUID) -> Playlist:
    row = conn.execute(
        f"{PLAYLISTS} WHERE p.id = %s AND p.workspace_id = %s", (playlist, team)
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "playlist_not_found")
    items = conn.execute(ITEMS, {"team": team, "playlist": playlist}).fetchall()
    return Playlist(
        **_summary(row),
        items=[
            PlaylistRound(
                match_id=i[0],
                round=i[1],
                map=i[2],
                played_at=i[3],
                mode=i[4],
                score_a=i[5],
                score_b=i[6],
                our_team=i[7],
                winner_team=i[8],
                tags=list(i[9]),
                comments=i[10],
            )
            for i in items
        ],
        permissions=permissions(conn, team),
    )


@router.get("/teams/{slug}/playlists/{playlist_id}")
def get_playlist(slug: Slug, playlist_id: uuid.UUID, conn: ConnDep) -> Playlist:
    team = readable_team(conn, slug)
    return read_playlist(conn, team, playlist_id)


# ===========================================================================================
# Writing (each through its database function)
# ===========================================================================================


@router.post(
    "/teams/{slug}/matches/{match_id}/rounds/{round_number}/comments",
    status_code=status.HTTP_201_CREATED,
)
def add_comment(
    slug: Slug, match_id: uuid.UUID, round_number: RoundNumber, body: CommentIn, conn: ConnDep
) -> ReviewComment:
    """A comment on a round (`review.comment`), at an instant of it when `tick` is given."""
    team = readable_team(conn, slug)
    with refusals():
        row = conn.execute(
            "SELECT add_review_comment(%s, %s, %s, %s, %s)",
            (team, match_id, round_number, body.tick, body.body),
        ).fetchone()
    assert row is not None
    return read_comment(conn, team, row[0])


@router.patch("/teams/{slug}/comments/{comment_id}")
def edit_comment(
    slug: Slug, comment_id: uuid.UUID, body: CommentEditIn, conn: ConnDep
) -> ReviewComment:
    """Its author changes a comment's text, while they may comment."""
    team = readable_team(conn, slug)
    with refusals():
        conn.execute("SELECT edit_review_comment(%s, %s, %s)", (team, comment_id, body.body))
    return read_comment(conn, team, comment_id)


@router.delete("/teams/{slug}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(slug: Slug, comment_id: uuid.UUID, conn: ConnDep) -> None:
    """Its author deletes a comment, or a member with `review.manage` does."""
    team = readable_team(conn, slug)
    with refusals():
        conn.execute("SELECT delete_review_comment(%s, %s)", (team, comment_id))


@router.put("/teams/{slug}/matches/{match_id}/rounds/{round_number}/tags")
def set_tags(
    slug: Slug, match_id: uuid.UUID, round_number: RoundNumber, body: TagsIn, conn: ConnDep
) -> RoundTags:
    """The round's tags become `tags` (`review.manage`); `[]` removes them all."""
    team = readable_team(conn, slug)
    with refusals():
        conn.execute(
            "SELECT set_review_tags(%s, %s, %s, %s::text[])",
            (team, match_id, round_number, body.tags),
        )
    found = next((t for t in round_tags(conn, team, match_id) if t.round == round_number), None)
    return found or RoundTags(round=round_number, tags=[])


@router.post("/teams/{slug}/playlists", status_code=status.HTTP_201_CREATED)
def create_playlist(slug: Slug, body: PlaylistIn, conn: ConnDep) -> Playlist:
    team = readable_team(conn, slug)
    with refusals():
        row = conn.execute(
            "SELECT create_review_playlist(%s, %s, %s)", (team, body.name, body.description)
        ).fetchone()
    assert row is not None
    return read_playlist(conn, team, row[0])


@router.patch("/teams/{slug}/playlists/{playlist_id}")
def update_playlist(
    slug: Slug, playlist_id: uuid.UUID, body: PlaylistEditIn, conn: ConnDep
) -> Playlist:
    team = readable_team(conn, slug)
    with refusals():
        conn.execute(
            "SELECT update_review_playlist(%s, %s, %s, %s)",
            (team, playlist_id, body.name, body.description),
        )
    return read_playlist(conn, team, playlist_id)


@router.delete("/teams/{slug}/playlists/{playlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_playlist(slug: Slug, playlist_id: uuid.UUID, conn: ConnDep) -> None:
    team = readable_team(conn, slug)
    with refusals():
        conn.execute("SELECT delete_review_playlist(%s, %s)", (team, playlist_id))


@router.post("/teams/{slug}/playlists/{playlist_id}/rounds")
def add_playlist_round(
    slug: Slug, playlist_id: uuid.UUID, body: RoundRef, conn: ConnDep
) -> Playlist:
    """Adds a round at the end of the playlist (nothing changes when it is in it already)."""
    team = readable_team(conn, slug)
    with refusals():
        conn.execute(
            "SELECT add_review_playlist_round(%s, %s, %s, %s)",
            (team, playlist_id, body.match_id, body.round),
        )
    return read_playlist(conn, team, playlist_id)


@router.delete(
    "/teams/{slug}/playlists/{playlist_id}/rounds/{match_id}/{round_number}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_playlist_round(
    slug: Slug,
    playlist_id: uuid.UUID,
    match_id: uuid.UUID,
    round_number: RoundNumber,
    conn: ConnDep,
) -> None:
    team = readable_team(conn, slug)
    with refusals():
        conn.execute(
            "SELECT remove_review_playlist_round(%s, %s, %s, %s)",
            (team, playlist_id, match_id, round_number),
        )


@router.put("/teams/{slug}/playlists/{playlist_id}/order")
def order_playlist(slug: Slug, playlist_id: uuid.UUID, body: OrderIn, conn: ConnDep) -> Playlist:
    """Puts the playlist's rounds in this order: exactly the rounds of it the team sees."""
    team = readable_team(conn, slug)
    with refusals():
        conn.execute(
            "SELECT order_review_playlist(%s, %s, %s::uuid[], %s::integer[])",
            (
                team,
                playlist_id,
                [r.match_id for r in body.rounds],
                [r.round for r in body.rounds],
            ),
        )
    return read_playlist(conn, team, playlist_id)
