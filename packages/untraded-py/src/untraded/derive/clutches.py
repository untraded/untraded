# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Clutches (metrics-v1 § 2): a player becomes the last one alive on the team, facing N enemies."""

from __future__ import annotations

import polars as pl


def build_clutches(
    deaths: pl.DataFrame,
    rounds: pl.DataFrame,
    states: pl.DataFrame,
    teams: pl.DataFrame,
) -> pl.DataFrame:
    """One row per clutch: who, against how many, from which tick, and whether the team won.

    Players alive at freeze end are the starting lineups. Deaths up to the round end are applied
    tick by tick (deaths on the same tick together), and a player who leaves the server mid-round
    (no longer alive in `player_tick`, without a death) leaves the lineup then. A team left with
    one player and at least one enemy alive starts a clutch, at most once per team and round.
    When both teams are down to one player on the same tick, both players are in a 1v1 clutch.
    """
    lineups = (
        states.join(
            rounds.select("round", "freeze_end_tick"),
            left_on=["round", "tick"],
            right_on=["round", "freeze_end_tick"],
        )
        .filter(pl.col("is_alive"))
        .join(teams, on="steamid")
        .select("round", "steamid", "team", "side")
    )
    ends = dict(zip(rounds["round"].to_list(), rounds["end_tick"].to_list(), strict=True))
    winners = dict(zip(rounds["round"].to_list(), rounds["winner_team"].to_list(), strict=True))
    # A player who leaves the server mid-round (a disconnection is not a death) leaves the lineup
    # at the first tick they are no longer alive in player_tick.
    ends_df = rounds.select("round", "end_tick")
    victims = deaths.select("round", pl.col("victim").alias("steamid")).drop_nulls()
    sampled = states.select("round", "tick").unique().sort("tick")
    last_alive = (
        states.filter(pl.col("is_alive"))
        .join(lineups.select("round", "steamid"), on=["round", "steamid"], how="semi")
        .group_by("round", "steamid")
        .agg(pl.col("tick").max().alias("last_alive"))
        .join(ends_df, on="round")
        .filter(pl.col("last_alive") < pl.col("end_tick"))
        .join(victims, on=["round", "steamid"], how="anti")
    )
    # The departure is the first player_tick sample of the round without them (none: not seen).
    departures = (
        last_alive.join(sampled, on="round")
        .filter((pl.col("tick") > pl.col("last_alive")) & (pl.col("tick") <= pl.col("end_tick")))
        .group_by("round", "steamid")
        .agg(pl.col("tick").min())
        .select("tick", "round", pl.col("steamid").alias("victim"))
    )
    events = pl.concat(
        [
            deaths.select(
                pl.col("tick").cast(pl.Int64),
                pl.col("round").cast(pl.Int64),
                pl.col("victim").cast(pl.UInt64),
            ),
            departures.select(
                pl.col("tick").cast(pl.Int64),
                pl.col("round").cast(pl.Int64),
                pl.col("victim").cast(pl.UInt64),
            ),
        ]
    )
    by_round = events.sort("tick").group_by("round", maintain_order=True)
    deaths_of = {int(number): group for (number,), group in by_round}

    rows = []
    for (number,), lineup in lineups.group_by("round", maintain_order=True):
        number = int(number)
        alive = {
            team: set(group["steamid"].to_list()) for (team,), group in lineup.group_by("team")
        }
        sides = dict(zip(lineup["steamid"].to_list(), lineup["side"].to_list(), strict=True))
        clutched: set[str] = set()
        died = deaths_of.get(number)
        if died is None:
            continue
        for (tick,), same_tick in died.filter(pl.col("tick") <= ends[number]).group_by(
            "tick", maintain_order=True
        ):
            for victim in same_tick["victim"].to_list():
                for players in alive.values():
                    players.discard(victim)
            for team, players in alive.items():
                enemies = sum(len(p) for t, p in alive.items() if t != team)
                if len(players) == 1 and enemies >= 1 and team not in clutched:
                    clutched.add(team)
                    (player,) = players
                    rows.append(
                        {
                            "round": number,
                            "steamid": player,
                            "team": team,
                            "side": sides[player],
                            "enemies": enemies,
                            "start_tick": tick,
                            "won": winners[number] == team,
                        }
                    )
    if not rows:
        return pl.DataFrame(
            schema={
                "round": pl.Int16,
                "steamid": pl.UInt64,
                "team": pl.String,
                "side": pl.String,
                "enemies": pl.Int8,
                "start_tick": pl.Int32,
                "won": pl.Boolean,
            }
        )
    return pl.DataFrame(rows).sort("start_tick", "steamid")
