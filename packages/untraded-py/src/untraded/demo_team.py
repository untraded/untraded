# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""A team for the demo account, made of the demo's own matches.

The demo's protagonist plays mostly without a fixed roster: too few of its matches have the same
three teammates for a team to see them. So the team's matches are a variant of the demo's
matches (`untraded.demo`, already anonymized): in each one, the protagonist's teammates become
the same roster identities (fake SteamIDs above `TEAM_BASE`, invented names, none of the solo
demo's), and the opponents get fresh fake identities in every match. The rounds, shots, kills,
damage and grenades are the real match's: the team's statistics are computed by the worker,
never invented. Every match maps different people onto the same identities, and the opponents
onto new ones: the team's view follows nobody from one match to the next (a variant can still be
paired with its solo match, whose rounds it shares, so it follows nobody further than the solo
demo does).

Each variant has its own id (the sha256 of the demo's id, salted otherwise) and is dated the day
before its solo match: it does not double the demo's matches. Most are sent for the team (scrims,
FACEIT, ESEA), they count for the team alone; the Premier ones were sent by one of its players,
and the team sees them because three of its roster played them on the same side.

`team.json` describes the rest for `untraded-worker import-demo --team`: the team, its members
and roles, which match came how, and a review (comments of the coach on rounds chosen for what
happened in them, tags, two playlists). The texts are written for the demo, in English (a comment
has one text, whatever the reader's language).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import polars as pl

from untraded.demo import FAKE_STEAM_BASE, PROTAGONIST, PROTAGONIST_NAME, DemoMatch
from untraded.fixtures import generic_knives, replace_players
from untraded.parsing.validate import validate

Tables = dict[str, pl.DataFrame]

TEAM_NAME = "Demo Esports"
TEAM_SLUG = "demo-esports"
SALT = "untraded-demo-team"
TEAM_BASE = FAKE_STEAM_BASE + 50_000
"""The team's people and opponents: far above the solo demo's fake ids, below any real one."""
OPPONENT_BASE = TEAM_BASE + 1_000
OPPONENT_SLOTS = 20
"""Fake ids per match for its opponents (a match with substitutes has more than five)."""
SHIFT = dt.timedelta(days=1)
"""A variant is played the day before its solo match: the demo's sessions are every other day."""

Role = Literal["owner", "coach", "player", "viewer"]
RosterRole = Literal["starter", "standin"]
Via = Literal["team", "roster"]


@dataclass(frozen=True)
class Person:
    steam_id: int
    name: str
    role: Role
    roster: RosterRole | None = None


OWNER = Person(PROTAGONIST, PROTAGONIST_NAME, "owner", "starter")
STARTERS = (
    Person(TEAM_BASE + 1, "Vantage", "player", "starter"),
    Person(TEAM_BASE + 2, "Ironside", "player", "starter"),
    Person(TEAM_BASE + 3, "Kilo", "player", "starter"),
    Person(TEAM_BASE + 4, "Mako", "player", "starter"),
)
STANDINS = (
    Person(TEAM_BASE + 5, "Rift", "player", "standin"),
    Person(TEAM_BASE + 6, "Saber", "player", "standin"),
    Person(TEAM_BASE + 7, "Tamsin", "player", "standin"),
)
COACH = Person(TEAM_BASE + 20, "Marek", "coach")
ANALYST = Person(TEAM_BASE + 21, "Ines", "viewer")
PEOPLE = (OWNER, *STARTERS, *STANDINS, COACH, ANALYST)
OPPONENT_NAMES = (
    "Axiom", "Blitz", "Cobalt", "Dynamo", "Fathom", "Gambit", "Havoc", "Impulse", "Jackal",
    "Kinetic", "Lynx", "Mantis", "Nomad", "Outlaw", "Phantom", "Quasar", "Raptor", "Static",
    "Torque", "Vortex", "Warden", "Xenon", "Yukon", "Zenith", "Apex", "Bandit", "Comet",
    "Delta", "Falcon", "Gecko", "Hydra", "Ion", "Jolt", "Kraken", "Lancer", "Maverick", "Neon",
    "Orbit", "Pulse", "Ranger",
)  # fmt: skip
OPPONENT_TEAMS = (
    "Northwind", "Copperline", "Glass Harbor", "Red Lantern", "Bluefin", "Stonegate",
    "Kingfisher", "Ashgrove", "Ironbark", "Tin Soldiers", "Lowtide", "Paper Cranes",
)  # fmt: skip
MODES: tuple[tuple[str, Via], ...] = (
    ("scrim", "team"),
    ("scrim", "team"),
    ("faceit", "team"),
    ("premier", "roster"),
    ("scrim", "team"),
    ("esea", "team"),
)
"""Mode and way in of each match, oldest first, cycled."""
ROSTER_RULE = 3
"""A team sees a match its players sent when 3 of its roster played it on the same side."""
STANDIN_EVERY = 7
"""One match in 7 (when its lineup is full), a stand-in replaces the last starter."""


@dataclass(frozen=True)
class TeamMatch:
    match_id: str
    mode: str
    played_at: dt.datetime
    via: Via
    sent_by: int
    tables: Tables


@dataclass(frozen=True)
class Moment:
    """A round worth a review: what happened in it, from the team's side."""

    match_id: str
    round: int
    tick: int | None
    """The plant, or the end of the freeze time; None when outside the round's ticks."""
    kind: str
    site: str | None


@dataclass(frozen=True)
class Comment:
    match_id: str
    round: int
    tick: int | None
    author: int
    body: str
    at: str


@dataclass(frozen=True)
class Tagged:
    match_id: str
    round: int
    labels: list[str]


@dataclass(frozen=True)
class Playlist:
    name: str
    description: str
    rounds: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class TeamDemo:
    matches: list[TeamMatch]
    comments: list[Comment]
    tags: list[Tagged]
    playlists: list[Playlist]


def _opponent_name(index: int, k: int) -> str:
    return OPPONENT_NAMES[(index * 7 + k) % len(OPPONENT_NAMES)]


def team_mapping(
    tables: Mapping[str, pl.DataFrame], index: int, protagonist: int = PROTAGONIST
) -> tuple[dict[int, int], dict[int, str], str]:
    """The match's players to the team's identities (the protagonist stays, its teammates become
    the roster, the AWPer first, then by kills) and to fresh opponents; with every fake id's name
    and the team's side."""
    players = tables["player"]
    found = players.filter(pl.col("steamid") == protagonist)
    if found.height != 1:
        raise ValueError("the protagonist does not play this match")
    side = str(found["team"][0])
    awp = (
        tables["shot"]
        .filter(pl.col("weapon") == "awp")
        .group_by("shooter")
        .len()
        .rename({"shooter": "steamid", "len": "awp"})
    )
    kills = (
        tables["kill"]
        .filter(~pl.col("is_team_kill"))
        .group_by("attacker")
        .len()
        .rename({"attacker": "steamid", "len": "kills"})
    )
    mates = (
        players.filter((pl.col("team") == side) & (pl.col("steamid") != protagonist))
        .join(awp, on="steamid", how="left")
        .join(kills, on="steamid", how="left")
        .with_columns(pl.col("awp", "kills").fill_null(0))
        .sort(["awp", "kills", "steamid"], descending=[True, True, False])["steamid"]
        .to_list()
    )
    lineup = list(STARTERS)
    if len(mates) >= len(STARTERS) and index % STANDIN_EVERY == STANDIN_EVERY - 2:
        lineup[-1] = STANDINS[0]
    lineup += [p for p in STANDINS if p not in lineup]
    if len(mates) > len(lineup):
        raise ValueError(f"{len(mates)} teammates: more than the roster holds")
    mapping = {protagonist: PROTAGONIST}
    names = {PROTAGONIST: PROTAGONIST_NAME}
    for old, person in zip(mates, lineup, strict=False):
        mapping[old] = person.steam_id
        names[person.steam_id] = person.name
    opponents = sorted(players.filter(pl.col("team") != side)["steamid"].to_list())
    if len(opponents) > OPPONENT_SLOTS:
        raise ValueError(f"{len(opponents)} opponents: more than {OPPONENT_SLOTS}")
    for k, old in enumerate(opponents):
        new = OPPONENT_BASE + index * OPPONENT_SLOTS + k
        mapping[old] = new
        names[new] = _opponent_name(index, k)
    return mapping, names, side


def variant(
    tables: Mapping[str, pl.DataFrame],
    index: int,
    *,
    mode: str,
    played_at: dt.date,
    protagonist: int = PROTAGONIST,
) -> tuple[Tables, str]:
    """One match as the team's: new identities, id, mode and date; returns it with the team's
    side. Only the protagonist keeps a rank, in Premier (a band of the solo demo)."""
    mapping, names, side = team_mapping(tables, index, protagonist)
    original = str(tables["match"]["match_id"][0])
    match_id = hashlib.sha256(f"{SALT}:{original}".encode()).hexdigest()
    out = generic_knives(replace_players(tables, mapping))
    out["player"] = out["player"].with_columns(
        pl.col("steamid").replace_strict(names, return_dtype=pl.String).alias("name"),
        pl.when((pl.col("steamid") == PROTAGONIST) & pl.lit(mode == "premier"))
        .then(pl.col("rank"))
        .cast(pl.Int32)
        .alias("rank"),
        pl.lit(None, pl.Int32).alias("comp_wins"),
    )
    ours, theirs = (TEAM_NAME, OPPONENT_TEAMS[index % len(OPPONENT_TEAMS)])
    named = mode != "premier"
    out["match"] = out["match"].with_columns(
        pl.lit(match_id).alias("match_id"),
        pl.lit(mode).alias("mode"),
        pl.lit(played_at).alias("played_at"),
        pl.lit("Untraded demo").alias("server_name"),
        pl.lit("demo").alias("game_build"),
        pl.lit((ours if side == "A" else theirs) if named else None, pl.String).alias(
            "team_a_name"
        ),
        pl.lit((ours if side == "B" else theirs) if named else None, pl.String).alias(
            "team_b_name"
        ),
    )
    validate(out)
    return out, side


def moments(tables: Mapping[str, pl.DataFrame], side: str) -> list[Moment]:
    """The rounds of the match worth a review, from the side `side`: retakes and post-plants
    (won or lost), and the pistol rounds that open each half."""
    match_id = str(tables["match"]["match_id"][0])
    out: list[Moment] = []
    previous_ct: str | None = None
    for r in tables["round"].sort("round").iter_rows(named=True):

        def within(tick: int | None, r: dict[str, Any] = r) -> int | None:
            # The site comments an instant of the round only (`add_review_comment`).
            if tick is None or not r["start_tick"] <= tick <= r["end_tick"]:
                return None
            return int(tick)

        ct = str(r["ct_team"])
        won = str(r["winner_team"]) == side
        planted = r["bomb_planted_tick"]
        site = None if r["bomb_site"] is None else str(r["bomb_site"])
        if planted is not None:
            if ct == side:
                kind = "retake_won" if won else "retake_lost"
            else:
                kind = "post_plant_won" if won else "post_plant_lost"
            out.append(Moment(match_id, int(r["round"]), within(planted), kind, site))
        elif ct != previous_ct and not r["is_overtime"]:
            kind = "pistol_won" if won else "pistol_lost"
            tick = within(r["freeze_end_tick"])
            out.append(Moment(match_id, int(r["round"]), tick, kind, None))
        previous_ct = ct
    return out


TEXTS: dict[str, tuple[str, ...]] = {
    "retake_lost": (
        "Retake on {site} came in one by one. Wait for the second player and trade the first "
        "contact.",
        "Lost the {site} retake with no utility left. Keep one flash for the retake from now on.",
        "{site} retake: we had the numbers and still lost it. Call the angle you clear first.",
    ),
    "retake_won": (
        "Clean {site} retake: smoke on the plant, flash, two players together. This is the "
        "standard.",
        "Good patience on the {site} retake, we let the clock work for us.",
    ),
    "post_plant_won": (
        "Good post-plant on {site}: crossfire held and nobody peeked the defuser early.",
        "This {site} plant is how we want it: spread out, play the time, trade the first kill.",
        "Post-plant on {site}: the molotov on the defuse won us this one. Same lineup next time.",
    ),
    "post_plant_lost": (
        "We gave up the {site} post-plant by stacking one angle. Spread out after the plant.",
        "{site} plant defused: too passive with the time we had. Check the timer before peeking.",
    ),
    "pistol_lost": (
        "Pistol round lost: we split too late. Agree the call before the freeze time ends.",
        "Pistol round: three of us on one angle, nobody on the flank. Review the setup.",
        "Pistol round lost on the first duel. Utility first, then the peek.",
    ),
    "pistol_won": (
        "Pistol round won with the default. Keep it, it works.",
        "Pistol round: good trade on the first contact, that is what won it.",
    ),
}
REPLIES = (
    "Agreed, I rotated late on this one.",
    "My bad, I should have waited for the flash.",
    "Noted, we drill it on Thursday.",
)
LABELS: dict[str, tuple[str, ...]] = {
    "retake_lost": ("retake", "to drill"),
    "retake_won": ("retake", "good example"),
    "post_plant_won": ("post-plant", "good example"),
    "post_plant_lost": ("post-plant", "to drill"),
    "pistol_lost": ("pistol", "to drill"),
    "pistol_won": ("pistol",),
}
PRIORITY = (
    "retake_lost", "post_plant_won", "pistol_lost", "retake_won", "post_plant_lost", "pistol_won",
)  # fmt: skip
COMMENTED_EVERY = 2
"""The coach reviewed one match in 2, at most `COMMENTS_PER_MATCH` rounds of each."""
COMMENTS_PER_MATCH = 2
PLAYLIST_ROUNDS = 15
PLAYLISTS = (
    (
        "Retakes to drill",
        "CT retakes we lost after the plant: who goes first, what utility is left.",
        "retake_lost",
    ),
    (
        "Post-plants that worked",
        "T rounds we closed after the plant. Watch the positions after the plant.",
        "post_plant_won",
    ),
)


def review(
    matches: Sequence[TeamMatch], sides: Sequence[str]
) -> tuple[list[Comment], list[Tagged], list[Playlist]]:
    """The team's review: comments of the coach (and a reply of a player now and then) on
    rounds chosen by what happened in them, their tags, and the two playlists."""
    used = dict.fromkeys(TEXTS, 0)
    comments: list[Comment] = []
    tags: list[Tagged] = []
    found: list[Moment] = []
    replies = 0
    for index, (match, side) in enumerate(zip(matches, sides, strict=True)):
        here = moments(match.tables, side)
        found.extend(here)
        if index % COMMENTED_EVERY:
            continue
        info = match.tables["match"].row(0, named=True)
        ended = match.played_at + dt.timedelta(
            seconds=float(info["ticks"]) / float(info["tickrate"])
        )
        # The coach looks for something else first in each match: the comments vary.
        start = (index // COMMENTED_EVERY) % len(PRIORITY)
        picked: list[Moment] = []
        for kind in PRIORITY[start:] + PRIORITY[:start]:
            first = next((m for m in here if m.kind == kind), None)
            if first is not None and len(picked) < COMMENTS_PER_MATCH:
                picked.append(first)
        for n, m in enumerate(picked):
            texts = TEXTS[m.kind]
            body = texts[used[m.kind] % len(texts)].format(site=m.site or "the site")
            used[m.kind] += 1
            at = ended + dt.timedelta(hours=14, minutes=7 * n)
            comments.append(
                Comment(m.match_id, m.round, m.tick, COACH.steam_id, body, at.isoformat())
            )
            if m.kind == "retake_lost":
                author = STARTERS[replies % len(STARTERS)].steam_id
                reply = REPLIES[replies % len(REPLIES)]
                later = (at + dt.timedelta(hours=1, minutes=12)).isoformat()
                comments.append(Comment(m.match_id, m.round, None, author, reply, later))
                replies += 1
            tags.append(Tagged(m.match_id, m.round, list(LABELS[m.kind])))
    playlists: list[Playlist] = []
    tagged = {(t.match_id, t.round) for t in tags}
    for name, description, kind in PLAYLISTS:
        rounds = [m for m in found if m.kind == kind][-PLAYLIST_ROUNDS:]
        playlists.append(
            Playlist(
                name, description, [{"match_id": m.match_id, "round": m.round} for m in rounds]
            )
        )
        for m in rounds:
            if (m.match_id, m.round) not in tagged:
                tags.append(Tagged(m.match_id, m.round, list(LABELS[m.kind])))
                tagged.add((m.match_id, m.round))
    return comments, tags, playlists


def build(demo: Sequence[DemoMatch], protagonist: int = PROTAGONIST) -> TeamDemo:
    """The team's variant of the demo's matches (`untraded.demo.build`, oldest first) and its
    review."""
    ordered = sorted(demo, key=lambda m: m.played_at)
    matches: list[TeamMatch] = []
    sides: list[str] = []
    for index, source in enumerate(ordered):
        mode, via = MODES[index % len(MODES)]
        at = source.played_at - SHIFT
        tables, side = variant(
            source.tables, index, mode=mode, played_at=at.date(), protagonist=protagonist
        )
        players = tables["player"]
        mates = players.filter((pl.col("team") == side) & (pl.col("steamid") != PROTAGONIST))
        present = [p.steam_id for p in STARTERS + STANDINS if p.steam_id in mates["steamid"]]
        if via == "roster" and len(present) < ROSTER_RULE - 1:
            via = "team"  # too few of the roster played it for the team to see it otherwise
        if via == "roster":
            # One of them sent it (it counts for them), the one of the cycle when they played.
            wanted = STARTERS[index % len(STARTERS)].steam_id
            sender = wanted if wanted in present else present[0]
        else:
            sender = (
                PROTAGONIST if mode in ("faceit", "esea") and index % 4 == 2 else COACH.steam_id
            )
        match_id = str(tables["match"]["match_id"][0])
        matches.append(TeamMatch(match_id, mode, at, via, sender, tables))
        sides.append(side)
    comments, tags, playlists = review(matches, sides)
    return TeamDemo(matches, comments, tags, playlists)


def _people(people: Iterable[Person]) -> list[dict[str, Any]]:
    return [asdict(p) for p in people]


def write(team: TeamDemo, root: Path) -> Path:
    """`root/matches/{match_id}/{table}.parquet` and `root/team.json`; returns the manifest's
    path."""
    for m in team.matches:
        target = root / "matches" / m.match_id
        target.mkdir(parents=True, exist_ok=True)
        for name, table in m.tables.items():
            table.write_parquet(target / f"{name}.parquet", compression="zstd")
    manifest = root / "team.json"
    body = {
        "team": {"name": TEAM_NAME, "slug": TEAM_SLUG},
        "people": _people(PEOPLE),
        "matches": [
            {
                "match_id": m.match_id,
                "mode": m.mode,
                "played_at": m.played_at.isoformat(),
                "via": m.via,
                "sent_by": m.sent_by,
            }
            for m in team.matches
        ],
        "comments": [asdict(c) for c in team.comments],
        "tags": [asdict(t) for t in team.tags],
        "playlists": [asdict(p) for p in team.playlists],
    }
    manifest.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest
