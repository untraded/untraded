# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The `shot` table: one row per `weapon_fire`, with the shooter's state at that tick.

No v1 metric reads it: it is kept for aim and movement metrics later, since a deleted demo
cannot be parsed again (docs/canonical-tables.md § 4).
"""

from __future__ import annotations

import polars as pl

from untraded.parsing._context import Context, steamid
from untraded.parsing.schema import SHOT

SHOT_PROPS = [
    "X",
    "Y",
    "Z",
    "pitch",
    "yaw",
    "velocity_X",
    "velocity_Y",
    "velocity_Z",
    "is_scoped",
    "ducking",
    "is_airborne",
    "is_walking",
    "accuracy_penalty",
]


def build_shots(ctx: Context) -> pl.DataFrame:
    if "weapon_fire" not in ctx.events:
        ctx.unavailable.append("shot: no weapon_fire event")
        return pl.DataFrame(schema=SHOT)
    fired = ctx.in_rounds(ctx.event("weapon_fire", player=SHOT_PROPS))
    return fired.select(
        "tick",
        "round",
        steamid("user_steamid").alias("shooter"),
        pl.col("weapon").fill_null("").str.strip_prefix("weapon_"),
        pl.col("silenced").fill_null(False),
        *(pl.col(f"user_{prop}").alias(prop.lower()) for prop in SHOT_PROPS),
    )
