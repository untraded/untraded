# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The `player_tick` and `inventory_change` tables."""

from __future__ import annotations

import polars as pl

from untraded.parsing._context import Context, side

SAMPLE_HZ = 16
"""⚙ Sampling rate of `player_tick` (docs/canonical-tables.md § 2)."""

TICK_PROPS = [
    "X",
    "Y",
    "Z",
    "pitch",
    "yaw",
    "velocity_X",
    "velocity_Y",
    "velocity_Z",
    "health",
    "armor_value",
    "has_helmet",
    "is_alive",
    "last_place_name",
    "active_weapon_name",
    "balance",
    "current_equip_value",
    "flash_duration",
    "is_scoped",
    "ducking",
    "is_airborne",
    "is_walking",
    "is_defusing",
    "has_defuser",
    "spotted",
    "approximate_spotted_by",
    "team_num",
]


def sample_ticks(ctx: Context, extra: list[int]) -> list[int]:
    """Ticks at SAMPLE_HZ within each live round, plus round boundaries and `extra` (kill ticks)."""
    step = max(1, round(ctx.tickrate / SAMPLE_HZ))
    wanted: set[int] = set(extra)
    for cut in ctx.cuts:
        wanted.update(range(cut.start_tick, cut.end_tick + 1, step))
        wanted.update((cut.freeze_end_tick, cut.end_tick))
    return sorted(wanted)


def build_player_ticks(ctx: Context, kill_ticks: list[int]) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Returns (`player_tick`, `inventory_change`), read in one pass.

    Player state is sampled at SAMPLE_HZ, exact at kills and round boundaries; rows of players
    not on a team (spectators, or absent at that tick) are dropped. Inventory changes are found
    on the same samples: a change undone within one sample interval (62 ms at 64 ticks/s) is not
    seen; there were 4 such changes of 2,363 on a 30-round match, and reading the inventory at
    every tick instead doubled the peak memory of a parse (about 2 GB).
    """
    raw = ctx.ticks([*TICK_PROPS, "inventory"], sample_ticks(ctx, kill_ticks))
    states = ctx.in_rounds(raw.with_columns(side("team_num").alias("side")).drop_nulls("side"))
    player_tick = states.select(
        "tick",
        "round",
        "steamid",
        "side",
        pl.col("X").alias("x"),
        pl.col("Y").alias("y"),
        pl.col("Z").alias("z"),
        "pitch",
        "yaw",
        pl.col("velocity_X").alias("velocity_x"),
        pl.col("velocity_Y").alias("velocity_y"),
        pl.col("velocity_Z").alias("velocity_z"),
        "health",
        pl.col("armor_value").alias("armor"),
        "has_helmet",
        "is_alive",
        pl.col("last_place_name").alias("place"),
        pl.col("active_weapon_name").alias("active_weapon"),
        "balance",
        pl.col("current_equip_value").alias("equip_value"),
        "flash_duration",
        "is_scoped",
        "ducking",
        "is_airborne",
        "is_walking",
        "is_defusing",
        "has_defuser",
        "spotted",
        pl.col("approximate_spotted_by").cast(pl.List(pl.UInt64)).alias("spotted_by"),
    ).sort("tick", "steamid")

    previous = pl.col("inventory").shift(1).over("steamid")
    inventory_change = (
        states.select("tick", "round", "steamid", "inventory")
        .sort("steamid", "tick")
        .filter(previous.is_null() | (pl.col("inventory") != previous))
        .sort("tick", "steamid")
    )
    return player_tick, inventory_change
