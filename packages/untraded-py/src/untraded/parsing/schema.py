# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Strict Polars schemas of the canonical tables (docs/canonical-tables.md).

Only the tables built so far are defined here.
"""

from __future__ import annotations

import polars as pl

Columns = dict[str, pl.DataType | type[pl.DataType]]

SCHEMA_VERSION = "1.1"

MODES = ("premier", "faceit", "esea", "scrim", "pro")
"""Supported game modes. The demo does not carry its mode: it is an ingestion input (ADR 0008)."""

Side = pl.Enum(["CT", "T"])
Team = pl.Enum(["A", "B"])
"""`A` started the match on CT, `B` on T; stable across side switches."""
Reason = pl.Enum(
    ["bomb_exploded", "bomb_defused", "elimination", "time_ran_out", "surrender", "other"]
)

_MATCH: Columns = {
    "match_id": pl.String,
    "schema_version": pl.String,
    "parser": pl.String,
    "parser_version": pl.String,
    "source": pl.String,
    "mode": pl.String,
    "played_at": pl.Date,
    "map": pl.String,
    "game_build": pl.String,
    "server_name": pl.String,
    "tickrate": pl.Float32,
    "ticks": pl.Int32,
    "rounds_played": pl.Int16,
    "score_a": pl.Int16,
    "score_b": pl.Int16,
    "team_a_name": pl.String,
    "team_b_name": pl.String,
    "first_round": pl.Int16,
    "events_available": pl.List(pl.String),
    "unavailable": pl.List(pl.String),
}

_PLAYER: Columns = {
    "steamid": pl.UInt64,
    "name": pl.String,
    "team": Team,
    "rank": pl.Int32,
    "comp_wins": pl.Int32,
    "rounds_on_team": pl.Int16,
}

_ROUND: Columns = {
    "round": pl.Int16,
    "start_tick": pl.Int32,
    "freeze_end_tick": pl.Int32,
    "end_tick": pl.Int32,
    "official_end_tick": pl.Int32,
    "winner_side": Side,
    "winner_team": Team,
    "reason": Reason,
    "ct_team": Team,
    "t_team": Team,
    "score_a": pl.Int16,
    "score_b": pl.Int16,
    "is_overtime": pl.Boolean,
    "bomb_planted_tick": pl.Int32,
    "bomb_site": pl.Enum(["A", "B"]),
    "bomb_planter": pl.UInt64,
    "bomb_defused_tick": pl.Int32,
    "bomb_defuser": pl.UInt64,
    "bomb_exploded_tick": pl.Int32,
}

_KILL: Columns = {
    "tick": pl.Int32,
    "round": pl.Int16,
    "attacker": pl.UInt64,
    "victim": pl.UInt64,
    "assister": pl.UInt64,
    "flash_assist": pl.Boolean,
    "weapon": pl.String,
    "headshot": pl.Boolean,
    "wallbang": pl.Boolean,
    "noscope": pl.Boolean,
    "through_smoke": pl.Boolean,
    "attacker_blind": pl.Boolean,
    "attacker_in_air": pl.Boolean,
    "hitgroup": pl.Int8,
    "distance": pl.Float32,
    "attacker_side": Side,
    "victim_side": Side,
    "is_team_kill": pl.Boolean,
    "is_suicide": pl.Boolean,
    "victim_bot": pl.Boolean,
    "attacker_x": pl.Float32,
    "attacker_y": pl.Float32,
    "attacker_z": pl.Float32,
    "victim_x": pl.Float32,
    "victim_y": pl.Float32,
    "victim_z": pl.Float32,
    "attacker_place": pl.String,
    "victim_place": pl.String,
    "attacker_equip_value": pl.Int32,
    "victim_equip_value": pl.Int32,
    "victim_inventory": pl.List(pl.String),
    "victim_flash_duration": pl.Float32,
}

_DAMAGE: Columns = {
    "tick": pl.Int32,
    "round": pl.Int16,
    "attacker": pl.UInt64,
    "victim": pl.UInt64,
    "weapon": pl.String,
    "hitgroup": pl.Int8,
    "dmg_health": pl.Int16,
    "dmg_armor": pl.Int16,
    "health_after": pl.Int16,
    "armor_after": pl.Int16,
    "damage": pl.Int16,
    "is_team_damage": pl.Boolean,
    "grenade_id": pl.Int32,
}

_BLIND: Columns = {
    "tick": pl.Int32,
    "round": pl.Int16,
    "victim": pl.UInt64,
    "flasher": pl.UInt64,
    "grenade_id": pl.Int32,
    "duration": pl.Float32,
    "is_teammate": pl.Boolean,
    "is_self": pl.Boolean,
    "from_fallback": pl.Boolean,
}

BombEvent = pl.Enum(
    ["plant_begin", "planted", "defuse_begin", "defused", "exploded", "dropped", "picked_up"]
)

_BOMB: Columns = {
    "tick": pl.Int32,
    "round": pl.Int16,
    "type": BombEvent,
    "player": pl.UInt64,
    "site": pl.Enum(["A", "B"]),
}

_ECONOMY: Columns = {
    "round": pl.Int16,
    "steamid": pl.UInt64,
    "side": Side,
    "money_start": pl.Int32,
    "spent": pl.Int32,
    "equip_value": pl.Int32,
    "round_start_equip_value": pl.Int32,
    "armor": pl.Int16,
    "has_helmet": pl.Boolean,
    "has_defuser": pl.Boolean,
    "inventory": pl.List(pl.String),
}

_SHOT: Columns = {
    "tick": pl.Int32,
    "round": pl.Int16,
    "shooter": pl.UInt64,
    "weapon": pl.String,
    "silenced": pl.Boolean,
    "x": pl.Float32,
    "y": pl.Float32,
    "z": pl.Float32,
    "pitch": pl.Float32,
    "yaw": pl.Float32,
    "velocity_x": pl.Float32,
    "velocity_y": pl.Float32,
    "velocity_z": pl.Float32,
    "is_scoped": pl.Boolean,
    "ducking": pl.Boolean,
    "is_airborne": pl.Boolean,
    "is_walking": pl.Boolean,
    "accuracy_penalty": pl.Float32,
}

GrenadeType = pl.Enum(["flash", "he", "smoke", "molotov", "incendiary", "decoy"])

_GRENADE: Columns = {
    "grenade_id": pl.Int32,
    "entity_id": pl.Int32,
    "round": pl.Int16,
    "thrower": pl.UInt64,
    "side": Side,
    "type": GrenadeType,
    "throw_tick": pl.Int32,
    "throw_x": pl.Float32,
    "throw_y": pl.Float32,
    "throw_z": pl.Float32,
    "detonate_tick": pl.Int32,
    "detonate_x": pl.Float32,
    "detonate_y": pl.Float32,
    "detonate_z": pl.Float32,
    "end_tick": pl.Int32,
}

_GRENADE_PATH: Columns = {
    "grenade_id": pl.Int32,
    "tick": pl.Int32,
    "x": pl.Float32,
    "y": pl.Float32,
    "z": pl.Float32,
}

_INVENTORY_CHANGE: Columns = {
    "tick": pl.Int32,
    "round": pl.Int16,
    "steamid": pl.UInt64,
    "inventory": pl.List(pl.String),
}

_PLAYER_TICK: Columns = {
    "tick": pl.Int32,
    "round": pl.Int16,
    "steamid": pl.UInt64,
    "side": Side,
    "x": pl.Float32,
    "y": pl.Float32,
    "z": pl.Float32,
    "pitch": pl.Float32,
    "yaw": pl.Float32,
    "velocity_x": pl.Float32,
    "velocity_y": pl.Float32,
    "velocity_z": pl.Float32,
    "health": pl.Int16,
    "armor": pl.Int16,
    "has_helmet": pl.Boolean,
    "is_alive": pl.Boolean,
    "place": pl.String,
    "active_weapon": pl.String,
    "balance": pl.Int32,
    "equip_value": pl.Int32,
    "flash_duration": pl.Float32,
    "is_scoped": pl.Boolean,
    "ducking": pl.Boolean,
    "is_airborne": pl.Boolean,
    "is_walking": pl.Boolean,
    "is_defusing": pl.Boolean,
    "has_defuser": pl.Boolean,
    "spotted": pl.Boolean,
    "spotted_by": pl.List(pl.UInt64),
}

MATCH = pl.Schema(_MATCH)
PLAYER = pl.Schema(_PLAYER)
ROUND = pl.Schema(_ROUND)
KILL = pl.Schema(_KILL)
DAMAGE = pl.Schema(_DAMAGE)
BLIND = pl.Schema(_BLIND)
BOMB = pl.Schema(_BOMB)
ECONOMY = pl.Schema(_ECONOMY)
SHOT = pl.Schema(_SHOT)
GRENADE = pl.Schema(_GRENADE)
GRENADE_PATH = pl.Schema(_GRENADE_PATH)
INVENTORY_CHANGE = pl.Schema(_INVENTORY_CHANGE)
PLAYER_TICK = pl.Schema(_PLAYER_TICK)

TABLES: dict[str, pl.Schema] = {
    "match": MATCH,
    "player": PLAYER,
    "round": ROUND,
    "kill": KILL,
    "damage": DAMAGE,
    "blind": BLIND,
    "bomb": BOMB,
    "economy": ECONOMY,
    "shot": SHOT,
    "grenade": GRENADE,
    "grenade_path": GRENADE_PATH,
    "inventory_change": INVENTORY_CHANGE,
    "player_tick": PLAYER_TICK,
}


class CanonicalError(ValueError):
    """A canonical table does not match its schema or fails a validation rule."""


def conform(frame: pl.DataFrame, table: str) -> pl.DataFrame:
    """Selects and casts the columns of `table`, in spec order. Missing or extra columns raise."""
    schema = TABLES[table]
    missing = [name for name in schema if name not in frame.columns]
    extra = [name for name in frame.columns if name not in schema]
    if missing or extra:
        raise CanonicalError(f"{table}: missing {missing}, unexpected {extra}")
    try:
        return frame.select(pl.col(name).cast(dtype, strict=True) for name, dtype in schema.items())
    except pl.exceptions.InvalidOperationError as error:
        raise CanonicalError(f"{table}: {error}") from error
