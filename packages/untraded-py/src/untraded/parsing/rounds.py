# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Rounds from game state (ADR 0008): pure functions on the game rules values, one row per tick.

`state` has one row per tick where at least one player is in the demo (demoparser2 returns no
row before that, which drops pre-match freeze ends), sorted by tick, with the columns
`tick`, `is_freeze_period`, `is_warmup_period`, `total_rounds_played`, `round_win_status`
and `round_win_reason`.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

# CCSGameRules::m_iRoundWinStatus
WIN_STATUS = {2: "T", 3: "CT"}
# CCSGameRules::m_eRoundWinReason (RoundEndReason), checked on corpus demos against bomb events
REASONS = {
    1: "bomb_exploded",
    7: "bomb_defused",
    8: "elimination",  # CTs win
    9: "elimination",  # terrorists win
    12: "time_ran_out",  # target saved
    17: "surrender",  # terrorists surrender
    18: "surrender",  # CTs surrender
}


@dataclass(frozen=True)
class RoundCut:
    round: int
    start_tick: int
    freeze_end_tick: int
    end_tick: int
    winner_side: str
    reason: str


def cut_rounds(state: pl.DataFrame) -> list[RoundCut]:
    """Live rounds: from a freeze end outside warmup to the next `total_rounds_played` increment.

    A round is numbered `total_rounds_played + 1` at its freeze end. When several live freeze
    ends share a number (restarts), the last one wins. A round with no increment after its
    freeze end (demo cut before the round ended) is dropped.
    """
    ticks = state["tick"].to_list()
    freeze = state["is_freeze_period"].to_list()
    warmup = state["is_warmup_period"].to_list()
    played = state["total_rounds_played"].to_list()
    status = state["round_win_status"].to_list()
    reason = state["round_win_reason"].to_list()

    cuts: dict[int, RoundCut] = {}
    freeze_start = ticks[0] if ticks else 0
    for i in range(1, len(ticks)):
        if freeze[i] and not freeze[i - 1]:
            freeze_start = ticks[i]
        if not (freeze[i - 1] and not freeze[i]) or warmup[i]:
            continue
        number = played[i] + 1
        end = next((j for j in range(i + 1, len(ticks)) if played[j] > played[i]), None)
        if end is None:
            continue
        cuts[number] = RoundCut(
            round=number,
            start_tick=freeze_start,
            freeze_end_tick=ticks[i],
            end_tick=ticks[end],
            winner_side=WIN_STATUS.get(status[end], ""),
            reason=REASONS.get(reason[end], "other"),
        )
    return [cuts[number] for number in sorted(cuts)]


def event_rounds(
    events: pl.DataFrame, rounds: list[RoundCut], *, last_event_tick: int | None
) -> pl.DataFrame:
    """Adds a `round` column to events and drops those outside any live round.

    An event belongs to the round whose window holds its tick: from its `start_tick` to the next
    round's `start_tick` (events just after a round ends, such as bomb kills, belong to it). The
    last window closes at `last_event_tick` (the end-of-match panel), or at the last round end.
    """
    if not rounds:
        return events.with_columns(pl.lit(None, pl.Int16).alias("round")).clear()
    starts = [r.start_tick for r in rounds]
    stops = [
        *starts[1:],
        last_event_tick if last_event_tick is not None else rounds[-1].end_tick + 1,
    ]
    windows = pl.DataFrame(
        {
            "start": pl.Series(starts, dtype=pl.Int32),
            "stop": pl.Series(stops, dtype=pl.Int32),
            "round": pl.Series([r.round for r in rounds], dtype=pl.Int16),
        }
    )
    return (
        events.sort("tick")
        .join_asof(windows, left_on="tick", right_on="start", strategy="backward")
        .filter(pl.col("round").is_not_null() & (pl.col("tick") < pl.col("stop")))
        .drop("start", "stop")
    )
