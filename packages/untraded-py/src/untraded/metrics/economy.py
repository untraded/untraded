# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""§ 5 Economy (docs/metrics-v1.md).

Buy types come from the round model (`team_round.buy_type`, thresholds in `BuyThresholds`); the
dataset carries them on each kept round, so `Dataset.split(buy=...)` works for every metric.
"""

from __future__ import annotations

from collections.abc import Mapping

import polars as pl

from untraded.metrics._helpers import per_player
from untraded.metrics.dataset import Dataset
from untraded.metrics.registry import ParamValue, metric

WEAPON_CLASSES = {
    "awp": ("AWP",),
    "rifle": (
        "AK-47",
        "M4A4",
        "M4A1-S",
        "Galil AR",
        "FAMAS",
        "SG 553",
        "AUG",
        "SSG 08",
        "G3SG1",
        "SCAR-20",
    ),
    "heavy": ("Nova", "XM1014", "MAG-7", "Sawed-Off", "M249", "Negev"),
    "smg": ("MAC-10", "MP9", "MP7", "MP5-SD", "UMP-45", "P90", "PP-Bizon"),
}
"""Best weapon held, in this order; anything else (pistols, knife, nothing) is `pistol`."""


def _rounds_won(ds: Dataset, *keys: str) -> pl.DataFrame:
    """Kept rounds per player and `keys`, with the % the player's team won."""
    rows = ds.played.join(
        ds["round_player"].select("match_id", "round", "steamid", "team_won"),
        on=["match_id", "round", "steamid"],
    )
    return (
        rows.group_by("steamid", *keys)
        .agg(pl.len().alias("rounds"), (pl.col("team_won").mean() * 100).alias("win_pct"))
        .sort("steamid", *keys)
    )


@metric(
    "eco.buy_type",
    version="1.0.0",
    name="Buy type",
    unit="table",
    kind="table",
    uses=("team_round", "round_player"),
    doc="Rounds played per team buy type (`pistol`, `eco`, `semi`, `force`, `full`), with the "
    "% won. The buy type is also a split: `Dataset.split(buy=...)`. Columns: `steamid`, "
    "`buy_type`, `rounds`, `win_pct`.",
)
def buy_type(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return _rounds_won(ds, "buy_type")


@metric(
    "eco.win_pct_by_matchup",
    version="1.0.0",
    name="Win % by economy",
    unit="table",
    kind="table",
    uses=("team_round", "round_player"),
    doc="% of rounds won per (team buy type, opponent buy type) pair. Columns: `steamid`, "
    "`buy_type`, `opponent_buy_type`, `rounds`, `win_pct`.",
)
def win_pct_by_matchup(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return _rounds_won(ds, "buy_type", "opponent_buy_type")


@metric(
    "eco.equipment_lost_at_death",
    version="1.0.0",
    name="Equipment lost",
    unit="dollars",
    uses=("death", "kill"),
    doc="The player's equipment value at the tick of death, averaged over their deaths.",
)
def equipment_lost_at_death(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    deaths = ds["death"].join(
        ds["kill"].select("match_id", "tick", "victim", "victim_equip_value"),
        on=["match_id", "tick", "victim"],
    )
    kept = ds.kept(deaths, player="victim")
    mean = kept.group_by(pl.col("victim").alias("steamid")).agg(
        pl.col("victim_equip_value").mean().alias("value")
    )
    return per_player(ds, mean, fill=None)


def _weapon_class(inventory: pl.Expr) -> pl.Expr:
    expr = pl.lit("pistol")
    for name, weapons in reversed(WEAPON_CLASSES.items()):
        held = inventory.list.eval(pl.element().is_in(weapons)).list.any()
        expr = pl.when(held).then(pl.lit(name)).otherwise(expr)
    return expr


@metric(
    "eco.kills_vs_buy",
    version="1.0.0",
    name="Kills by economy",
    unit="table",
    kind="table",
    uses=("death", "kill", "inventory_change"),
    doc="The player's enemy kills per (killer weapon class, victim weapon class). The class is "
    "the best weapon held: `awp`, `rifle` (other snipers included), `heavy` (shotguns and "
    "machine guns), `smg`, else `pistol`. The killer's inventory is the last change before "
    "the kill, the victim's is read at the kill. Columns: `steamid`, `killer_class`, "
    "`victim_class`, `kills`.",
)
def kills_vs_buy(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    kills = (
        ds["death"]
        .filter(pl.col("is_enemy_kill"))
        .join(
            ds["kill"].select("match_id", "tick", "victim", "victim_inventory"),
            on=["match_id", "tick", "victim"],
        )
        .sort("tick")
    )
    inventories = (
        ds["inventory_change"]
        .select("match_id", "tick", pl.col("steamid").alias("killer"), "inventory")
        .sort("tick")
    )
    with_killer = kills.join_asof(
        inventories,
        on="tick",
        by=["match_id", "killer"],
        strategy="backward",
        check_sortedness=False,  # both sides are sorted by tick above
    )
    classes = ds.kept(with_killer, player="killer").select(
        pl.col("killer").alias("steamid"),
        _weapon_class(pl.col("inventory").fill_null([])).alias("killer_class"),
        _weapon_class(pl.col("victim_inventory")).alias("victim_class"),
    )
    return (
        classes.group_by("steamid", "killer_class", "victim_class")
        .agg(pl.len().alias("kills"))
        .sort("steamid", "killer_class", "victim_class")
    )
