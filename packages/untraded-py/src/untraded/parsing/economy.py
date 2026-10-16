# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The `economy` table: one row per player and round."""

from __future__ import annotations

import polars as pl

from untraded.parsing._context import Context

BUY_SECONDS = 7.0
"""⚙ Buy state is read this long after freeze end (metrics-v1 § 5), or at round end if sooner."""

BUY_PROPS = [
    "cash_spent_this_round",
    "current_equip_value",
    "round_start_equip_value",
    "armor_value",
    "has_helmet",
    "has_defuser",
    "inventory",
]


def build_economy(ctx: Context) -> pl.DataFrame:
    delay = round(BUY_SECONDS * ctx.tickrate)
    moments = pl.DataFrame(
        {
            "round": pl.Series([c.round for c in ctx.cuts], dtype=pl.Int16),
            "start_tick": pl.Series([c.start_tick for c in ctx.cuts], dtype=pl.Int32),
            "buy_tick": pl.Series(
                [min(c.freeze_end_tick + delay, c.end_tick) for c in ctx.cuts], dtype=pl.Int32
            ),
        }
    )
    money = ctx.ticks(["balance"], moments["start_tick"].to_list()).select(
        pl.col("tick").alias("start_tick"), "steamid", pl.col("balance").alias("money_start")
    )
    bought = ctx.ticks(BUY_PROPS, moments["buy_tick"].to_list()).rename(
        {
            "tick": "buy_tick",
            "cash_spent_this_round": "spent",
            "current_equip_value": "equip_value",
            "armor_value": "armor",
        }
    )
    players = ctx.on_team.select("round", pl.col("steamid").cast(pl.UInt64), "side")
    return (
        players.join(moments, on="round", how="left")
        .join(money, on=["start_tick", "steamid"], how="left")
        .join(bought.drop("name", strict=False), on=["buy_tick", "steamid"], how="left")
        .drop("start_tick", "buy_tick")
        .sort("round", "steamid")
    )
