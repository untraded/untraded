# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The `bomb` table: one row per bomb event."""

from __future__ import annotations

import polars as pl

from untraded.parsing._context import Context, steamid
from untraded.parsing.core import bomb_site
from untraded.parsing.schema import BOMB

# event -> canonical type, and whether the site comes from the player's place (plant events)
EVENTS = {
    "bomb_beginplant": ("plant_begin", True),
    "bomb_planted": ("planted", True),
    "bomb_begindefuse": ("defuse_begin", False),
    "bomb_defused": ("defused", False),
    "bomb_exploded": ("exploded", False),
    "bomb_dropped": ("dropped", False),
    "bomb_pickup": ("picked_up", False),
}
AT_PLANTED_BOMB = {"defuse_begin", "defused", "exploded"}


def build_bomb(ctx: Context, rounds: pl.DataFrame) -> pl.DataFrame:
    """Defuses and explosions take the site of the round's plant (`rounds.bomb_site`)."""
    parts = []
    for name, (kind, from_place) in EVENTS.items():
        if name not in ctx.events:
            continue
        found = ctx.event(name, player=["last_place_name"]) if from_place else ctx.event(name)
        if not found.height:
            continue
        player = (
            steamid("user_steamid") if "user_steamid" in found.columns else pl.lit(None, pl.UInt64)
        )
        site = bomb_site("user_last_place_name") if from_place else pl.lit(None, pl.String)
        parts.append(
            found.select(
                "tick", pl.lit(kind).alias("type"), player.alias("player"), site.alias("site")
            )
        )
    if not parts:
        ctx.unavailable.append("bomb: no bomb event")
        return pl.DataFrame(schema=BOMB)
    events = ctx.in_rounds(pl.concat(parts, how="vertical_relaxed"))
    sites = rounds.select("round", pl.col("bomb_site").cast(pl.String).alias("round_site"))
    return (
        events.join(sites, on="round", how="left")
        .with_columns(
            pl.when(pl.col("type").is_in(list(AT_PLANTED_BOMB)))
            .then(pl.col("round_site"))
            .otherwise(pl.col("site"))
            .alias("site")
        )
        .drop("round_site")
        .sort("tick", "type")
    )
