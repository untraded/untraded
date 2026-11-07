# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""§ 2 Duels, trades and clutches (docs/metrics-v1.md), from the round model (docs/round-model.md).

The round model stores trade delays and distances; the thresholds below are applied here.
"""

from __future__ import annotations

from collections.abc import Mapping

import polars as pl

from untraded.metrics._helpers import per_player, rate, rounds, total
from untraded.metrics.dataset import Dataset
from untraded.metrics.registry import ROUNDS, ParamValue, metric

WINDOW = {"trade.window_s": 5.0}
WINDOW_W3 = {"trade.window_w3_s": 3.0}
OPPORTUNITY = {"trade.opportunity_distance": 1300.0}
ISOLATION = {"isolation.radius": 1000.0}
RP = ("round_player",)


def _count(ds: Dataset, rows: pl.DataFrame, player: str) -> pl.DataFrame:
    """Rows of the player's kept rounds, counted per player (column `player`)."""
    kept = ds.kept(rows, player=player)
    return per_player(
        ds, kept.group_by(pl.col(player).alias("steamid")).agg(pl.len().alias("value"))
    )


# Openings


@metric(
    "duel.opening_kills",
    version="1.0.0",
    name="Opening kills",
    unit="count",
    better="higher",
    uses=RP,
    doc="Rounds where the player makes the opening kill (first enemy kill after freeze end).",
)
def opening_kills(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return total(ds, "opening_kill")


@metric(
    "duel.opening_deaths",
    version="1.0.0",
    name="Opening deaths",
    unit="count",
    better="lower",
    uses=RP,
    doc="Rounds where the player is the opening victim.",
)
def opening_deaths(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return total(ds, "opening_death")


def _attempts(ds: Dataset) -> pl.DataFrame:
    kills, deaths = total(ds, "opening_kill"), total(ds, "opening_death")
    return kills.join(deaths, on="steamid", suffix="_d").select(
        "steamid", (pl.col("value") + pl.col("value_d")).alias("value")
    )


@metric(
    "duel.opening_attempts",
    version="1.0.0",
    name="Opening duels",
    unit="count",
    better="neutral",
    uses=RP,
    doc="Opening kills + opening deaths.",
)
def opening_attempts(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return _attempts(ds)


@metric(
    "duel.opening_success_pct",
    version="1.0.0",
    name="Opening success",
    unit="pct",
    better="higher",
    cases=("duel.opening_attempts",),
    uses=RP,
    doc="Opening kills ÷ opening duels * 100.",
)
def opening_success_pct(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return rate(total(ds, "opening_kill"), _attempts(ds), scale=100.0)


@metric(
    "duel.opening_attempt_pct",
    version="1.0.0",
    name="Opening frequency",
    unit="pct",
    better="neutral",
    cases=(ROUNDS,),
    uses=RP,
    doc="Opening duels ÷ rounds played * 100.",
)
def opening_attempt_pct(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    return rate(_attempts(ds), rounds(ds), scale=100.0)


@metric(
    "duel.opening_win_conversion_pct",
    version="1.0.0",
    name="Opening conversion",
    unit="pct",
    better="higher",
    cases=("duel.opening_kills",),
    uses=RP,
    doc="% of rounds with an opening kill by the player that the team wins.",
)
def opening_win_conversion_pct(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    opened = ds.round_players().filter(pl.col("opening_kill")).group_by("steamid")
    won = per_player(ds, opened.agg(pl.col("team_won").sum().alias("value")))
    return rate(won, per_player(ds, opened.agg(pl.len().alias("value"))), scale=100.0)


# Trades


def _trade_kills(ds: Dataset, window: ParamValue) -> pl.DataFrame:
    rows = ds["death"].filter(pl.col("is_enemy_kill") & (pl.col("avenges_delay_s") <= window))
    return _count(ds, rows, "killer")


def _traded_deaths(ds: Dataset, window: ParamValue) -> pl.DataFrame:
    return _count(ds, ds["death"].filter(pl.col("trade_delay_s") <= window), "victim")


def untraded(window: ParamValue) -> pl.Expr:
    """A death not traded within `window`."""
    return pl.col("trade_delay_s").is_null() | (pl.col("trade_delay_s") > window)


def _untraded(ds: Dataset, window: ParamValue) -> pl.DataFrame:
    """Deaths - traded deaths - the deaths nobody could trade (no living teammate)."""
    alone = ds["death"].filter(untraded(window) & pl.col("nearest_teammate_distance").is_null())
    return (
        total(ds, "deaths")
        .join(_traded_deaths(ds, window), on="steamid", suffix="_t")
        .join(_count(ds, alone, "victim"), on="steamid", suffix="_a")
        .select("steamid", (pl.col("value") - pl.col("value_t") - pl.col("value_a")).alias("value"))
    )


def _trade_metrics(suffix: str, param: str, default: float) -> None:
    seconds = f"{default:g} s"
    params = {param: default}

    @metric(
        f"trade.trade_kills{suffix}",
        version="1.1.0",
        name=f"Trade kills ({seconds})",
        unit="count",
        better="higher",
        params=params,
        uses=("death",),
        doc=f"Kills of an enemy who killed a teammate of the player within `{param}` before.",
    )
    def trade_kills(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
        return _trade_kills(ds, p[param])

    @metric(
        f"trade.traded_deaths{suffix}",
        version="1.1.0",
        name=f"Traded deaths ({seconds})",
        unit="count",
        better="neutral",
        params=params,
        uses=("death",),
        doc=f"The player's deaths whose killer was killed by a teammate within `{param}`.",
    )
    def traded_deaths(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
        return _traded_deaths(ds, p[param])

    @metric(
        f"trade.traded_death_pct{suffix}",
        version="1.1.0",
        name=f"Traded death % ({seconds})",
        unit="pct",
        better="higher",
        cases=("base.deaths",),
        params=params,
        uses=("death", "round_player"),
        doc="Traded deaths ÷ deaths * 100.",
    )
    def traded_death_pct(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
        return rate(_traded_deaths(ds, p[param]), total(ds, "deaths"), scale=100.0)

    @metric(
        f"trade.untraded_deaths{suffix}",
        version="1.2.0",
        name=f"Untraded deaths ({seconds})",
        unit="count",
        better="lower",
        params=params,
        uses=("death", "round_player"),
        doc="Deaths with a living teammate that were not traded (the product's signature "
        "metric). The last player alive has nobody to trade them: such a death is left out.",
    )
    def untraded_deaths(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
        return _untraded(ds, p[param])


_trade_metrics("", "trade.window_s", WINDOW["trade.window_s"])
_trade_metrics("_w3", "trade.window_w3_s", WINDOW_W3["trade.window_w3_s"])


def slow_trades(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    """Trade kills that took longer than `trade.window_w3_s`, within `trade.window_s`."""
    return ds["death"].filter(
        pl.col("is_enemy_kill")
        & (pl.col("avenges_delay_s") > p["trade.window_w3_s"])
        & (pl.col("avenges_delay_s") <= p["trade.window_s"])
    )


@metric(
    "trade.slow_trade_pct",
    version="1.0.0",
    name="Slow trades",
    unit="pct",
    better="lower",
    cases=("trade.trade_kills",),
    params={**WINDOW, **WINDOW_W3},
    uses=("death",),
    doc="Trade kills that took longer than `trade.window_w3_s` ÷ trade kills (within "
    "`trade.window_s`) * 100.",
)
def slow_trade_pct(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    return rate(
        _count(ds, slow_trades(ds, p), "killer"), _trade_kills(ds, p["trade.window_s"]), scale=100.0
    )


def opportunities(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    """The trade opportunities: the teammate was within `trade.opportunity_distance` of the
    killer, and saw the killer within `trade.window_s` of the kill (or traded it, which proves
    it: the engine's spotting can lag behind a quick trade). Adds `converted`: this teammate
    traded the death within the window."""
    window = p["trade.window_s"]
    traders = (
        ds["death"]
        .select("match_id", "tick", "victim", "trader", traded=pl.col("trade_delay_s") <= window)
        .unique(["match_id", "tick", "victim"], keep="first")
    )
    return (
        ds["trade_opportunity"]
        .filter(pl.col("distance_to_killer") <= p["trade.opportunity_distance"])
        .join(traders, on=["match_id", "tick", "victim"], how="left")
        .with_columns(
            ((pl.col("trader") == pl.col("teammate")) & pl.col("traded"))
            .fill_null(False)
            .alias("converted")
        )
        .filter((pl.col("sight_delay_s") <= window) | pl.col("converted"))
        .drop("trader", "traded")
    )


OPPORTUNITY_DOC = (
    "within `trade.opportunity_distance` of the killer, and saw the killer (the engine's "
    "spotting) within `trade.window_s` of the kill, or traded it"
)


@metric(
    "trade.kill_opportunities",
    version="1.2.0",
    name="Trade opportunities",
    unit="count",
    better="neutral",
    params={**WINDOW, **OPPORTUNITY},
    uses=("death", "trade_opportunity"),
    doc=f"Times a teammate of the player was killed while the player was alive, {OPPORTUNITY_DOC}.",
)
def kill_opportunities(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    return _count(ds, opportunities(ds, p), "teammate")


@metric(
    "trade.kill_conversion_pct",
    version="1.3.0",
    name="Opportunity conversion",
    unit="pct",
    better="higher",
    cases=("trade.kill_opportunities",),
    params={**WINDOW, **OPPORTUNITY},
    uses=("death", "trade_opportunity"),
    doc="Trade opportunities the player converted (traded that death within `trade.window_s`) "
    "÷ trade opportunities * 100.",
)
def kill_conversion_pct(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    chances = opportunities(ds, p)
    return rate(
        _count(ds, chances.filter(pl.col("converted")), "teammate"),
        _count(ds, chances, "teammate"),
        scale=100.0,
    )


@metric(
    "trade.death_opportunities",
    version="1.2.0",
    name="Tradable deaths",
    unit="count",
    better="neutral",
    params={**WINDOW, **OPPORTUNITY},
    uses=("death", "trade_opportunity"),
    doc="The player's deaths where at least one teammate had a trade opportunity.",
)
def death_opportunities(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    tradable = opportunities(ds, p).select("match_id", "round", "tick", "victim").unique()
    return _count(ds, tradable, "victim")


# Duels lost

SIGHT = {"duel.sight_s": 2.0}
NOT_A_GUN = (
    "hegrenade",
    "flashbang",
    "smokegrenade",
    "decoy",
    "molotov",
    "incgrenade",
    "inferno",
    "planted_c4",
    "taser",
    "world",
)


def lost_duels(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    """Deaths in a duel: killed by an enemy's gun, not blind, after seeing the killer (the
    engine's spotting) within `duel.sight_s` before. Shot in the back, burnt or flashed is not
    a duel. Adds `damaged`: the player had hurt the killer earlier in the round."""
    weapon = pl.col("weapon")
    shots = (
        ds["kill"]
        .select("match_id", "tick", "victim", "weapon")
        .unique(["match_id", "tick", "victim"], keep="first")
    )
    # A player dies once a round: only the first death is a duel, so that a crafted demo
    # repeating deaths cannot multiply the rows of the joins below.
    once = (
        ds["death"]
        .filter(pl.col("victim").is_not_null())
        .sort("match_id", "tick")
        .unique(["match_id", "round", "victim"], keep="first", maintain_order=True)
    )
    # Blind at the death: a blind that started before it and lasts until it (the kill's own
    # `victim_flash_duration` is the last flash's length, not reset when it wears off).
    blinded = (
        once.select("match_id", "round", "tick", "victim")
        .join(
            ds["blind"].select(
                "match_id", "round", "victim", pl.col("tick").alias("blind_tick"), "duration"
            ),
            on=["match_id", "round", "victim"],
        )
        .join(ds["match"].select("match_id", "tickrate"), on="match_id")
        .filter(
            (pl.col("blind_tick") <= pl.col("tick"))
            & (pl.col("tick") <= pl.col("blind_tick") + pl.col("duration") * pl.col("tickrate"))
        )
        .select("match_id", "tick", "victim")
        .unique()
    )
    hits = ds["damage"].select(
        "match_id",
        "round",
        pl.col("attacker").alias("victim"),
        pl.col("victim").alias("killer"),
        pl.col("tick").alias("hit_tick"),
    )
    deaths = (
        once.filter(pl.col("is_enemy_kill") & (pl.col("last_sight_s") <= p["duel.sight_s"]))
        .join(shots, on=["match_id", "tick", "victim"])
        .join(blinded, on=["match_id", "tick", "victim"], how="anti")
        .filter(~weapon.is_in(NOT_A_GUN) & ~weapon.str.contains("(?i)knife|bayonet"))
    )
    damaged = (
        deaths.select("match_id", "round", "tick", "victim", "killer")
        .join(hits, on=["match_id", "round", "victim", "killer"])
        .filter(pl.col("hit_tick") <= pl.col("tick"))
        .select("match_id", "tick", "victim", damaged=pl.lit(True))
        .unique()
    )
    return deaths.join(damaged, on=["match_id", "tick", "victim"], how="left").with_columns(
        pl.col("damaged").fill_null(False)
    )


@metric(
    "duel.duels_lost",
    version="1.0.0",
    name="Duels lost",
    unit="count",
    better="neutral",
    params=SIGHT,
    uses=("death", "kill", "damage", "blind"),
    doc="Deaths in a duel: killed by an enemy's gun (no grenade, fire, knife, zeus or bomb), "
    "not blind, having seen the killer (the engine's spotting) within `duel.sight_s` before.",
)
def duels_lost(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    return _count(ds, lost_duels(ds, p), "victim")


@metric(
    "duel.lost_without_damage_pct",
    version="1.0.0",
    name="Duels lost without damage",
    unit="pct",
    better="lower",
    cases=("duel.duels_lost",),
    params=SIGHT,
    uses=("death", "kill", "damage", "blind"),
    doc="Duels lost where the player had not hurt the killer in the round ÷ duels lost * 100.",
)
def lost_without_damage_pct(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    lost = lost_duels(ds, p)
    return rate(
        _count(ds, lost.filter(~pl.col("damaged")), "victim"),
        _count(ds, lost, "victim"),
        scale=100.0,
    )


# Peeks lost

PEEK = {**SIGHT, "duel.peek_distance": 64.0}


def lost_peeks(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    """Duels lost while peeking: in the second before the death, the player had been at least
    `duel.peek_distance` from where they died. Adds `flash_held`: a flash still in the
    inventory at the death, which could have been thrown for the peek."""
    inventory = (
        ds["kill"]
        .select("match_id", "tick", "victim", "victim_inventory")
        .unique(["match_id", "tick", "victim"], keep="first")
    )
    return (
        lost_duels(ds, p)
        .filter(pl.col("moved_1s") >= p["duel.peek_distance"])
        .join(inventory, on=["match_id", "tick", "victim"], how="left")
        .with_columns(
            pl.col("victim_inventory")
            .list.contains("Flashbang")
            .fill_null(False)
            .alias("flash_held")
        )
        .drop("victim_inventory")
    )


@metric(
    "duel.peeks_lost",
    version="1.0.0",
    name="Peeks lost",
    unit="count",
    better="neutral",
    params=PEEK,
    uses=("death", "kill", "damage", "blind"),
    doc="Duels lost (`duel.duels_lost`) where, in the second before the death, the player had "
    "been at least `duel.peek_distance` from where they died: they peeked.",
)
def peeks_lost(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    return _count(ds, lost_peeks(ds, p), "victim")


@metric(
    "duel.dry_peek_pct",
    version="1.0.0",
    name="Peeks without the flash",
    unit="pct",
    better="lower",
    cases=("duel.peeks_lost",),
    params=PEEK,
    uses=("death", "kill", "damage", "blind"),
    doc="Peeks lost with a flash still in the inventory ÷ peeks lost * 100: the flash that could "
    "have gone first.",
)
def dry_peek_pct(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    lost = lost_peeks(ds, p)
    return rate(
        _count(ds, lost.filter(pl.col("flash_held")), "victim"),
        _count(ds, lost, "victim"),
        scale=100.0,
    )


# Spacing


def _isolated(ds: Dataset, window: ParamValue, radius: ParamValue) -> pl.DataFrame:
    rows = ds["death"].filter(
        (pl.col("trade_delay_s").is_null() | (pl.col("trade_delay_s") > window))
        & (pl.col("nearest_teammate_distance") > radius)
    )
    return _count(ds, rows, "victim")


ISOLATION_DOC = (
    "**Untraded** deaths where the nearest living teammate was more than `isolation.radius` away. "
    "A death with no living teammate (last player alive) is not isolated."
)


@metric(
    "duel.isolated_deaths",
    version="1.1.0",
    name="Isolated deaths",
    unit="count",
    better="lower",
    params={**WINDOW, **ISOLATION},
    uses=("death",),
    doc=ISOLATION_DOC,
)
def isolated_deaths(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    return _isolated(ds, p["trade.window_s"], p["isolation.radius"])


@metric(
    "duel.isolated_death_pct",
    version="1.1.0",
    name="Isolated death %",
    unit="pct",
    better="lower",
    cases=("base.deaths",),
    params={**WINDOW, **ISOLATION},
    uses=("death", "round_player"),
    doc="Isolated deaths ÷ deaths * 100.",
)
def isolated_death_pct(ds: Dataset, p: Mapping[str, ParamValue]) -> pl.DataFrame:
    return rate(
        _isolated(ds, p["trade.window_s"], p["isolation.radius"]), total(ds, "deaths"), scale=100.0
    )


@metric(
    "duel.nearest_teammate_at_death",
    version="1.0.0",
    name="Spacing at death",
    unit="units",
    better="lower",
    cases=("base.deaths",),
    uses=("death",),
    doc="Median, over deaths with a living teammate, of the distance to the nearest one.",
)
def nearest_teammate_at_death(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    deaths = ds.kept(ds["death"].drop_nulls("nearest_teammate_distance"), player="victim")
    median = deaths.group_by(pl.col("victim").alias("steamid")).agg(
        pl.col("nearest_teammate_distance").median().alias("value")
    )
    return per_player(ds, median, fill=None)


# Clutches


def _clutches(ds: Dataset) -> pl.DataFrame:
    return ds.kept(ds["clutch"])


def _clutch_metrics(enemies: int) -> None:
    @metric(
        f"clutch.attempts_1v{enemies}",
        version="1.1.0",
        name=f"1v{enemies} attempts",
        unit="count",
        better="neutral",
        uses=("clutch",),
        doc=f"Rounds where the player becomes the last one alive on the team, facing "
        f"{enemies} living enem{'ies' if enemies > 1 else 'y'}.",
    )
    def attempts(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
        rows = _clutches(ds).filter(pl.col("enemies") == enemies)
        return per_player(ds, rows.group_by("steamid").agg(pl.len().alias("value")))

    @metric(
        f"clutch.wins_1v{enemies}",
        version="1.1.0",
        name=f"1v{enemies} wins",
        unit="count",
        better="higher",
        uses=("clutch",),
        doc=f"1v{enemies} clutches the team wins.",
    )
    def wins(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
        rows = _clutches(ds).filter((pl.col("enemies") == enemies) & pl.col("won"))
        return per_player(ds, rows.group_by("steamid").agg(pl.len().alias("value")))


for _enemies in range(1, 6):
    _clutch_metrics(_enemies)


@metric(
    "clutch.win_pct",
    version="1.1.0",
    name="Clutch success",
    unit="pct",
    better="higher",
    cases=(
        "clutch.attempts_1v1",
        "clutch.attempts_1v2",
        "clutch.attempts_1v3",
        "clutch.attempts_1v4",
        "clutch.attempts_1v5",
    ),
    uses=("clutch",),
    doc="Clutch wins ÷ clutch attempts * 100, over all N.",
)
def clutch_win_pct(ds: Dataset, _: Mapping[str, ParamValue]) -> pl.DataFrame:
    by_player = _clutches(ds).group_by("steamid")
    wins = per_player(ds, by_player.agg(pl.col("won").sum().alias("value")))
    return rate(wins, per_player(ds, by_player.agg(pl.len().alias("value"))), scale=100.0)
