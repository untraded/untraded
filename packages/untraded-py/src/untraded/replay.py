# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""A round as the 2D viewer replays it: compact, one JSON document per round.

Built from the canonical tables of a match (`player_tick`, `kill`, `grenade`, `grenade_path`,
`bomb`, `blind`, `round`, `player`, `match`). The players' states share one timeline, the
`player_tick` samples of the round (16 Hz, exact at kills and round boundaries): each player has
one array per state, aligned on `ticks`, with `null` where they have no sample. Coordinates are
world units rounded to integers, angles whole degrees: enough for a 1024-pixel radar, where one
pixel is 4 to 7 units.

Format version `REPLAY_VERSION`; a change to it is a new version, and the replays are rebuilt.
"""

from __future__ import annotations

import gzip
import json
from collections.abc import Mapping
from typing import Any

import polars as pl

from untraded.maps import RADARS

REPLAY_VERSION = 1

STATES = {
    # replay key: (player_tick column, how it is stored)
    "x": ("x", "int"),
    "y": ("y", "int"),
    "z": ("z", "int"),
    "yaw": ("yaw", "deg"),
    "hp": ("health", "int"),
    "armor": ("armor", "int"),
    "alive": ("is_alive", "bool"),
    "flash": ("flash_duration", "tenth"),
    "scoped": ("is_scoped", "bool"),
    "defusing": ("is_defusing", "bool"),
}
"""The player states a replay keeps. `weapon` is kept too, as an index into `weapons`."""


def build_replays(tables: Mapping[str, pl.DataFrame]) -> dict[int, dict[str, Any]]:
    """Every round of the match, by round number."""
    return {int(number): build_replay(tables, int(number)) for number in tables["round"]["round"]}


def build_replay(tables: Mapping[str, pl.DataFrame], number: int) -> dict[str, Any]:
    match = tables["match"].row(0, named=True)
    round_ = tables["round"].filter(pl.col("round") == number).row(0, named=True)
    sides = {round_["ct_team"]: "CT", round_["t_team"]: "T"}
    names = {row["steamid"]: row for row in tables["player"].iter_rows(named=True)}

    ticks_frame = tables["player_tick"].filter(pl.col("round") == number)
    timeline = ticks_frame.select("tick").unique().sort("tick")["tick"].to_list()
    weapons = sorted({w for w in ticks_frame["active_weapon"].unique().to_list() if w is not None})
    weapon_index = {name: i for i, name in enumerate(weapons)}
    players = []
    for steamid in sorted(ticks_frame["steamid"].unique().to_list()):
        rows = (
            pl.DataFrame({"tick": timeline}, schema={"tick": pl.Int32})
            .join(ticks_frame.filter(pl.col("steamid") == steamid), on="tick", how="left")
            .sort("tick")
        )
        player: dict[str, Any] = {
            "steamid": str(steamid),
            "name": names.get(steamid, {}).get("name", str(steamid)),
            "team": names.get(steamid, {}).get("team"),
            "side": sides.get(names.get(steamid, {}).get("team")),
        }
        for key, (column, kind) in STATES.items():
            player[key] = _values(rows[column], kind)
        player["weapon"] = [
            None if w is None else weapon_index[w] for w in rows["active_weapon"].to_list()
        ]
        players.append(player)

    radar = RADARS.get(match["map"])
    return {
        "version": REPLAY_VERSION,
        "match_id": match["match_id"],
        "round": number,
        "map": match["map"],
        "radar": None
        if radar is None
        else {
            "pos_x": radar.pos_x,
            "pos_y": radar.pos_y,
            "scale": radar.scale,
            "lower_below": radar.lower_below,
        },
        "tickrate": float(match["tickrate"]),
        "start_tick": round_["start_tick"],
        "freeze_end_tick": round_["freeze_end_tick"],
        "end_tick": round_["end_tick"],
        "winner_side": round_["winner_side"],
        "reason": round_["reason"],
        "ticks": timeline,
        "weapons": weapons,
        "players": players,
        "kills": _kills(tables["kill"], number),
        "grenades": _grenades(tables["grenade"], tables["grenade_path"], number),
        "blinds": _rows(
            tables["blind"].filter(pl.col("round") == number),
            {"tick": "tick", "victim": "victim", "flasher": "flasher", "duration": "duration"},
        ),
        "bomb": _bomb(tables["bomb"], ticks_frame, number),
    }


def to_json_gz(replay: Mapping[str, Any]) -> bytes:
    """The replay as the store keeps it and the API serves it: compact JSON, gzipped."""
    text = json.dumps(replay, separators=(",", ":"), ensure_ascii=False)
    return gzip.compress(text.encode("utf-8"), compresslevel=9, mtime=0)


def _values(column: pl.Series, kind: str) -> list[Any]:
    if kind == "int":
        return [None if v is None else round(v) for v in column.to_list()]
    if kind == "deg":
        return [None if v is None else round(v) % 360 for v in column.to_list()]
    if kind == "tenth":
        return [None if v is None else round(v, 1) for v in column.to_list()]
    return [None if v is None else int(bool(v)) for v in column.to_list()]


PLAYER_KEYS = frozenset({"attacker", "victim", "assister", "flasher", "player", "thrower"})
"""Replay keys holding a SteamID: always a string (it does not fit in a JavaScript number)."""


def _value(key: str, value: Any) -> Any:
    if value is None:
        return None
    if key in PLAYER_KEYS:
        return str(value)
    if isinstance(value, float):
        return round(value, 1)
    return value


def _rows(frame: pl.DataFrame, columns: Mapping[str, str]) -> list[dict[str, Any]]:
    return [
        {key: _value(key, row[column]) for key, column in columns.items()}
        for row in frame.sort("tick").iter_rows(named=True)
    ]


def _kills(kills: pl.DataFrame, number: int) -> list[dict[str, Any]]:
    found = _rows(
        kills.filter(pl.col("round") == number),
        {
            "tick": "tick",
            "attacker": "attacker",
            "victim": "victim",
            "assister": "assister",
            "weapon": "weapon",
            "headshot": "headshot",
            "wallbang": "wallbang",
            "through_smoke": "through_smoke",
            "team_kill": "is_team_kill",
            "attacker_x": "attacker_x",
            "attacker_y": "attacker_y",
            "attacker_z": "attacker_z",
            "victim_x": "victim_x",
            "victim_y": "victim_y",
            "victim_z": "victim_z",
        },
    )
    for kill in found:
        for key in ("attacker_x", "attacker_y", "attacker_z", "victim_x", "victim_y", "victim_z"):
            if kill[key] is not None:
                kill[key] = round(kill[key])
    return found


def _grenades(grenades: pl.DataFrame, paths: pl.DataFrame, number: int) -> list[dict[str, Any]]:
    found = []
    for row in grenades.filter(pl.col("round") == number).sort("throw_tick").iter_rows(named=True):
        path = paths.filter(pl.col("grenade_id") == row["grenade_id"]).sort("tick")
        found.append(
            {
                "id": row["grenade_id"],
                "type": row["type"],
                "thrower": _value("thrower", row["thrower"]),
                "side": row["side"],
                "throw_tick": row["throw_tick"],
                "detonate_tick": row["detonate_tick"],
                "end_tick": row["end_tick"],
                "detonate": None
                if row["detonate_x"] is None
                else [round(row["detonate_x"]), round(row["detonate_y"]), round(row["detonate_z"])],
                "path": {
                    "ticks": path["tick"].to_list(),
                    "x": [round(v) for v in path["x"].to_list()],
                    "y": [round(v) for v in path["y"].to_list()],
                    "z": [round(v) for v in path["z"].to_list()],
                },
            }
        )
    return found


def _bomb(bomb: pl.DataFrame, ticks: pl.DataFrame, number: int) -> dict[str, Any]:
    """The bomb's events, and where it was planted: the planter's position at that tick (the
    bomb itself has no position in the tables)."""
    events = _rows(
        bomb.filter(pl.col("round") == number),
        {"tick": "tick", "type": "type", "player": "player", "site": "site"},
    )
    planted = next((e for e in events if e["type"] == "planted"), None)
    position = None
    if planted is not None and planted["player"] is not None:
        planter = ticks.filter(
            (pl.col("steamid") == int(planted["player"])) & (pl.col("tick") <= planted["tick"])
        ).sort("tick")
        if planter.height:
            last = planter.row(-1, named=True)
            position = [round(last["x"]), round(last["y"]), round(last["z"])]
    return {"events": events, "planted_at": position}
