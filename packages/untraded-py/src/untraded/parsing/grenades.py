# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The `grenade` and `grenade_path` tables, and the `grenade_id` links of `damage` and `blind`.

`parse_grenades` returns grenades held in hand (no position) and projectiles in flight. Each
throw is one run of consecutive ticks of a projectile entity: entity ids are reused during a
match. Checked on a matchmaking demo (520 throws): every HE, smoke, flash and decoy detonation
event carries its projectile's entity id; a molotov's `inferno_startburn` carries the fire's own
entity id and comes exactly one tick after its projectile, from the same thrower; `weapon_fire`
tells molotovs from incendiaries.
"""

from __future__ import annotations

import polars as pl

from untraded.parsing._context import Context, frame, side, steamid
from untraded.parsing.schema import GRENADE, GRENADE_PATH

PATH_HZ = 16
"""⚙ Trajectory sampling rate of `grenade_path` (docs/canonical-tables.md § 4)."""

PROJECTILES = {
    "CHEGrenadeProjectile": "he",
    "CFlashbangProjectile": "flash",
    "CSmokeGrenadeProjectile": "smoke",
    "CMolotovProjectile": "molotov",  # or incendiary, from weapon_fire
    "CDecoyProjectile": "decoy",
}
DETONATIONS = {
    "he": "hegrenade_detonate",
    "flash": "flashbang_detonate",
    "smoke": "smokegrenade_detonate",
    "decoy": "decoy_started",
}
# player_hurt weapon -> grenade types that can cause it
DAMAGE_WEAPONS = {
    "hegrenade": ["he"],
    "inferno": ["molotov", "incendiary"],
    "molotov": ["molotov", "incendiary"],
    "incgrenade": ["molotov", "incendiary"],
    "smokegrenade": ["smoke"],
    "flashbang": ["flash"],
    "decoy": ["decoy"],
}
LINK_SLACK_SECONDS = 1.0


def build_grenades(ctx: Context) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Returns (`grenade`, `grenade_path`)."""
    raw = frame(ctx.parser.parse_grenades())
    flying = raw.filter(
        pl.col("grenade_type").is_in(list(PROJECTILES)) & pl.col("x").is_not_null()
    ).select(
        pl.col("grenade_type").replace_strict(PROJECTILES).alias("type"),
        pl.col("grenade_entity_id").alias("entity_id"),
        pl.col("tick").cast(pl.Int32),
        pl.col("steamid").cast(pl.UInt64).alias("thrower"),
        "x",
        "y",
        "z",
    )
    if not flying.height:
        ctx.unavailable.append("grenade: no projectile in the demo")
        return pl.DataFrame(schema=GRENADE), pl.DataFrame(schema=GRENADE_PATH)

    points = flying.sort("entity_id", "tick").with_columns(
        (pl.col("tick").diff().over("entity_id").fill_null(2) > 1).cum_sum().alias("throw")
    )
    throws = (
        points.group_by("throw")
        .agg(
            pl.col("type", "entity_id", "thrower").first(),
            pl.col("tick").first().alias("throw_tick"),
            pl.col("tick").last().alias("last_tick"),
            pl.col("x").first().alias("throw_x"),
            pl.col("y").first().alias("throw_y"),
            pl.col("z").first().alias("throw_z"),
            pl.col("x").last().alias("last_x"),
            pl.col("y").last().alias("last_y"),
            pl.col("z").last().alias("last_z"),
        )
        .sort("throw_tick", "entity_id")
        .with_columns(pl.int_range(1, pl.len() + 1, dtype=pl.Int32).alias("grenade_id"))
    )
    throws = _molotov_or_incendiary(ctx, throws)
    throws = _detonations(ctx, throws)
    throws = ctx.in_rounds(throws.with_columns(pl.col("throw_tick").alias("tick"))).drop("tick")
    sides = ctx.ticks(["team_num"], throws["throw_tick"].to_list()).select(
        pl.col("tick").alias("throw_tick"),
        pl.col("steamid").alias("thrower"),
        side("team_num").alias("side"),
    )
    grenades = throws.join(sides, on=["throw_tick", "thrower"], how="left").sort("throw_tick")

    step = max(1, round(ctx.tickrate / PATH_HZ))
    path = (
        points.join(grenades.select("throw", "grenade_id", "throw_tick", "path_end"), on="throw")
        .filter(pl.col("tick") <= pl.col("path_end"))
        .filter(
            ((pl.col("tick") - pl.col("throw_tick")) % step == 0)
            | (pl.col("tick") == pl.col("tick").max().over("grenade_id"))
        )
        .select("grenade_id", "tick", "x", "y", "z")
        .sort("tick", "grenade_id")
    )
    return grenades.drop("throw", "last_x", "last_y", "last_z", "path_end"), path


def _molotov_or_incendiary(ctx: Context, throws: pl.DataFrame) -> pl.DataFrame:
    fired = (
        ctx.event("weapon_fire")
        .filter(pl.col("weapon").is_in(["weapon_molotov", "weapon_incgrenade"]))
        .select(
            pl.col("tick").alias("fire_tick"),
            steamid("user_steamid").alias("thrower"),
            pl.when(pl.col("weapon") == "weapon_incgrenade")
            .then(pl.lit("incendiary"))
            .otherwise(pl.lit("molotov"))
            .alias("fired"),
        )
        .sort("fire_tick")
        if "weapon_fire" in ctx.events
        else pl.DataFrame(schema={"fire_tick": pl.Int32, "thrower": pl.UInt64, "fired": pl.String})
    )
    return (
        throws.sort("throw_tick")
        .join_asof(
            fired,
            left_on="throw_tick",
            right_on="fire_tick",
            by="thrower",
            strategy="backward",
            tolerance=round(ctx.tickrate),
            check_sortedness=False,  # sorted on the asof key; groups cannot be checked
        )
        .with_columns(
            pl.when(pl.col("type") == "molotov")
            .then(pl.col("fired").fill_null("molotov"))
            .otherwise(pl.col("type"))
            .alias("type")
        )
        .drop("fire_tick", "fired")
    )


def _detonations(ctx: Context, throws: pl.DataFrame) -> pl.DataFrame:
    """Adds detonate_tick/x/y/z, end_tick and path_end (last trajectory point kept)."""
    found = []
    for kind, name in DETONATIONS.items():
        if name not in ctx.events:
            continue
        found.append(
            ctx.event(name).select(
                pl.lit(kind).alias("type"),
                pl.col("entityid").alias("entity_id"),
                pl.col("tick").alias("detonate_tick"),
                pl.col("x").alias("detonate_x"),
                pl.col("y").alias("detonate_y"),
                pl.col("z").alias("detonate_z"),
            )
        )
    by_entity = (
        pl.concat(found)
        if found
        else pl.DataFrame(
            schema={"type": pl.String, "entity_id": pl.Int32, "detonate_tick": pl.Int32}
            | dict.fromkeys(["detonate_x", "detonate_y", "detonate_z"], pl.Float32)
        )
    )
    # A detonation belongs to the throw of the same entity whose run holds it (flashes: +1 tick).
    matched = (
        throws.join(by_entity, on=["type", "entity_id"], how="left")
        .filter(pl.col("detonate_tick").is_between(pl.col("throw_tick"), pl.col("last_tick") + 2))
        .sort("grenade_id", "detonate_tick")
        .unique("grenade_id", keep="first")
    )
    throws = throws.join(
        matched.select("grenade_id", pl.selectors.starts_with("detonate_")),
        on="grenade_id",
        how="left",
    )

    # Molotovs: the fire starts one tick after the projectile ends, from the same thrower.
    burns = (
        ctx.event("inferno_startburn").select(
            pl.col("tick").alias("burn_tick"),
            steamid("user_steamid").alias("thrower"),
            pl.col("entityid").alias("fire_id"),
            "x",
            "y",
            "z",
        )
        if "inferno_startburn" in ctx.events
        else None
    )
    if burns is not None and burns.height:
        fire = (
            throws.filter(pl.col("type").is_in(["molotov", "incendiary"]))
            .select("grenade_id", "thrower", "last_tick")
            .join(burns, on="thrower")
            .filter(pl.col("burn_tick").is_between(pl.col("last_tick"), pl.col("last_tick") + 2))
            .sort("grenade_id", "burn_tick")
            .unique("grenade_id", keep="first")
        )
        expire = _ends(
            ctx, "inferno_expire", fire.select("fire_id", "burn_tick"), "fire_id", "burn_tick"
        )
        fire = fire.join(expire, on=["fire_id", "burn_tick"], how="left")
        throws = throws.join(
            fire.select(
                "grenade_id",
                pl.col("burn_tick").alias("burn_detonate_tick"),
                pl.col("x").alias("burn_x"),
                pl.col("y").alias("burn_y"),
                pl.col("z").alias("burn_z"),
                pl.col("end_tick").alias("fire_end_tick"),
            ),
            on="grenade_id",
            how="left",
        ).with_columns(
            pl.coalesce("detonate_tick", "burn_detonate_tick").alias("detonate_tick"),
            pl.coalesce("detonate_x", "burn_x").alias("detonate_x"),
            pl.coalesce("detonate_y", "burn_y").alias("detonate_y"),
            pl.coalesce("detonate_z", "burn_z").alias("detonate_z"),
        )
    else:
        throws = throws.with_columns(pl.lit(None, pl.Int32).alias("fire_end_tick"))

    smoke_end = _ends(
        ctx,
        "smokegrenade_expired",
        throws.filter(pl.col("type") == "smoke")
        .select("grenade_id", "entity_id", "detonate_tick")
        .drop_nulls(),
        "entity_id",
        "detonate_tick",
    ).select("grenade_id", "end_tick")
    throws = throws.join(smoke_end, on="grenade_id", how="left")
    return throws.with_columns(
        # no detonation event (e.g. a molotov put out in the air): the last trajectory point
        pl.coalesce("detonate_x", "last_x").alias("detonate_x"),
        pl.coalesce("detonate_y", "last_y").alias("detonate_y"),
        pl.coalesce("detonate_z", "last_z").alias("detonate_z"),
        pl.coalesce("detonate_tick", "last_tick").alias("detonate_tick"),
        pl.coalesce("end_tick", "fire_end_tick").alias("end_tick"),
        pl.min_horizontal("last_tick", pl.coalesce("detonate_tick", "last_tick")).alias("path_end"),
    ).drop("last_tick", "fire_end_tick", pl.selectors.starts_with("burn_"), strict=False)


def _ends(ctx: Context, event: str, starts: pl.DataFrame, key: str, start: str) -> pl.DataFrame:
    """`end_tick` of each start: the first `event` of the same entity after it."""
    if event not in ctx.events or not starts.height:
        return starts.with_columns(pl.lit(None, pl.Int32).alias("end_tick"))
    ends = ctx.event(event).select(pl.col("entityid").alias(key), pl.col("tick").alias("end_tick"))
    return starts.sort(start).join_asof(
        ends.sort("end_tick"),
        left_on=start,
        right_on="end_tick",
        by=key,
        strategy="forward",
        check_sortedness=False,
    )


def link_grenades(
    damage: pl.DataFrame, blind: pl.DataFrame, grenades: pl.DataFrame, *, tickrate: float
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Fills `grenade_id` in `damage` (HE and fire) and `blind` (flash of the same detonation)."""
    if not grenades.height:
        return damage, blind
    slack = round(LINK_SLACK_SECONDS * tickrate)
    windows = grenades.select(
        "grenade_id",
        pl.col("thrower").alias("attacker"),
        pl.col("type").cast(pl.String),
        "throw_tick",
        (pl.coalesce("end_tick", "detonate_tick") + slack).alias("until"),
    )
    hits = (
        damage.with_row_index("row")
        .filter(pl.col("weapon").is_in(list(DAMAGE_WEAPONS)))
        .select("row", "tick", "attacker", "weapon")
        .with_columns(pl.col("weapon").replace_strict(DAMAGE_WEAPONS).alias("types"))
        .explode("types")
        .join(windows, left_on=["attacker", "types"], right_on=["attacker", "type"])
        .filter(pl.col("tick").is_between(pl.col("throw_tick"), pl.col("until")))
        .sort("throw_tick", descending=True)
        .unique("row", keep="first")
        .select("row", pl.col("grenade_id").alias("linked"))
    )
    damage = (
        damage.with_row_index("row")
        .join(hits, on="row", how="left")
        .with_columns(pl.coalesce("grenade_id", "linked").alias("grenade_id"))
        .drop("row", "linked")
    )

    flashes = (
        grenades.filter(pl.col("type") == "flash")
        .select(
            pl.col("detonate_tick").alias("tick"),
            pl.col("thrower").alias("flasher"),
            pl.col("grenade_id").alias("linked"),
        )
        .unique(["tick", "flasher"], keep="first")
    )
    blind = (
        blind.join(flashes, on=["tick", "flasher"], how="left")
        .with_columns(pl.coalesce("grenade_id", "linked").alias("grenade_id"))
        .drop("linked")
    )
    return damage, blind
