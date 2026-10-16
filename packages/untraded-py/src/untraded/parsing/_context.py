# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""What every table builder shares while one demo is parsed, and demoparser2 conversions."""

from __future__ import annotations

from dataclasses import dataclass, field

import polars as pl
from demoparser2 import DemoParser

from untraded.parsing.rounds import RoundCut, event_rounds
from untraded.parsing.teams import Teams

SIDES = {2: "T", 3: "CT"}


@dataclass
class Context:
    parser: DemoParser
    events: set[str]
    """Game events present in the demo (`list_game_events`)."""
    cuts: list[RoundCut]
    teams: Teams
    tickrate: float
    last_event_tick: int | None
    """End-of-match panel: events from this tick on are dropped."""
    on_team: pl.DataFrame
    """One row per round and player on a team at freeze end: round, steamid, side, props."""
    unavailable: list[str] = field(default_factory=list)
    """Tables or columns that could not be built, with the reason (match.unavailable)."""

    def event(self, name: str, **props: list[str]) -> pl.DataFrame:
        """The event as Polars, or an empty frame (only `tick`) when the demo lacks it."""
        if name not in self.events:
            return pl.DataFrame({"tick": pl.Series([], dtype=pl.Int32)})
        return frame(self.parser.parse_event(name, **props)).with_columns(
            pl.col("tick").cast(pl.Int32)
        )

    def in_rounds(self, events: pl.DataFrame) -> pl.DataFrame:
        """Adds `round` and drops events outside live rounds (see rounds.event_rounds)."""
        return event_rounds(events, self.cuts, last_event_tick=self.last_event_tick)

    def ticks(self, props: list[str], ticks: list[int]) -> pl.DataFrame:
        """Player props at the given ticks (one row per tick and player present)."""
        if not ticks:
            return pl.DataFrame(
                schema={"tick": pl.Int32, "steamid": pl.UInt64, **dict.fromkeys(props, pl.Null)}
            )
        return frame(self.parser.parse_ticks(props, ticks=sorted(set(ticks)))).with_columns(
            pl.col("tick").cast(pl.Int32), pl.col("steamid").cast(pl.UInt64)
        )


def frame(data: object) -> pl.DataFrame:
    return pl.from_pandas(data)


def steamid(column: str) -> pl.Expr:
    """demoparser2 gives event steamids as strings; `0` or empty means no player."""
    text = pl.col(column).cast(pl.String)
    return (
        pl.when(text.is_in(["", "0"]) | text.is_null())
        .then(None)
        .otherwise(text)
        .cast(pl.UInt64, strict=True)
    )


def side(column: str) -> pl.Expr:
    """`team_num` (2 terrorists, 3 counter-terrorists) to `T` / `CT`; anything else is null."""
    return pl.col(column).cast(pl.Int64, strict=False).replace_strict(SIDES, default=None)
