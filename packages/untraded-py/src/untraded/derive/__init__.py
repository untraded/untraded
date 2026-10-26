# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The round model (workstream E4): derived tables computed from the canonical tables only.

No demo is needed: `derive()` reads the canonical tables of one match (as returned by
`untraded.parsing.parse_demo`, or read back from Parquet) and returns validated derived tables.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields

import polars as pl

from untraded.derive.buys import BuyThresholds, build_team_rounds
from untraded.derive.clutches import build_clutches
from untraded.derive.deaths import build_deaths
from untraded.derive.players import build_round_players
from untraded.derive.schema import TABLES
from untraded.winprob import Model, default_model, swings

__all__ = ["BuyThresholds", "DerivedError", "RoundModel", "derive", "swing_table"]


class DerivedError(ValueError):
    """A derived table does not match its schema or breaks an invariant."""


@dataclass(frozen=True)
class RoundModel:
    round_player: pl.DataFrame
    death: pl.DataFrame
    trade_opportunity: pl.DataFrame
    clutch: pl.DataFrame
    team_round: pl.DataFrame
    swing: pl.DataFrame

    def tables(self) -> dict[str, pl.DataFrame]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


DEFAULT_BUY_THRESHOLDS = BuyThresholds()


def derive(
    tables: Mapping[str, pl.DataFrame],
    *,
    buy_thresholds: BuyThresholds = DEFAULT_BUY_THRESHOLDS,
    winprob: Model | None = None,
) -> RoundModel:
    """Derives the round model of one match from its canonical tables. `winprob` is the
    win-probability model the swings are computed with (default: the published one)."""
    tickrate = float(tables["match"]["tickrate"][0])
    rounds = tables["round"]
    states = tables["player_tick"]
    teams = tables["player"].select("steamid", "team")

    death, opportunities = build_deaths(tables["kill"], teams, rounds, states, tickrate)
    model = {
        "round_player": build_round_players(
            economy=tables["economy"],
            teams=teams,
            rounds=rounds,
            kills=tables["kill"],
            deaths=death,
            damage=tables["damage"],
            states=states,
            tickrate=tickrate,
        ),
        "death": death,
        "trade_opportunity": opportunities,
        "clutch": build_clutches(death, rounds, states, teams),
        "team_round": build_team_rounds(tables["economy"], rounds, teams, buy_thresholds),
        "swing": swings(tables, winprob or default_model()),
    }
    derived = RoundModel(**{name: _conform(frame, name) for name, frame in model.items()})
    _check(derived)
    return derived


def swing_table(tables: Mapping[str, pl.DataFrame], winprob: Model | None = None) -> pl.DataFrame:
    """The `swing` table alone, for matches derived before it existed."""
    return _conform(swings(tables, winprob or default_model()), "swing")


def _conform(frame: pl.DataFrame, name: str) -> pl.DataFrame:
    schema = TABLES[name]
    missing = [column for column in schema if column not in frame.columns]
    if missing:
        raise DerivedError(f"{name}: missing {missing}")
    return frame.select(pl.col(column).cast(dtype, strict=True) for column, dtype in schema.items())


def _check(model: RoundModel) -> None:
    """Invariants of the round model."""
    players = model.round_player
    if players.select("round", "steamid").is_duplicated().any():
        raise DerivedError("round_player: more than one row per player and round")
    if (players["deaths"] > 1).any():
        raise DerivedError("round_player: a player died twice in a round")
    team_size = players.group_by("round", "team").len()
    if (team_size["len"] > 5).any():
        raise DerivedError("round_player: more than 5 players on a team in a round")
    openings = model.death.filter(pl.col("is_opening")).group_by("round").len()
    if (openings["len"] > 1).any():
        raise DerivedError("death: more than one opening in a round")
    if model.clutch.select("round", "team").is_duplicated().any():
        raise DerivedError("clutch: more than one clutch per team and round")
    if model.team_round.select("round", "team").is_duplicated().any():
        raise DerivedError("team_round: more than one row per team and round")
