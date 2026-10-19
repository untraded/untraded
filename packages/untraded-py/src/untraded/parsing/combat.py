# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The `damage` and `blind` tables."""

from __future__ import annotations

import polars as pl

from untraded.parsing._context import Context, side, steamid
from untraded.parsing.core import hitgroup
from untraded.parsing.schema import BLIND, DAMAGE

FULL_HEALTH = 100


def build_damage(ctx: Context) -> pl.DataFrame:
    if "player_hurt" not in ctx.events:
        ctx.unavailable.append("damage: no player_hurt event")
        return pl.DataFrame(schema=DAMAGE)
    raw = ctx.in_rounds(ctx.event("player_hurt", player=["team_num"]))
    hurts = raw.with_row_index("order").select(
        "order",
        "tick",
        "round",
        steamid("attacker_steamid").alias("attacker"),
        steamid("user_steamid").alias("victim"),
        pl.col("weapon").fill_null(""),
        hitgroup("hitgroup").alias("hitgroup"),
        pl.col("dmg_health"),
        pl.col("dmg_armor"),
        pl.col("health").alias("health_after"),
        pl.col("armor").alias("armor_after"),
        side("attacker_team_num").alias("attacker_side"),
        side("user_team_num").alias("victim_side"),
    )
    return capped_damage(hurts).drop("order", "attacker_side", "victim_side")


def capped_damage(hurts: pl.DataFrame) -> pl.DataFrame:
    """Adds `damage` (the health the hit removed) and `is_team_damage`, sorted by tick.

    Health only goes down within a round and starts at 100, so the health before a hit is the
    health after the previous hit on the same victim in that round. The `health` prop at the
    event tick is not reliable for this (already updated in about a third of the hits). The
    damage is the health lost, `health before - health after`: `dmg_health` is rounded down
    while health drops by whole points, so it is often one point short (CS Demo Manager also
    counts the health lost). Without `health_after`, it falls back to `min(dmg_health, health
    before)`.
    """
    before = (
        pl.col("health_after").shift(1).over("round", "victim", order_by=["tick", "order"])
    ).fill_null(FULL_HEALTH)
    return (
        hurts.with_columns(
            pl.when(pl.col("health_after").is_not_null())
            .then(before - pl.col("health_after"))
            .otherwise(pl.min_horizontal("dmg_health", before))
            .clip(0)
            .alias("damage")
        )
        .with_columns(
            (
                (pl.col("attacker") != pl.col("victim"))
                & (pl.col("attacker_side") == pl.col("victim_side"))
            )
            .fill_null(False)
            .alias("is_team_damage"),
            pl.lit(None, pl.Int32).alias("grenade_id"),
        )
        .sort("tick", "order")
    )


def build_blind(ctx: Context) -> pl.DataFrame:
    detonations = ctx.event("flashbang_detonate")
    if "player_blind" in ctx.events:
        blinds = ctx.event("player_blind").select(
            "tick",
            steamid("user_steamid").alias("victim"),
            steamid("attacker_steamid").alias("flasher"),
            pl.col("blind_duration").alias("duration"),
            pl.lit(False).alias("from_fallback"),
        )
    elif detonations.height:
        blinds = _blinds_from_flash_duration(ctx, detonations)
    else:
        if "flashbang_detonate" not in ctx.events:
            ctx.unavailable.append("blind: no player_blind nor flashbang_detonate event")
        return pl.DataFrame(schema=BLIND)

    blinds = ctx.in_rounds(blinds)
    sides = ctx.ticks(["team_num"], blinds["tick"].to_list()).select(
        "tick", "steamid", side("team_num").alias("side")
    )
    return (
        blinds.join(
            sides.rename({"steamid": "victim", "side": "victim_side"}),
            on=["tick", "victim"],
            how="left",
        )
        .join(
            sides.rename({"steamid": "flasher", "side": "flasher_side"}),
            on=["tick", "flasher"],
            how="left",
        )
        .with_columns(
            (pl.col("victim") == pl.col("flasher")).fill_null(False).alias("is_self"),
            pl.lit(None, pl.Int32).alias("grenade_id"),
        )
        .with_columns(
            (~pl.col("is_self") & (pl.col("victim_side") == pl.col("flasher_side")))
            .fill_null(False)
            .alias("is_teammate")
        )
        .drop("victim_side", "flasher_side")
        .sort("tick", "victim")
    )


def _blinds_from_flash_duration(ctx: Context, detonations: pl.DataFrame) -> pl.DataFrame:
    """ADR 0008 fallback: `flash_duration` rises on every blinded player at the detonation tick.

    Checked against `player_blind` on a matchmaking demo: same tick and same duration for 156 of
    161 blinds; the others were already blinded by an earlier flash.
    """
    ticks = detonations["tick"].to_list()
    before = ctx.ticks(["flash_duration"], [t - 1 for t in ticks]).select(
        (pl.col("tick") + 1).alias("tick"), "steamid", pl.col("flash_duration").alias("before")
    )
    after = ctx.ticks(["flash_duration"], ticks)
    # Several flashes detonating on the same tick cannot be told apart: credit the first thrower.
    throwers = detonations.group_by("tick").agg(steamid("user_steamid").first().alias("flasher"))
    return (
        after.join(before, on=["tick", "steamid"], how="left")
        .filter(pl.col("flash_duration") > pl.col("before").fill_null(0) + 1e-3)
        .join(throwers, on="tick", how="left")
        .select(
            "tick",
            pl.col("steamid").alias("victim"),
            "flasher",
            pl.col("flash_duration").alias("duration"),
            pl.lit(True).alias("from_fallback"),
        )
    )
