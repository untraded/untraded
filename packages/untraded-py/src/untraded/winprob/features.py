# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The state of a round, as the win-probability model sees it.

One sample per `step` seconds of play (from freeze-time end), seen by the counter-terrorists:
who is alive, their health, armor, equipment and kits, whether the bomb is down and the time
left. The target is whether the counter-terrorists win the round. A sample is kept while the
round is still open: both sides have someone alive (or only the counter-terrorists do while the
bomb is down: they can still defuse), and the bomb has neither been defused nor exploded.

Model 2 adds what the living carry (AWPs, rifles, other primaries, grenades, from
`inventory_change`), two bends in the round clock, and the defuse race: once the bomb is down,
the seconds left on it minus the time the quickest living counter-terrorist needs to reach it
(straight-line distance at knife speed) and defuse it.

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
RUN_SPEED = 250.0
"""Units per second, knife out: how fast a counter-terrorist runs to the bomb."""
DEFUSE_SECONDS = 10.0
DEFUSE_KIT_SECONDS = 5.0
DEFUSE_MARGIN_CAP = 20.0
"""The defuse race is clipped to plus or minus this many seconds: beyond, it is decided."""

AWPS = ("AWP",)
RIFLES = (
    "AK-47",
    "M4A4",
    "M4A1-S",
    "AUG",
    "SG 553",
    "Galil AR",
    "FAMAS",
    "SCAR-20",
    "G3SG1",
)
OTHER_PRIMARIES = (
    "SSG 08",
    "MP7",
    "MP9",
    "MAC-10",
    "MP5-SD",
    "UMP-45",
    "P90",
    "PP-Bizon",
    "XM1014",
    "Nova",
    "MAG-7",
    "Sawed-Off",
    "Negev",
    "M249",
)
CARRIED: Mapping[str, tuple[str, ...]] = {
    "awp": AWPS,
    "rifles": RIFLES,
    "smgs": OTHER_PRIMARIES,
    "smokes": ("Smoke Grenade",),
    "flashes": ("Flashbang",),
    "fires": ("Molotov", "Incendiary Grenade"),
    "hes": ("High Explosive Grenade",),
}
"""What the living carry, counted per side: inventory names as the parser writes them (a grenade
held twice is listed twice)."""

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
"""Model 1's inputs besides the map. Health and armor are in hundreds of points, equipment in
thousands of dollars, times in tens of seconds; `*_planted` are those values while the bomb is
down (zero before), so the model can weigh them differently after the plant."""

TIME_BENDS = (3.0, 6.0)
"""Where the round clock may bend, in tens of seconds left before the plant."""

NUMERIC_V2 = [
    *NUMERIC,
    *(f"{name}_{side}" for name in CARRIED for side in ("ct", "t")),
    *(f"time_left_over_{int(bend * 10)}s" for bend in TIME_BENDS),
    "defuse_margin",
]
"""Model 2's inputs besides the map: model 1's, the counts of what the living carry, the clock's
bends (`max(0, time_left - bend)`) and the defuse race (tens of seconds, positive when the
quickest counter-terrorist would make it, zero before the plant)."""

FEATURE_SETS: Mapping[str, list[str]] = {"v1": NUMERIC, "v2": NUMERIC_V2}

CANDIDATES: Mapping[str, list[str]] = {
    "defuse_race": ["defuse_margin"],
    "clock_bends": [f"time_left_over_{int(bend * 10)}s" for bend in TIME_BENDS],
    "weapons": [f"{n}_{s}" for n in ("awp", "rifles", "smgs") for s in ("ct", "t")],
    "grenades": [f"{n}_{s}" for n in ("smokes", "flashes", "fires", "hes") for s in ("ct", "t")],
}
"""Model 2's feature families on top of model 1's: each is kept only if it earns its place on
the corpus (`untraded.winprob.validation.select_features`)."""

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
    **{f"{name}_ct": 1 for name in CARRIED},
    **{f"{name}_t": -1 for name in CARRIED},
    "defuse_margin": 1,
}
"""Signs the model must respect (counter-terrorists' point of view): one more player, more health,
armor, equipment, weapons or grenades never lowers their side's chances, nor does a better defuse
race. The others are left to the data."""


def _carried(ticks: pl.DataFrame, tables: Mapping[str, pl.DataFrame]) -> pl.DataFrame:
    """`ticks` with each player's counts of `CARRIED` items at that tick: their last inventory
    change at or before it (zero when the match has no `inventory_change`)."""
    changes = tables.get("inventory_change")
    if changes is None or changes.is_empty():
        return ticks.with_columns(pl.lit(0).alias(name) for name in CARRIED)
    # Counted on the changes (a small table) before the join, so that no inventory list is
    # copied onto every sampled tick.
    counts = changes.select(
        pl.col("tick").cast(pl.Int32),
        pl.col("steamid"),
        *(
            pl.col("inventory").list.eval(pl.element().is_in(list(items))).list.sum().alias(name)
            for name, items in CARRIED.items()
        ),
    ).sort("tick")
    joined = (
        ticks.with_columns(pl.col("tick").cast(pl.Int32))
        .sort("tick")
        .join_asof(counts, on="tick", by="steamid", strategy="backward", check_sortedness=False)
    )
    return joined.with_columns(pl.col(name).fill_null(0) for name in CARRIED)


def _bomb_spots(tables: Mapping[str, pl.DataFrame]) -> pl.DataFrame:
    """Where the bomb went down in each round: the planter's last position before the plant."""
    schema = pl.Schema(
        {"round": pl.Int16, "bomb_x": pl.Float64, "bomb_y": pl.Float64, "bomb_z": pl.Float64}
    )
    planters = (
        tables["round"]
        .filter(pl.col("bomb_planted_tick").is_not_null(), pl.col("bomb_planter").is_not_null())
        .select("round", "bomb_planter", "bomb_planted_tick")
    )
    if planters.is_empty():
        return pl.DataFrame(schema=schema)
    return (
        tables["player_tick"]
        .join(planters, left_on=["round", "steamid"], right_on=["round", "bomb_planter"])
        .filter(pl.col("tick") <= pl.col("bomb_planted_tick"))
        .sort("tick")
        .group_by("round")
        .agg(
            pl.col("x").last().alias("bomb_x"),
            pl.col("y").last().alias("bomb_y"),
            pl.col("z").last().alias("bomb_z"),
        )
        .cast(schema)
    )


def _per_side(ticks: pl.DataFrame, tables: Mapping[str, pl.DataFrame]) -> pl.DataFrame:
    """Team totals per round and tick, from `player_tick` rows: alive, health, armor, equipment
    and `CARRIED` items of the living, kits of living counter-terrorists, and the seconds the
    quickest of them needs to reach the bomb and defuse it (null before the plant)."""
    rows = _carried(ticks, tables).join(_bomb_spots(tables), on="round", how="left")
    alive = pl.col("is_alive")
    ct, t = pl.col("side") == "CT", pl.col("side") == "T"
    distance = (
        (pl.col("x") - pl.col("bomb_x")) ** 2
        + (pl.col("y") - pl.col("bomb_y")) ** 2
        + (pl.col("z") - pl.col("bomb_z")) ** 2
    ).sqrt()
    defuse = pl.when(pl.col("has_defuser")).then(DEFUSE_KIT_SECONDS).otherwise(DEFUSE_SECONDS)
    # A position the demo got wrong (NaN) does not run the race.
    need = (distance / RUN_SPEED + defuse).fill_nan(None)
    return rows.group_by("round", "tick").agg(
        (alive & ct).sum().alias("alive_ct"),
        (alive & t).sum().alias("alive_t"),
        pl.col("health").filter(alive & ct).sum().alias("hp_ct"),
        pl.col("health").filter(alive & t).sum().alias("hp_t"),
        pl.col("armor").filter(alive & ct).sum().alias("armor_ct"),
        pl.col("armor").filter(alive & t).sum().alias("armor_t"),
        pl.col("equip_value").filter(alive & ct).sum().alias("equip_ct"),
        pl.col("equip_value").filter(alive & t).sum().alias("equip_t"),
        (alive & ct & pl.col("has_defuser")).sum().alias("kits"),
        *(pl.col(name).filter(alive & ct).sum().alias(f"{name}_ct") for name in CARRIED),
        *(pl.col(name).filter(alive & t).sum().alias(f"{name}_t") for name in CARRIED),
        need.filter(alive & ct).min().alias("defuse_need"),
    )


def _finish(frame: pl.DataFrame, tickrate: float) -> pl.DataFrame:
    """Scaled features from team totals and the round's timing (`freeze_end_tick`,
    `bomb_planted_tick` on each row)."""
    planted = pl.col("bomb_planted_tick").is_not_null() & (
        pl.col("tick") >= pl.col("bomb_planted_tick")
    )
    elapsed = (pl.col("tick") - pl.col("freeze_end_tick")) / tickrate
    since_plant = (pl.col("tick") - pl.col("bomb_planted_tick")) / tickrate
    bomb_left = (BOMB_SECONDS - since_plant).clip(0)
    time_left = pl.when(planted).then(bomb_left).otherwise((ROUND_SECONDS - elapsed).clip(0)) / 10
    margin = (bomb_left - pl.col("defuse_need")).clip(-DEFUSE_MARGIN_CAP, DEFUSE_MARGIN_CAP) / 10
    finished = frame.with_columns(
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
        pl.when(planted).then(margin.fill_null(0.0)).otherwise(0.0).alias("defuse_margin"),
    )
    return finished.with_columns(
        (pl.col("time_left") - bend).clip(0).alias(f"time_left_over_{int(bend * 10)}s")
        for bend in TIME_BENDS
    ).with_columns(pl.col(NUMERIC_V2).cast(pl.Float64).fill_nan(0.0))


def samples(tables: Mapping[str, pl.DataFrame], step: float = 1.0) -> pl.DataFrame:
    """The open states of every round of a match, one per `step` seconds: `match_id`, `map`,
    `played_at`, `round`, `tick`, the `NUMERIC_V2` features (model 1's `NUMERIC` among them) and
    `ct_won`."""
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
    sides = _per_side(ticks.join(chosen, on=["round", "tick"]), tables)
    frame = _finish(sides.join(timing, on="round"), tickrate)
    still_open = (pl.col("alive_ct") > 0) & ((pl.col("alive_t") > 0) | (pl.col("planted") > 0))
    return (
        frame.filter(still_open)
        .with_columns(
            pl.lit(match["match_id"]).alias("match_id"),
            pl.lit(match["map"]).alias("map"),
            pl.lit(match["played_at"]).cast(pl.Date).alias("played_at"),
        )
        .select("match_id", "map", "played_at", "round", "tick", *NUMERIC_V2, "ct_won")
        .sort("round", "tick")
    )


def state_at(
    tables: Mapping[str, pl.DataFrame],
    round_number: int,
    tick: int,
    *,
    without: int | None = None,
    planted: bool = False,
) -> pl.DataFrame:
    """The features of one round just before `tick` (the last `player_tick` sample before it):
    one row, before any change the event at `tick` makes.

    For the state just after an event: `without` takes a player out (a kill: their health,
    armor, equipment, kit and what they carry go with them, and the defuse race is run again
    without them); `planted` puts the bomb down where its planter stands, with its whole timer
    to go."""
    match = tables["match"].row(0, named=True)
    rnd = tables["round"].filter(pl.col("round") == round_number)
    ticks = tables["player_tick"].filter(pl.col("round") == round_number, pl.col("tick") < tick)
    if ticks.is_empty() or rnd.is_empty():
        raise ValueError(f"no state before tick {tick} of round {round_number}")
    if planted:
        rnd = rnd.with_columns(pl.lit(tick - 1).cast(pl.Int32).alias("bomb_planted_tick"))
    last = ticks.filter(pl.col("tick") == pl.col("tick").max())
    if without is not None:
        last = last.with_columns(pl.col("is_alive") & (pl.col("steamid") != without))
    # This round's rows only: the bomb spot is looked up for every event of a match.
    scoped = {**tables, "round": rnd, "player_tick": ticks}
    # Timed one tick before the event: a plant at `tick` is not down yet in the state before it.
    sides = _per_side(last, scoped).with_columns(pl.lit(tick - 1).cast(pl.Int32).alias("tick"))
    frame = sides.join(rnd.select("round", "freeze_end_tick", "bomb_planted_tick"), on="round")
    return _finish(frame, float(match["tickrate"])).with_columns(pl.lit(match["map"]).alias("map"))
