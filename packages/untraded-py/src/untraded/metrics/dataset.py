# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""What metrics read: the canonical and derived tables of one or more matches.

Tables of several matches are concatenated with a `match_id` column, so per-round metrics are
recomputed over all rounds, never averaged per match (metrics-v1 § 0). Splits (side, map) keep a
subset of the rounds played; metrics only count events of the player's kept rounds.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace

import polars as pl

MatchTables = Mapping[str, pl.DataFrame]
"""Canonical tables (`parse_demo(...).tables()`) and derived tables (`derive(...).tables()`)."""


@dataclass(frozen=True)
class Dataset:
    tables: Mapping[str, pl.DataFrame]
    """Every table with `match_id` (and `map` on `round_player`)."""
    played: pl.DataFrame
    """The rounds kept: `match_id`, `round`, `steamid`, `side`, `team`, `map`, and with the round
    model's `team_round`, `buy_type` and `opponent_buy_type`."""

    @classmethod
    def from_matches(cls, matches: Iterable[MatchTables]) -> Dataset:
        per_table: dict[str, list[pl.DataFrame]] = {}
        for tables in matches:
            info = tables["match"].row(0, named=True)
            for name, frame in tables.items():
                tagged = frame.with_columns(pl.lit(info["match_id"]).alias("match_id"))
                if name == "round_player":
                    tagged = tagged.with_columns(pl.lit(info["map"]).alias("map"))
                per_table.setdefault(name, []).append(tagged)
        merged = {name: pl.concat(frames, how="vertical") for name, frames in per_table.items()}
        played = merged["round_player"].select(
            "match_id", "round", "steamid", "side", "team", "map"
        )
        if "team_round" in merged:
            played = _with_buy_types(played, merged["team_round"])
        return cls(tables=merged, played=played)

    def split(
        self, *, side: str | None = None, map: str | None = None, buy: str | None = None
    ) -> Dataset:
        """Keeps the rounds a player played on that side, on that map, and/or with that team
        buy type (metrics-v1 § 5)."""
        kept = self.played
        if side is not None:
            kept = kept.filter(pl.col("side") == side)
        if map is not None:
            kept = kept.filter(pl.col("map") == map)
        if buy is not None:
            kept = kept.filter(pl.col("buy_type") == buy)
        return replace(self, played=kept)

    def __getitem__(self, table: str) -> pl.DataFrame:
        return self.tables[table]

    def players(self) -> pl.DataFrame:
        """One row per player with at least one kept round."""
        return self.played.select("steamid").unique().sort("steamid")

    def rounds_played(self) -> pl.DataFrame:
        return self.played.group_by("steamid").agg(pl.len().alias("rounds"))

    def kept(self, frame: pl.DataFrame, player: str = "steamid") -> pl.DataFrame:
        """Rows of `frame` in a kept round of the player in column `player`."""
        keys = self.played.select("match_id", "round", pl.col("steamid").alias(player))
        return frame.join(keys, on=["match_id", "round", player], how="semi")

    def round_players(self) -> pl.DataFrame:
        """`round_player` rows of the kept rounds."""
        return self.kept(self.tables["round_player"])


def _with_buy_types(played: pl.DataFrame, team_round: pl.DataFrame) -> pl.DataFrame:
    buys = team_round.select("match_id", "round", "team", pl.col("buy_type").cast(pl.String))
    opponents = buys.rename({"team": "opponent", "buy_type": "opponent_buy_type"})
    both = buys.join(opponents, on=["match_id", "round"]).filter(
        pl.col("team") != pl.col("opponent")
    )
    return played.join(both.drop("opponent"), on=["match_id", "round", "team"], how="left")
