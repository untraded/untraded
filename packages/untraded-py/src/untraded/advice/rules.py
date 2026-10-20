# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The rules, batch 1: trades, spacing, opening duels, clutches, aim, utility, positioning.

Each rule's evidence applies the same filter as the metric it watches, so the events listed are
the ones the metric counts (the tests check it on the fixtures).
"""

from __future__ import annotations

from collections.abc import Mapping

import polars as pl

from untraded.advice.engine import Rule, placed, rule, standard
from untraded.metrics import Dataset
from untraded.metrics.positioning import recurring_death_spot
from untraded.metrics.registry import ParamValue
from untraded.metrics.utility import GRENADE_PRICES

TWO = {"advice.min_events": 2}


def _untraded(p: Mapping[str, ParamValue]) -> pl.Expr:
    return pl.col("trade_delay_s").is_null() | (pl.col("trade_delay_s") > p["trade.window_s"])


def untraded_deaths(ds: Dataset, player: int, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    deaths = placed(ds, ds["death"].filter(_untraded(p)), player, "victim")
    return standard(deaths, ("killer", "nearest_teammate_distance"))


def isolated_deaths(ds: Dataset, player: int, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    rows = ds["death"].filter(
        _untraded(p) & (pl.col("nearest_teammate_distance") > p["isolation.radius"])
    )
    return standard(placed(ds, rows, player, "victim"), ("killer", "nearest_teammate_distance"))


def missed_trades(ds: Dataset, player: int, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    """Opportunities (a teammate killed near the player) the player did not convert: no kill of
    that killer by the player within the trade window."""
    chances = placed(
        ds,
        ds["trade_opportunity"].filter(
            pl.col("distance_to_killer") <= p["trade.opportunity_distance"]
        ),
        player,
        "teammate",
    )
    trades = (
        ds["death"]
        .filter(
            (pl.col("killer") == player)
            & pl.col("is_enemy_kill")
            & (pl.col("avenges_delay_s") <= p["trade.window_s"])
        )
        .select("match_id", "round", pl.col("victim").alias("killer"))
        .unique()
    )
    missed = chances.join(trades, on=["match_id", "round", "killer"], how="anti")
    return standard(missed.rename({"victim": "teammate_killed"}), ("teammate_killed", "killer"))


def opening_deaths(ds: Dataset, player: int, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    deaths = placed(ds, ds["death"].filter(pl.col("is_opening")), player, "victim")
    return standard(deaths, ("killer",))


def openings_lost(ds: Dataset, player: int, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    """Rounds where the player made the opening kill and the team still lost."""
    lost = ds["round_player"].filter(
        pl.col("opening_kill") & ~pl.col("team_won") & (pl.col("steamid") == player)
    )
    kills = ds["death"].filter(pl.col("is_opening") & (pl.col("killer") == player))
    rows = lost.select("match_id", "round").join(
        kills.select("match_id", "round", "tick", "killer", "victim"), on=["match_id", "round"]
    )
    return standard(placed(ds, rows, player, "killer"), ("victim",))


def clutches_lost(ds: Dataset, player: int, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    rows = ds["clutch"].filter(~pl.col("won")).with_columns(pl.col("start_tick").alias("tick"))
    return standard(placed(ds, rows.drop("side"), player, "steamid"), ("enemies",))


def duels_without_damage(ds: Dataset, player: int, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    """Deaths to an enemy the player had not damaged in that round: duels lost on the aim."""
    deaths = ds["death"].filter(pl.col("is_enemy_kill"))
    hits = (
        ds["damage"]
        .filter(pl.col("attacker") == player)
        .select(
            "match_id", "round", pl.col("victim").alias("killer"), pl.col("tick").alias("hit_tick")
        )
    )
    mine = placed(ds, deaths, player, "victim")
    touched = (
        mine.join(hits, on=["match_id", "round", "killer"])
        .filter(pl.col("hit_tick") <= pl.col("tick"))
        .select("match_id", "round", "tick")
        .unique()
    )
    return standard(mine.join(touched, on=["match_id", "round", "tick"], how="anti"), ("killer",))


def wasted_utility(ds: Dataset, player: int, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    deaths = ds["death"].join(
        ds["kill"].select("match_id", "tick", "victim", "victim_inventory"),
        on=["match_id", "tick", "victim"],
    )
    grenades = pl.element().is_in(list(GRENADE_PRICES))
    price = pl.element().replace_strict(GRENADE_PRICES, default=0, return_dtype=pl.Int64)
    rows = deaths.with_columns(
        pl.col("victim_inventory").list.eval(pl.element().filter(grenades)).alias("grenades"),
        pl.col("victim_inventory").list.eval(price).list.sum().alias("value"),
    ).filter(pl.col("value") > 0)
    return standard(placed(ds, rows, player, "victim"), ("grenades", "value"))


def team_flashes(ds: Dataset, player: int, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    """Living teammates blinded by the player's flashes for at least `flash.min_blind_s`."""
    deaths = ds["death"].select("match_id", "round", "victim", pl.col("tick").alias("death_tick"))
    blinds = (
        ds["blind"]
        .join(deaths, on=["match_id", "round", "victim"], how="left")
        .filter(pl.col("death_tick").is_null() | (pl.col("tick") <= pl.col("death_tick")))
        .filter(
            pl.col("is_teammate")
            & ~pl.col("is_self")
            & (pl.col("duration") >= p["flash.min_blind_s"])
        )
    )
    return standard(placed(ds, blinds, player, "flasher"), ("victim", "duration"))


def recurring_spot(ds: Dataset, player: int, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    """Untraded deaths in a zone that holds a recurring share of them (`pos.recurring_death_spot`),
    over the session and the days before it."""
    spots = recurring_death_spot(ds, p).filter(pl.col("steamid") == player)
    deaths = (
        ds["death"]
        .filter(_untraded(p))
        .join(
            ds["kill"].select("match_id", "tick", "victim", pl.col("victim_place").alias("zone")),
            on=["match_id", "tick", "victim"],
        )
    )
    rows = placed(ds, deaths, player, "victim").join(
        spots.select("map", pl.col("side").cast(pl.String), "zone"), on=["map", "side", "zone"]
    )
    return standard(rows, ("zone", "killer"))


for definition in (
    Rule(
        id="trade.untraded_deaths",
        version="1.0.0",
        family="trade",
        metric="trade.untraded_deaths",
        evidence=untraded_deaths,
        actions=("adjust.trade_distance", "adjust.play_with_entry", "drill.trade_timing"),
    ),
    Rule(
        id="trade.isolated_deaths",
        version="1.0.0",
        family="trade",
        metric="duel.isolated_death_pct",
        evidence=isolated_deaths,
        actions=("adjust.trade_distance", "adjust.info_before_peek"),
    ),
    Rule(
        id="trade.missed_trades",
        version="1.0.0",
        family="trade",
        metric="trade.kill_conversion_pct",
        evidence=missed_trades,
        actions=("drill.trade_timing", "adjust.follow_entry"),
    ),
    Rule(
        id="duel.opening_deaths",
        version="1.0.0",
        family="duel",
        metric="duel.opening_success_pct",
        evidence=opening_deaths,
        params=TWO,
        actions=("drill.prefire", "adjust.info_before_peek", "adjust.use_utility_to_peek"),
    ),
    Rule(
        id="duel.openings_lost",
        version="1.0.0",
        family="duel",
        metric="duel.opening_win_conversion_pct",
        evidence=openings_lost,
        params=TWO,
        actions=("adjust.play_the_advantage", "adjust.regroup_after_opening"),
    ),
    Rule(
        id="clutch.clutches_lost",
        version="1.0.0",
        family="clutch",
        metric="clutch.win_pct",
        evidence=clutches_lost,
        params=TWO,
        actions=("adjust.clutch_time", "drill.retake_servers"),
    ),
    Rule(
        id="combat.duels_without_damage",
        version="1.0.0",
        family="combat",
        metric="base.hs_pct",
        evidence=duels_without_damage,
        actions=("drill.aim_botz", "drill.crosshair_placement", "drill.counter_strafe"),
    ),
    Rule(
        id="util.wasted_utility",
        version="1.0.0",
        family="util",
        metric="util.unused_value_at_death",
        evidence=wasted_utility,
        actions=("adjust.use_utility_before_death", "drill.lineups"),
    ),
    Rule(
        id="util.team_flashes",
        version="1.0.0",
        family="util",
        metric="util.teammates_flashed",
        evidence=team_flashes,
        actions=("adjust.call_your_flashes", "drill.pop_flashes"),
    ),
    Rule(
        id="pos.recurring_death_spot",
        version="1.0.0",
        family="pos",
        metric="pos.recurring_death_spot",
        evidence=recurring_spot,
        params=TWO,
        history=True,
        indicator="trade.untraded_deaths",
        actions=("adjust.change_position", "adjust.change_timing", "drill.prefire"),
    ),
):
    rule(definition)
