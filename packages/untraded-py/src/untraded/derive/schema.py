# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Strict schemas of the derived tables (the round model, workstream E4).

Derived tables hold facts measured in the match (delays in seconds, distances in Hammer units).
Adjustable thresholds (trade window, opportunity distance, isolation radius) are applied by the
metrics, so changing a parameter never requires deriving again. Buy types are the exception: the
plan places them here, and their thresholds are explicit parameters (`BuyThresholds`).
"""

from __future__ import annotations

import polars as pl

from untraded.parsing.schema import Side, Team

Columns = dict[str, pl.DataType | type[pl.DataType]]

BuyType = pl.Enum(["pistol", "eco", "semi", "force", "full"])

_ROUND_PLAYER: Columns = {
    "round": pl.Int16,
    "steamid": pl.UInt64,
    "team": Team,
    "side": Side,
    "kills": pl.Int16,
    "deaths": pl.Int16,
    "assists": pl.Int16,
    "flash_assists": pl.Int16,
    "damage": pl.Int32,
    "survived": pl.Boolean,
    "death_tick": pl.Int32,
    "death_trade_delay_s": pl.Float32,
    "opening_kill": pl.Boolean,
    "opening_death": pl.Boolean,
    "setup_place": pl.String,
    "team_won": pl.Boolean,
}

_DEATH: Columns = {
    "tick": pl.Int32,
    "round": pl.Int16,
    "victim": pl.UInt64,
    "victim_team": Team,
    "killer": pl.UInt64,
    "killer_team": Team,
    "is_enemy_kill": pl.Boolean,
    "is_opening": pl.Boolean,
    "trade_delay_s": pl.Float32,
    "trader": pl.UInt64,
    "avenges_delay_s": pl.Float32,
    "nearest_teammate_distance": pl.Float32,
}

_TRADE_OPPORTUNITY: Columns = {
    "tick": pl.Int32,
    "round": pl.Int16,
    "victim": pl.UInt64,
    "killer": pl.UInt64,
    "teammate": pl.UInt64,
    "distance_to_killer": pl.Float32,
}

_CLUTCH: Columns = {
    "round": pl.Int16,
    "steamid": pl.UInt64,
    "team": Team,
    "side": Side,
    "enemies": pl.Int8,
    "start_tick": pl.Int32,
    "won": pl.Boolean,
}

_TEAM_ROUND: Columns = {
    "round": pl.Int16,
    "team": Team,
    "side": Side,
    "won": pl.Boolean,
    "equip_value": pl.Float32,
    "buy_type": BuyType,
}

TABLES: dict[str, pl.Schema] = {
    "round_player": pl.Schema(_ROUND_PLAYER),
    "death": pl.Schema(_DEATH),
    "trade_opportunity": pl.Schema(_TRADE_OPPORTUNITY),
    "clutch": pl.Schema(_CLUTCH),
    "team_round": pl.Schema(_TEAM_ROUND),
}
