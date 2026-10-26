# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The state of a round, as the win-probability model sees it.

One sample per `step` seconds of play (from freeze-time end), seen by the counter-terrorists:
who is alive, their health, armor, equipment and kits, whether the bomb is down and the time
left. The target is whether the counter-terrorists win the round. A sample is kept while the
round is still open: both sides have someone alive (or only the counter-terrorists do while the
bomb is down: they can still defuse), and the bomb has neither been defused nor exploded.

`state_at` gives the same features at any tick, for the swing of an event
(`untraded.winprob.swing`).
"""

from __future__ import annotations

from collections.abc import Mapping

import polars as pl

ROUND_SECONDS = 115.0
"""Round time after freeze-time end in Premier and FACEIT (1:55)."""
BOMB_SECONDS = 40.0
"""Bomb timer once planted."""

NUMERIC = [
    "alive_ct",
    "alive_t",
    "hp_ct",
    "hp_t",
    "armor_ct",
    "armor_t",
    "equip_ct",
    "equip_t",
    "kits",
    "planted",
    "time_left",
    "time_left_planted",
    "alive_ct_planted",
    "alive_t_planted",
]
"""The model's inputs besides the map. Health and armor are in hundreds of points, equipment in
thousands of dollars, times in tens of seconds; `*_planted` are those values while the bomb is
down (zero before), so the model can weigh them differently after the plant."""

MONOTONE: Mapping[str, int] = {
    "alive_ct": 1,
    "alive_t": -1,
    "hp_ct": 1,
    "hp_t": -1,
    "armor_ct": 1,
    "armor_t": -1,
    "equip_ct": 1,
    "equip_t": -1,
    "kits": 1,
}
"""Signs the model must respect (counter-terrorists' point of view): one more player, more health,
armor or equipment never lowers their side's chances. The others are left to the data."""


def _per_side(ticks: pl.DataFrame) -> pl.DataFrame:
    """Team totals per round and tick, from `player_tick` rows: alive, health, armor and
    equipment of the living, kits of living counter-terrorists."""
    alive = pl.col("is_alive")
    ct, t = pl.col("side") == "CT", pl.col("side") == "T"
    return ticks.group_by("round", "tick").agg(
        (alive & ct).sum().alias("alive_ct"),
        (alive & t).sum().alias("alive_t"),
        pl.col("health").filter(alive & ct).sum().alias("hp_ct"),
        pl.col("health").filter(alive & t).sum().alias("hp_t"),
        pl.col("armor").filter(alive & ct).sum().alias("armor_ct"),
        pl.col("armor").filter(alive & t).sum().alias("armor_t"),
        pl.col("equip_value").filter(alive & ct).sum().alias("equip_ct"),
        pl.col("equip_value").filter(alive & t).sum().alias("equip_t"),
        (alive & ct & pl.col("has_defuser")).sum().alias("kits"),
    )


def _finish(frame: pl.DataFrame, tickrate: float) -> pl.DataFrame:
    """Scaled features from team totals and the round's timing (`freeze_end_tick`,
    `bomb_planted_tick` on each row)."""
    planted = pl.col("bomb_planted_tick").is_not_null() & (
        pl.col("tick") >= pl.col("bomb_planted_tick")
    )
    elapsed = (pl.col("tick") - pl.col("freeze_end_tick")) / tickrate
    since_plant = (pl.col("tick") - pl.col("bomb_planted_tick")) / tickrate
    time_left = (
        pl.when(planted)
        .then((BOMB_SECONDS - since_plant).clip(0))
        .otherwise((ROUND_SECONDS - elapsed).clip(0))
    ) / 10
    return frame.with_columns(
        pl.col("hp_ct") / 100,
        pl.col("hp_t") / 100,
        pl.col("armor_ct") / 100,
        pl.col("armor_t") / 100,
        pl.col("equip_ct") / 1000,
        pl.col("equip_t") / 1000,
        planted.cast(pl.Float64).alias("planted"),
        pl.when(planted).then(0.0).otherwise(time_left).alias("time_left"),
        pl.when(planted).then(time_left).otherwise(0.0).alias("time_left_planted"),
        pl.when(planted).then(pl.col("alive_ct")).otherwise(0).alias("alive_ct_planted"),
        pl.when(planted).then(pl.col("alive_t")).otherwise(0).alias("alive_t_planted"),
    ).with_columns(pl.col(NUMERIC).cast(pl.Float64))


def samples(tables: Mapping[str, pl.DataFrame], step: float = 1.0) -> pl.DataFrame:
    """The open states of every round of a match, one per `step` seconds: `match_id`, `map`,
    `played_at`, `round`, `tick`, the `NUMERIC` features and `ct_won`."""
    match = tables["match"].row(0, named=True)
    tickrate = float(match["tickrate"])
    rounds = tables["round"].filter(
        pl.col("winner_side").is_not_null()
        & pl.col("reason")
        .cast(pl.String)
        .is_in(["bomb_exploded", "bomb_defused", "elimination", "time_ran_out"])
    )
    timing = rounds.select(
        "round",
        "freeze_end_tick",
        "bomb_planted_tick",
        pl.min_horizontal("end_tick", "bomb_defused_tick", "bomb_exploded_tick").alias("over"),
        (pl.col("winner_side") == "CT").alias("ct_won"),
    )
    step_ticks = max(1, round(step * tickrate))
    ticks = (
        tables["player_tick"]
        .join(timing.select("round", "freeze_end_tick", "over"), on="round")
        .filter(pl.col("tick") >= pl.col("freeze_end_tick"), pl.col("tick") < pl.col("over"))
    )
    # One sample tick per step: the first tick of each step-long slice of the round.
    chosen = (
        ticks.select(
            "round",
            "tick",
            ((pl.col("tick") - pl.col("freeze_end_tick")) // step_ticks).alias("slice"),
        )
        .unique()
        .group_by("round", "slice")
        .agg(pl.col("tick").min())
        .select("round", "tick")
    )
    sides = _per_side(ticks.join(chosen, on=["round", "tick"]))
    frame = _finish(sides.join(timing, on="round"), tickrate)
    still_open = (pl.col("alive_ct") > 0) & ((pl.col("alive_t") > 0) | (pl.col("planted") > 0))
    return (
        frame.filter(still_open)
        .with_columns(
            pl.lit(match["match_id"]).alias("match_id"),
            pl.lit(match["map"]).alias("map"),
            pl.lit(match["played_at"]).cast(pl.Date).alias("played_at"),
        )
        .select("match_id", "map", "played_at", "round", "tick", *NUMERIC, "ct_won")
        .sort("round", "tick")
    )


def state_at(tables: Mapping[str, pl.DataFrame], round_number: int, tick: int) -> pl.DataFrame:
    """The features of one round just before `tick` (the last `player_tick` sample before it):
    one row, before any change the event at `tick` makes."""
    match = tables["match"].row(0, named=True)
    rnd = tables["round"].filter(pl.col("round") == round_number)
    ticks = tables["player_tick"].filter(pl.col("round") == round_number, pl.col("tick") < tick)
    if ticks.is_empty() or rnd.is_empty():
        raise ValueError(f"no state before tick {tick} of round {round_number}")
    last = ticks.filter(pl.col("tick") == pl.col("tick").max())
    # Timed one tick before the event: a plant at `tick` is not down yet in the state before it.
    sides = _per_side(last).with_columns(pl.lit(tick - 1).cast(pl.Int32).alias("tick"))
    frame = sides.join(rnd.select("round", "freeze_end_tick", "bomb_planted_tick"), on="round")
    return _finish(frame, float(match["tickrate"])).with_columns(pl.lit(match["map"]).alias("map"))
