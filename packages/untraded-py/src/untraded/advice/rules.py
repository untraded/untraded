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
from untraded.metrics.duels import lost_duels, lost_peeks, opportunities, untraded
from untraded.metrics.positioning import recurring_death_spot
from untraded.metrics.registry import ParamValue

TWO = {"advice.min_events": 2}


def _untraded(p: Mapping[str, ParamValue]) -> pl.Expr:
    """Untraded, with a living teammate who could have traded (`trade.untraded_deaths`)."""
    return untraded(p["trade.window_s"]) & pl.col("nearest_teammate_distance").is_not_null()


def untraded_deaths(ds: Dataset, player: int, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    deaths = placed(ds, ds["death"].filter(_untraded(p)), player, "victim")
    return standard(deaths, ("killer", "nearest_teammate_distance"))


def isolated_deaths(ds: Dataset, player: int, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    rows = ds["death"].filter(
        _untraded(p) & (pl.col("nearest_teammate_distance") > p["isolation.radius"])
    )
    return standard(placed(ds, rows, player, "victim"), ("killer", "nearest_teammate_distance"))


def missed_trades(ds: Dataset, player: int, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    """Opportunities (a teammate killed near the player, whose killer the player saw) the player
    did not convert: the player did not trade that death within the trade window."""
    missed = opportunities(ds, p).filter(~pl.col("converted"))
    rows = placed(ds, missed, player, "teammate").rename({"victim": "teammate_killed"})
    return standard(rows, ("teammate_killed", "killer"))


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


def duels_without_damage(ds: Dataset, player: int, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    """Duels lost (the killer seen, a gun, not blind) without hurting the killer: lost on the
    aim."""
    rows = lost_duels(ds, p).filter(~pl.col("damaged"))
    return standard(placed(ds, rows, player, "victim"), ("killer", "weapon"))


def wasted_utility(ds: Dataset, player: int, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    """Peeks lost with a flash still in the inventory: the flash stayed on the body instead of
    going first."""
    rows = lost_peeks(ds, p).filter(pl.col("flash_held"))
    return standard(placed(ds, rows, player, "victim"), ("killer", "weapon"))


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
        version="1.1.0",
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
        version="1.1.0",
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
        version="2.0.0",
        family="combat",
        metric="duel.lost_without_damage_pct",
        evidence=duels_without_damage,
        actions=("drill.aim_botz", "drill.crosshair_placement", "drill.counter_strafe"),
    ),
    Rule(
        id="util.wasted_utility",
        version="2.0.0",
        family="util",
        metric="duel.dry_peek_pct",
        evidence=wasted_utility,
        actions=("adjust.use_utility_to_peek", "drill.pop_flashes"),
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
        version="1.1.0",
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
