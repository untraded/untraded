# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""A demo account built from real matches, with every player anonymized.

A demo needs matches rich enough to show everything (sessions, a reference, priorities, the 2D
viewer, the rating), and nobody's identity: the matches of one player are taken, every steamid is
replaced by a fake one (the same in every match, so a regular teammate stays recognisable) and
every name by an invented one; the server, the team names, the game build and the other
players' ranks go too, and the protagonist's rank becomes its band of 2,500
(`untraded.fixtures.replace_players` raises if a steamid would slip through). This is
pseudonymization, not anonymity: someone who knows whose matches they are could find them in
public match histories by their maps and scores. Use the matches of a player who agrees.

The dates are moved: the matches keep their order but are grouped into sessions of a few matches,
one every other day, the last one ending at `end`. Sessions of different sizes give the reports a
growing history (no reference, then the player's own days), and priorities followed from one
session to the next.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from untraded.fixtures import generic_knives, replace_players
from untraded.parsing.validate import validate

Tables = dict[str, pl.DataFrame]

FAKE_STEAM_BASE = 76561190000100000
"""Fake SteamID64s start after this one: no Steam account sits in this range."""
PROTAGONIST = FAKE_STEAM_BASE + 1
PROTAGONIST_NAME = "Demo"
PSEUDOS = (
    "Kestrel", "Ravel", "Juno", "Marlow", "Tidewater", "Ember", "Sable", "Quill", "Nimbus",
    "Halcyon", "Brisk", "Corvo", "Vesper", "Lumen", "Pike", "Orrin", "Talon", "Wren", "Ashby",
    "Fennel", "Glint", "Harrow", "Ione", "Jasper", "Kite", "Lark", "Moss", "Nyx", "Onyx",
    "Pallas", "Rook", "Sorrel", "Thistle", "Umber", "Vale", "Wisp", "Yarrow", "Zephyr", "Alder",
    "Bram", "Cinder", "Dusk", "Elm", "Flint", "Gale", "Heron", "Iris", "Jett", "Knoll", "Loch",
    "Merit", "Nova", "Oak", "Pine", "Quartz", "Reed", "Slate", "Tarn", "Ursa", "Vireo", "Weald",
    "Yew", "Zinnia", "Arbor", "Birch", "Coral", "Drift", "Echo", "Fable", "Grove", "Hollow",
    "Indigo", "Juniper", "Kelp", "Lyric", "Meadow", "Nettle", "Opal", "Prism", "Rune", "Spruce",
    "Tundra", "Ultra", "Verge", "Willow", "Xeno", "Yonder", "Zest", "Aster", "Bolt", "Crest",
    "Dune", "Eddy", "Frost", "Gust", "Haze", "Inlet", "Jade", "Karst", "Ledge", "Mist", "Nook",
)  # fmt: skip
RANK_BAND = 2500
SESSION_SIZES = (3, 4, 3, 2, 4, 3, 4, 3, 4)
"""Matches per session, oldest first, cycled: the corpus's 30 matches make 9 sessions."""
SESSION_GAP = dt.timedelta(days=2)
BETWEEN_MATCHES = dt.timedelta(minutes=8)


@dataclass(frozen=True)
class DemoMatch:
    match_id: str
    """A new id (the sha256 of the original id, salted): the original one is not kept."""
    mode: str
    played_at: dt.datetime
    tables: Tables


def steam_mapping(
    matches: Sequence[Mapping[str, pl.DataFrame]], protagonist: int
) -> dict[int, int]:
    """Every player of the matches to a fake SteamID64: the protagonist first, then by how often
    they play (a regular teammate gets a small number), then by id, for a stable mapping."""
    counts = Counter(s for t in matches for s in t["player"]["steamid"].to_list())
    if protagonist not in counts:
        raise ValueError("the protagonist plays in none of the matches")
    others = sorted((s for s in counts if s != protagonist), key=lambda s: (-counts[s], s))
    mapping = {protagonist: PROTAGONIST}
    mapping.update({s: PROTAGONIST + 1 + i for i, s in enumerate(others)})
    return mapping


def fake_name(steam_id: int) -> str:
    if steam_id == PROTAGONIST:
        return PROTAGONIST_NAME
    n = steam_id - PROTAGONIST - 1
    base = PSEUDOS[n % len(PSEUDOS)]
    return base if n < len(PSEUDOS) else f"{base}{n // len(PSEUDOS) + 1}"


def anonymize(
    tables: Mapping[str, pl.DataFrame], mapping: Mapping[int, int], match_id: str
) -> Tables:
    """One match with fake steamids and names; only the protagonist keeps a rank (the level
    references read it)."""
    out = generic_knives(replace_players(tables, mapping))
    out["player"] = out["player"].with_columns(
        pl.col("steamid").map_elements(fake_name, return_dtype=pl.String).alias("name"),
        # The protagonist's rating as its band of 2,500 (what the level references read).
        pl.when(pl.col("steamid") == PROTAGONIST)
        .then(pl.col("rank") // RANK_BAND * RANK_BAND)
        .cast(pl.Int32)
        .alias("rank"),
        pl.lit(None, pl.Int32).alias("comp_wins"),
    )
    out["match"] = out["match"].with_columns(
        pl.lit(match_id).alias("match_id"),
        pl.lit("Untraded demo").alias("server_name"),
        pl.lit("demo").alias("game_build"),
        pl.lit(None, pl.String).alias("team_a_name"),
        pl.lit(None, pl.String).alias("team_b_name"),
    )
    validate(out)
    return out


def _duration(tables: Mapping[str, pl.DataFrame]) -> dt.timedelta:
    info = tables["match"].row(0, named=True)
    return dt.timedelta(seconds=float(info["ticks"]) / float(info["tickrate"]))


def _sessions(count: int) -> Iterator[list[int]]:
    start, i = 0, 0
    while start < count:
        size = SESSION_SIZES[i % len(SESSION_SIZES)]
        yield list(range(start, min(start + size, count)))
        start += size
        i += 1


def build(
    matches: Sequence[Mapping[str, pl.DataFrame]], protagonist: int, end: dt.datetime
) -> list[DemoMatch]:
    """The demo account's matches, oldest first: anonymized, dated in sessions, the last one
    ending before `end` (timezone-aware)."""
    ordered = sorted(
        matches,
        key=lambda t: (t["match"]["played_at"][0] is None, str(t["match"]["played_at"][0])),
    )
    mapping = steam_mapping(ordered, protagonist)
    sessions = list(_sessions(len(ordered)))
    # The last session starts at 19:00 the day before `end`; each earlier one SESSION_GAP before.
    last_start = (end - dt.timedelta(days=1)).replace(hour=19, minute=0, second=0, microsecond=0)
    out: list[DemoMatch] = []
    for number, indices in enumerate(sessions):
        at = last_start - SESSION_GAP * (len(sessions) - 1 - number)
        for i in indices:
            source = ordered[i]
            original = str(source["match"]["match_id"][0])
            match_id = hashlib.sha256(f"untraded-demo:{original}".encode()).hexdigest()
            tables = anonymize(source, mapping, match_id)
            tables["match"] = tables["match"].with_columns(pl.lit(at.date()).alias("played_at"))
            out.append(DemoMatch(match_id, str(tables["match"]["mode"][0]), at, tables))
            at = at + _duration(source) + BETWEEN_MATCHES
    return out


def write(matches: Sequence[DemoMatch], root: Path) -> Path:
    """`root/matches/{match_id}/{table}.parquet` and `root/demo.json` (each match's id, mode and
    start); returns the manifest's path."""
    for m in matches:
        target = root / "matches" / m.match_id
        target.mkdir(parents=True, exist_ok=True)
        for name, table in m.tables.items():
            table.write_parquet(target / f"{name}.parquet", compression="zstd")
    manifest = root / "demo.json"
    manifest.write_text(
        json.dumps(
            [
                {"match_id": m.match_id, "mode": m.mode, "played_at": m.played_at.isoformat()}
                for m in matches
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest
