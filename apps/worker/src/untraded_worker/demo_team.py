# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The demo account's team: `untraded-worker import-demo <demo> --team <directory>` loads what
`untraded demo team` wrote (`team.json` and the team's matches) after the demo's own matches.

- The team's people are invented accounts (fake SteamIDs, which no Steam account can sign in
  with), invited and consenting to the analysis only, as the demo user is; the demo user owns
  the team, so it sees everything, and stays read-only like the whole demo (the API refuses its
  writes).
- The team is created as an admin creates one (`create_team`), with its members, their roles and
  its roster. The roster starts before the first match: a roster added today would not reach
  matches played before (`refresh_access`).
- A match sent for the team is an upload of the team's own source (`workspace_match.reason =
  'team'`), with who sent it: it counts for nobody's account. A Premier match is an upload of
  one of its players, which the team sees through its roster (3 of them on the same side).
- The review is written through the database's own functions (`add_review_comment`...), as its
  authors, so it passes the checks the site's writes pass.

Running the import again skips what exists: the matches (by their id), the team (by its slug,
when the demo user owns it), the members, the comments (by their text), the playlists (by their
name). `untraded-worker remove-demo-team` deletes the team and erases its invented members: the
demo user, its owner, could not be erased before."""

from __future__ import annotations

import datetime as dt
import json
import logging
import uuid
from pathlib import Path
from typing import Any

import polars as pl
import psycopg

from untraded.demo import FAKE_STEAM_BASE, REAL_LOWEST
from untraded.fixtures import PLAYER_COLUMNS
from untraded.parsing import CanonicalMatch
from untraded_worker.demo import Source, ensure_user, import_match
from untraded_worker.store import LocalStore

log = logging.getLogger("untraded.worker")

ROLES = {"coach": "coach", "player": "player", "viewer": "viewer"}
"""A person's role in `team.json` to the role `create_team` made (the owner is the demo user)."""
ROSTER_BEFORE = dt.timedelta(days=14)
RECEIVED_AFTER = dt.timedelta(hours=2)


def _fake(steam_id: Any) -> int:
    value = int(steam_id)
    if not FAKE_STEAM_BASE < value < REAL_LOWEST:
        raise ValueError(f"team.json names a SteamID outside the demo's fake range: {value}")
    return value


def _match_uuid(match_id: str) -> uuid.UUID:
    """A match's upload id, drawn from its id (a sha256): the same at every import."""
    if len(match_id) != 64 or not match_id.isalnum():
        raise ValueError(f"unexpected match id in team.json: {match_id!r}")
    return uuid.UUID(match_id[:32])


def ensure_team(conn: psycopg.Connection[Any], name: str, slug: str, owner_steam: int) -> uuid.UUID:
    """The demo's team, created on the first import; a team of that slug that the demo user does
    not own is someone else's, and stops the import."""
    found = conn.execute(
        "SELECT id FROM workspace WHERE kind = 'team' AND slug = %s", (slug,)
    ).fetchone()
    if found is None:
        row = conn.execute("SELECT create_team(%s, %s, %s)", (name, slug, owner_steam)).fetchone()
        assert row is not None
        return uuid.UUID(str(row[0]))
    team = uuid.UUID(str(found[0]))
    owned = conn.execute(
        "SELECT 1 FROM membership m JOIN workspace_role r ON r.id = m.role_id "
        "JOIN app_user u ON u.id = m.user_id "
        "WHERE m.workspace_id = %s AND u.steam_id = %s AND '*' = ANY (r.permissions)",
        (team, owner_steam),
    ).fetchone()
    if owned is None:
        raise RuntimeError(f"the team {slug!r} exists and the demo user does not own it")
    return team


def _upload_source(conn: psycopg.Connection[Any], column: str, owner: uuid.UUID) -> uuid.UUID:
    """The upload source of a workspace or a user (`column`), created when missing."""
    if column not in ("workspace_id", "user_id"):
        raise ValueError(f"no upload source by {column!r}")
    found = conn.execute(
        f"SELECT id FROM ingest_source WHERE {column} = %s AND kind = 'upload' "
        "ORDER BY created_at LIMIT 1",
        (owner,),
    ).fetchone()
    if found is None:
        found = conn.execute(
            f"INSERT INTO ingest_source ({column}, kind) VALUES (%s, 'upload') RETURNING id",
            (owner,),
        ).fetchone()
    assert found is not None
    return uuid.UUID(str(found[0]))


def _as(conn: psycopg.Connection[Any], user: uuid.UUID) -> None:
    """The rest of the transaction runs as `user` for the database's checks (`has_permission`)."""
    conn.execute("SELECT set_config('app.user_id', %s, true)", (str(user),))


def import_demo_team(
    conn: psycopg.Connection[Any],
    store: LocalStore,
    root: Path,
    *,
    owner_steam_id: int,
    consent_version: str,
) -> int:
    """Loads the team of `root/team.json` for the demo user (`owner_steam_id`, imported first);
    returns how many of its matches were loaded now."""
    manifest = json.loads((root / "team.json").read_text(encoding="utf-8"))
    people = manifest["people"]
    entries = manifest["matches"]
    if not entries:
        raise ValueError("team.json lists no match")
    starts = [dt.datetime.fromisoformat(str(e["played_at"])) for e in entries]
    # Everything checked before anything is written.
    known = {_fake(p["steam_id"]) for p in people}
    for entry in entries:
        _match_uuid(str(entry["match_id"]))
        if entry["via"] not in ("team", "roster"):
            raise ValueError(f"unexpected way in for a match in team.json: {entry['via']!r}")
        if _fake(entry["sent_by"]) not in known:
            raise ValueError("a match of team.json was sent by someone not in the team")
        _only_fake_players(root / "matches" / str(entry["match_id"]))

    with conn.transaction():
        owner = conn.execute(
            "SELECT id FROM app_user WHERE steam_id = %s AND deleted_at IS NULL",
            (owner_steam_id,),
        ).fetchone()
        if owner is None:
            raise RuntimeError("the demo user is missing: import the demo's own matches first")
        users = {owner_steam_id: uuid.UUID(str(owner[0]))}
        for person in people:
            steam = _fake(person["steam_id"])
            if person["role"] == "owner":
                if steam != owner_steam_id:
                    raise ValueError("team.json's owner is not the demo user")
                continue
            if person["role"] not in ROLES:
                raise ValueError(f"unexpected role in team.json: {person['role']!r}")
            users[steam] = ensure_user(conn, steam, str(person["name"]), consent_version)
        team = ensure_team(
            conn, str(manifest["team"]["name"]), str(manifest["team"]["slug"]), owner_steam_id
        )
        roles = dict(
            conn.execute(
                "SELECT name, id FROM workspace_role WHERE workspace_id = %s", (team,)
            ).fetchall()
        )
        roster_row = conn.execute(
            "SELECT id FROM roster WHERE workspace_id = %s", (team,)
        ).fetchone()
        assert roster_row is not None
        since = (min(starts) - ROSTER_BEFORE).date()
        for person in people:
            steam = int(person["steam_id"])
            if person["role"] != "owner":
                conn.execute(
                    "INSERT INTO membership (workspace_id, user_id, role_id) VALUES (%s, %s, %s) "
                    "ON CONFLICT (workspace_id, user_id) DO NOTHING",
                    (team, users[steam], roles[ROLES[person["role"]]]),
                )
            conn.execute("SELECT follow_member(%s, %s)", (team, users[steam]))
            if person.get("roster") is not None:
                conn.execute(
                    "INSERT INTO roster_member (roster_id, steam_id, role, valid_from) "
                    "SELECT %(roster)s, %(steam)s, %(role)s::roster_role, %(since)s "
                    "WHERE NOT EXISTS (SELECT 1 FROM roster_member WHERE roster_id = %(roster)s "
                    "AND steam_id = %(steam)s AND valid_to IS NULL)",
                    {
                        "roster": roster_row[0],
                        "steam": steam,
                        "role": person["roster"],
                        "since": since,
                    },
                )
        team_source = _upload_source(conn, "workspace_id", team)

    done = 0
    for entry, start in zip(entries, starts, strict=True):
        match_id = str(entry["match_id"])
        sender = users[_fake(entry["sent_by"])]
        received = start + RECEIVED_AFTER
        external = str(_match_uuid(match_id))
        if entry["via"] == "team":
            source = Source(team_source, external, received, sender)
        elif entry["via"] == "roster":
            with conn.transaction():
                personal = _upload_source(conn, "user_id", sender)
            source = Source(personal, external, received)
        else:
            raise ValueError(f"unexpected way in for a match in team.json: {entry['via']!r}")
        loaded = import_match(conn, store, root / "matches" / match_id, entry, source)
        if loaded is not None:
            log.info("demo team match %s loaded as %s", match_id, loaded)
            done += 1

    # Everyone in these matches replays a real player: none of them goes into the references.
    conn.execute(
        "UPDATE player SET benchmark_opt_out = true WHERE steam_id IN ("
        "SELECT mp.steam_id FROM match_player mp JOIN match m ON m.id = mp.match_id "
        "WHERE m.sha256 = ANY (%s))",
        ([str(e["match_id"]) for e in entries],),
    )
    _review(conn, team, manifest, users)
    return done


def _only_fake_players(directory: Path) -> None:
    """Raises unless every steamid of the match's tables is a demo one (or 0, the world): a
    directory of real matches is never published through the demo."""
    tables = CanonicalMatch.read(directory).tables()
    for table, columns in PLAYER_COLUMNS.items():
        for column in columns:
            values = tables[table][column]
            if values.dtype == pl.List:
                values = values.explode()
            for steam in values.drop_nulls().unique().to_list():
                if steam != 0:
                    _fake(steam)


def _review(
    conn: psycopg.Connection[Any],
    team: uuid.UUID,
    manifest: dict[str, Any],
    users: dict[int, uuid.UUID],
) -> None:
    """The team's comments, tags and playlists, written as their authors (the tags and the
    playlists as the coach, who holds `review.manage`)."""
    ids = [str(m["match_id"]) for m in manifest["matches"]]
    matches = {
        str(sha): uuid.UUID(str(i))
        for sha, i in conn.execute(
            "SELECT sha256, id FROM match WHERE sha256 = ANY (%s)", (ids,)
        ).fetchall()
    }
    coach = next(users[int(p["steam_id"])] for p in manifest["people"] if p["role"] == "coach")
    for c in manifest["comments"]:
        match = matches[str(c["match_id"])]
        with conn.transaction():
            known = conn.execute(
                "SELECT 1 FROM review_comment WHERE workspace_id = %s AND match_id = %s "
                "AND round = %s AND body = %s",
                (team, match, c["round"], c["body"]),
            ).fetchone()
            if known is not None:
                continue
            _as(conn, users[_fake(c["author"])])
            row = conn.execute(
                "SELECT add_review_comment(%s, %s, %s, %s, %s)",
                (team, match, c["round"], c["tick"], c["body"]),
            ).fetchone()
            assert row is not None
            conn.execute(
                "UPDATE review_comment SET created_at = %s WHERE id = %s",
                (dt.datetime.fromisoformat(str(c["at"])), row[0]),
            )
    with conn.transaction():
        _as(conn, coach)
        for t in manifest["tags"]:
            conn.execute(
                "SELECT set_review_tags(%s, %s, %s, %s)",
                (team, matches[str(t["match_id"])], t["round"], list(t["labels"])),
            )
        for p in manifest["playlists"]:
            found = conn.execute(
                "SELECT id FROM review_playlist WHERE workspace_id = %s AND name = %s",
                (team, p["name"]),
            ).fetchone()
            if found is None:
                found = conn.execute(
                    "SELECT create_review_playlist(%s, %s, %s)",
                    (team, p["name"], p["description"]),
                ).fetchone()
            assert found is not None
            for r in p["rounds"]:
                conn.execute(
                    "SELECT add_review_playlist_round(%s, %s, %s, %s)",
                    (team, found[0], matches[str(r["match_id"])], r["round"]),
                )


def remove_demo_team(conn: psycopg.Connection[Any], *, owner_steam_id: int, slug: str) -> int:
    """Deletes the demo's team as its owner (`delete_team`: the matches sent for it go with it,
    `drop_team_matches`), then erases its invented members (`request_erasure`: their accounts
    and the matches that counted only for them). The demo user owns the team, which would
    refuse its own erasure: this comes first. Returns how many members are erased; 0 when
    there is no such team."""
    with conn.transaction():
        found = conn.execute(
            "SELECT id FROM workspace WHERE kind = 'team' AND slug = %s", (slug,)
        ).fetchone()
        if found is None:
            return 0
        team = ensure_team(conn, "", slug, owner_steam_id)  # raises unless the demo owns it
        owner = conn.execute(
            "SELECT id FROM app_user WHERE steam_id = %s AND deleted_at IS NULL", (owner_steam_id,)
        ).fetchone()
        assert owner is not None
        members = [
            int(steam)
            for (steam,) in conn.execute(
                "SELECT u.steam_id FROM membership m JOIN app_user u ON u.id = m.user_id "
                "WHERE m.workspace_id = %s AND u.steam_id <> %s ORDER BY u.steam_id",
                (team, owner_steam_id),
            ).fetchall()
        ]
        _as(conn, uuid.UUID(str(owner[0])))
        conn.execute("SELECT delete_team(%s)", (team,))
        erased = 0
        for steam in members:
            if not FAKE_STEAM_BASE < steam < REAL_LOWEST:
                log.warning("member %s of the demo team is not a demo account: kept", steam)
                continue
            conn.execute("SELECT request_erasure(%s)", (steam,))
            erased += 1
    return erased
