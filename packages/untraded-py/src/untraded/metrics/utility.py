# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""§ 4 Utility (docs/metrics-v1.md): grenades thrown, flashes, utility damage, wasted utility.

Events count in the kept rounds of the player who caused them (thrower, flasher, attacker), or
who died (wasted utility).
"""

from __future__ import annotations

from collections.abc import Mapping

import polars as pl

from untraded.metrics._helpers import per_player, rate, rounds
from untraded.metrics.dataset import Dataset
from untraded.metrics.registry import ROUNDS, ParamValue, metric

MIN_BLIND = {"flash.min_blind_s": 1.0}
THROWN = {
    "flash": ("flash",),
    "he": ("he",),
    "molotov": ("molotov", "incendiary"),
    "smoke": ("smoke",),
    "decoy": ("decoy",),
}
FIRE_WEAPONS = ("inferno", "molotov", "incgrenade")
GRENADE_PRICES = {
    "Flashbang": 200,
    "High Explosive Grenade": 300,
    "Smoke Grenade": 300,
    "Molotov": 400,
    "Incendiary Grenade": 500,
    "Decoy Grenade": 50,
}
"""Buy prices in CS2 (names as in the `inventory` lists), for wasted utility."""


def _by(ds: Dataset, rows: pl.DataFrame, player: str, value: pl.Expr) -> pl.DataFrame:
    """`value` aggregated per player (column `player`) over their kept rounds."""
    kept = ds.kept(rows, player=player)
    return per_player(ds, kept.group_by(pl.col(player).alias("steamid")).agg(value.alias("value")))


# Grenades thrown


def _thrown(ds: Dataset, types: tuple[str, ...]) -> pl.DataFrame:
    rows = ds["grenade"].filter(pl.col("type").cast(pl.String).is_in(types))
    return _by(ds, rows, "thrower", pl.len())


def _thrown_metric(name: str, types: tuple[str, ...]) -> None:
    merged = " (molotov and incendiary merged)" if len(types) > 1 else ""

    @metric(
        f"util.thrown_{name}",
        version="1.0.0",
        name=f"{name.capitalize() if name != 'he' else 'HE'} thrown",
        unit="count",
        better="neutral",
        uses=("grenade",),
        doc=f"Grenades of type `{name}` thrown{merged}.",
    )
    def thrown(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
        return _thrown(ds, types)


for _name, _types in THROWN.items():
    _thrown_metric(_name, _types)


@metric(
    "util.thrown_per_round",
    version="1.0.0",
    name="Utility per round",
    unit="per_round",
    better="higher",
    cases=(ROUNDS,),
    uses=("grenade", "round_player"),
    doc="Grenades thrown (all types) ÷ rounds played.",
)
def thrown_per_round(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return rate(_thrown(ds, tuple(t for ts in THROWN.values() for t in ts)), rounds(ds))


# Flashes


def _blinds(ds: Dataset) -> pl.DataFrame:
    """Blinds of living players: `player_blind` also fires on players already dead, whose blind
    changes nothing."""
    deaths = ds["death"].select("match_id", "round", "victim", pl.col("tick").alias("death_tick"))
    return (
        ds["blind"]
        .join(deaths, on=["match_id", "round", "victim"], how="left")
        .filter(pl.col("death_tick").is_null() | (pl.col("tick") <= pl.col("death_tick")))
        .drop("death_tick")
    )


def _enemy_blinds(ds: Dataset) -> pl.DataFrame:
    return _blinds(ds).filter(~pl.col("is_teammate") & ~pl.col("is_self"))


def _team_blinds(ds: Dataset) -> pl.DataFrame:
    return _blinds(ds).filter(pl.col("is_teammate") & ~pl.col("is_self"))


def _long(threshold: ParamValue) -> pl.Expr:
    return pl.col("duration") >= threshold


@metric(
    "util.enemies_flashed",
    version="1.0.0",
    name="Enemies flashed",
    unit="count",
    better="higher",
    params=MIN_BLIND,
    uses=("blind", "death"),
    doc="Living enemies blinded by the player's flashes for at least `flash.min_blind_s`.",
)
def enemies_flashed(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    return _by(ds, _enemy_blinds(ds), "flasher", _long(p["flash.min_blind_s"]).sum())


@metric(
    "util.enemy_blind_time",
    version="1.0.0",
    name="Blind time dealt",
    unit="seconds",
    better="higher",
    uses=("blind", "death"),
    doc="Sum of the blind durations of living enemies (every blind, no minimum).",
)
def enemy_blind_time(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return _by(ds, _enemy_blinds(ds), "flasher", pl.col("duration").sum())


@metric(
    "util.blind_per_flash",
    version="1.0.0",
    name="Flash efficiency",
    unit="seconds",
    better="higher",
    cases=("util.thrown_flash",),
    uses=("blind", "death", "grenade"),
    doc="Enemy blind time dealt ÷ flashes thrown.",
)
def blind_per_flash(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    dealt = _by(ds, _enemy_blinds(ds), "flasher", pl.col("duration").sum())
    return rate(dealt, _thrown(ds, THROWN["flash"]))


@metric(
    "util.teammates_flashed",
    version="1.0.0",
    name="Teammates flashed",
    unit="count",
    better="lower",
    params=MIN_BLIND,
    uses=("blind", "death"),
    doc="Living teammates (not the player) blinded by the player's flashes for at least "
    "`flash.min_blind_s`.",
)
def teammates_flashed(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    return _by(ds, _team_blinds(ds), "flasher", _long(p["flash.min_blind_s"]).sum())


@metric(
    "util.team_blind_time",
    version="1.0.0",
    name="Team blind time",
    unit="seconds",
    better="lower",
    uses=("blind", "death"),
    doc="Sum of the blind durations of living teammates (every blind, no minimum).",
)
def team_blind_time(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return _by(ds, _team_blinds(ds), "flasher", pl.col("duration").sum())


def self_blinds(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    """The player's own flash blinding them for at least `flash.min_blind_s`, while alive."""
    return _blinds(ds).filter(pl.col("is_self") & _long(p["flash.min_blind_s"]))


@metric(
    "util.self_flashed",
    version="1.0.0",
    name="Self-flashes",
    unit="count",
    better="lower",
    params=MIN_BLIND,
    uses=("blind", "death"),
    doc="Times the player blinded themselves for at least `flash.min_blind_s`.",
)
def self_flashed(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    rows = _blinds(ds).filter(pl.col("is_self"))
    return _by(ds, rows, "flasher", _long(p["flash.min_blind_s"]).sum())


@metric(
    "util.flash_to_kill",
    version="1.0.0",
    name="Decisive flashes",
    unit="count",
    better="higher",
    uses=("blind", "death", "round_player", "match"),
    doc="Enemies blinded by the player and killed by the player's team (the player included) "
    "while still blind: blind tick ≤ kill tick ≤ blind tick + duration. One count per kill, "
    "for each player whose flash was still active.",
)
def flash_to_kill(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    teams = ds["round_player"].select(
        "match_id",
        "round",
        pl.col("steamid").alias("flasher"),
        pl.col("team").alias("flasher_team"),
    )
    kills = (
        ds["death"]
        .filter(pl.col("is_enemy_kill"))
        .select("match_id", "round", "victim", "killer_team", pl.col("tick").alias("kill_tick"))
    )
    tickrate = ds["match"].select("match_id", "tickrate")
    decisive = (
        _enemy_blinds(ds)
        .join(teams, on=["match_id", "round", "flasher"])
        .join(kills, on=["match_id", "round", "victim"])
        .join(tickrate, on="match_id")
        .filter(
            (pl.col("killer_team") == pl.col("flasher_team"))
            & (pl.col("kill_tick") >= pl.col("tick"))
            & (pl.col("kill_tick") <= pl.col("tick") + pl.col("duration") * pl.col("tickrate"))
        )
        .unique(["match_id", "round", "victim", "flasher"])
    )
    return _by(ds, decisive, "flasher", pl.len())


def empty_flashes(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    """Flashes that went off and blinded no living enemy for at least `flash.min_blind_s`."""
    went_off = ds["grenade"].filter(
        (pl.col("type").cast(pl.String) == "flash") & pl.col("detonate_tick").is_not_null()
    )
    landed = _enemy_blinds(ds).filter(_long(p["flash.min_blind_s"]))
    return went_off.join(
        landed.select("match_id", "grenade_id").unique(), on=["match_id", "grenade_id"], how="anti"
    )


@metric(
    "util.empty_flash_pct",
    version="1.0.0",
    name="Flashes on nobody",
    unit="pct",
    better="lower",
    cases=("util.thrown_flash",),
    params=MIN_BLIND,
    uses=("blind", "death", "grenade"),
    doc="Flashes that went off and blinded no living enemy for at least `flash.min_blind_s` ÷ "
    "flashes thrown * 100.",
)
def empty_flash_pct(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    return rate(
        _by(ds, empty_flashes(ds, p), "thrower", pl.len()),
        _thrown(ds, THROWN["flash"]),
        scale=100.0,
    )


# Utility damage


def _grenade_damage(ds: Dataset, weapons: tuple[str, ...], *, team: bool) -> pl.DataFrame:
    """Capped damage of the player's own grenades (`grenade_id` set: ownership verified, see
    demoparser2 #317), to enemies or to teammates; self-damage is neither."""
    rows = ds["damage"].filter(
        pl.col("weapon").is_in(weapons)
        & pl.col("grenade_id").is_not_null()
        & (pl.col("attacker") != pl.col("victim"))
        & (pl.col("is_team_damage") == team)
    )
    return _by(ds, rows, "attacker", pl.col("damage").sum())


@metric(
    "util.he_damage",
    version="1.0.0",
    name="HE damage",
    unit="hp",
    better="higher",
    uses=("damage",),
    doc="Capped damage of the player's HE grenades to enemies.",
)
def he_damage(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return _grenade_damage(ds, ("hegrenade",), team=False)


@metric(
    "util.he_team_damage",
    version="1.0.0",
    name="HE team damage",
    unit="hp",
    better="lower",
    uses=("damage",),
    doc="Capped damage of the player's HE grenades to teammates (self-damage excluded).",
)
def he_team_damage(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return _grenade_damage(ds, ("hegrenade",), team=True)


@metric(
    "util.fire_damage",
    version="1.0.0",
    name="Fire damage",
    unit="hp",
    better="higher",
    uses=("damage",),
    doc="Capped damage of the player's molotovs and incendiaries (fire and impact) to enemies, "
    "counting only damage linked to one of the player's own grenades (demoparser2 #317).",
)
def fire_damage(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return _grenade_damage(ds, FIRE_WEAPONS, team=False)


def he_team_hits(ds: Dataset) -> pl.DataFrame:
    """One row per HE grenade of the player's that hurt a teammate (self-damage is not one)."""
    rows = ds["damage"].filter(
        (pl.col("weapon") == "hegrenade")
        & pl.col("grenade_id").is_not_null()
        & (pl.col("attacker") != pl.col("victim"))
        & pl.col("is_team_damage")
    )
    return rows.sort("tick").unique(["match_id", "grenade_id"], keep="first", maintain_order=True)


@metric(
    "util.he_team_hits",
    version="1.0.0",
    name="HE on teammates",
    unit="count",
    better="lower",
    uses=("damage",),
    doc="The player's HE grenades that hurt at least one teammate (self-damage excluded).",
)
def he_team_hits_count(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return _by(ds, he_team_hits(ds), "attacker", pl.len())


# Wasted utility


def grenade_rounds(ds: Dataset) -> pl.DataFrame:
    """Rounds the player started with a grenade (`economy.inventory`), and which ones (`grenades`).
    A grenade picked up later does not count."""
    names = list(GRENADE_PRICES)
    held = pl.col("inventory").list.eval(pl.element().filter(pl.element().is_in(names)))
    return (
        ds["economy"].with_columns(held.alias("grenades")).filter(pl.col("grenades").list.len() > 0)
    )


def unused_grenade_rounds(ds: Dataset) -> pl.DataFrame:
    """`grenade_rounds` where the player threw no grenade at all."""
    threw = ds["grenade"].select("match_id", "round", pl.col("thrower").alias("steamid")).unique()
    return grenade_rounds(ds).join(threw, on=["match_id", "round", "steamid"], how="anti")


@metric(
    "util.grenade_rounds",
    version="1.0.0",
    name="Rounds with grenades",
    unit="count",
    better="neutral",
    uses=("economy",),
    doc="Rounds the player started with at least one grenade in the inventory.",
)
def grenade_rounds_count(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return _by(ds, grenade_rounds(ds), "steamid", pl.len())


@metric(
    "util.unused_grenade_round_pct",
    version="1.0.0",
    name="Grenades never thrown",
    unit="pct",
    better="lower",
    cases=("util.grenade_rounds",),
    uses=("economy", "grenade"),
    doc="Rounds started with a grenade where the player threw none ÷ rounds started with a "
    "grenade * 100.",
)
def unused_grenade_round_pct(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return rate(
        _by(ds, unused_grenade_rounds(ds), "steamid", pl.len()),
        _by(ds, grenade_rounds(ds), "steamid", pl.len()),
        scale=100.0,
    )


@metric(
    "util.unused_value_at_death",
    version="1.0.0",
    name="Wasted utility",
    unit="dollars",
    better="lower",
    cases=("base.deaths",),
    uses=("death", "kill"),
    doc="Buy value of the grenades in the player's inventory at death, averaged over their "
    "deaths (flash 200, HE 300, smoke 300, molotov 400, incendiary 500, decoy 50).",
)
def unused_value_at_death(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    deaths = ds["death"].join(
        ds["kill"].select("match_id", "tick", "victim", "victim_inventory"),
        on=["match_id", "tick", "victim"],
    )
    price = pl.element().replace_strict(GRENADE_PRICES, default=0, return_dtype=pl.Int64)
    items = deaths.with_columns(
        pl.col("victim_inventory").list.eval(price).list.sum().alias("wasted")
    )
    kept = ds.kept(items, player="victim")
    mean = kept.group_by(pl.col("victim").alias("steamid")).agg(pl.col("wasted").mean())
    return per_player(ds, mean.rename({"wasted": "value"}), fill=None)
