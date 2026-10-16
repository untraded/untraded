# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Rounds from game state (ADR 0008), on synthetic game rules timelines."""

from __future__ import annotations

import polars as pl

from untraded.parsing.rounds import RoundCut, cut_rounds, event_rounds

FREEZE, LIVE, AFTER = "freeze", "live", "after"


def timeline(*steps: tuple[int, str, int, int, int, bool]) -> pl.DataFrame:
    """Steps of (tick, phase, total_rounds_played, win_status, win_reason, warmup)."""
    return pl.DataFrame(
        {
            "tick": [s[0] for s in steps],
            "is_freeze_period": [s[1] == FREEZE for s in steps],
            "is_warmup_period": [s[5] for s in steps],
            "total_rounds_played": [s[2] for s in steps],
            "round_win_status": [s[3] for s in steps],
            "round_win_reason": [s[4] for s in steps],
        }
    )


def two_rounds() -> pl.DataFrame:
    return timeline(
        (65, FREEZE, 0, 0, 0, False),
        (1000, LIVE, 0, 0, 0, False),
        (5000, AFTER, 1, 3, 8, False),  # CT win, elimination
        (5448, FREEZE, 1, 0, 0, False),
        (6728, LIVE, 1, 0, 0, False),
        (9000, AFTER, 2, 2, 1, False),  # T win, bomb exploded
    )


def test_cuts_rounds_from_freeze_ends_and_round_count() -> None:
    assert cut_rounds(two_rounds()) == [
        RoundCut(1, 65, 1000, 5000, "CT", "elimination"),
        RoundCut(2, 5448, 6728, 9000, "T", "bomb_exploded"),
    ]


def test_ignores_warmup_freeze_ends() -> None:
    state = timeline(
        (10, FREEZE, 0, 0, 0, True),
        (300, LIVE, 0, 0, 0, True),  # warmup freeze end: not a round
        (900, FREEZE, 0, 0, 0, False),
        (2000, LIVE, 0, 0, 0, False),
        (4000, AFTER, 1, 3, 12, False),
    )
    assert cut_rounds(state) == [RoundCut(1, 900, 2000, 4000, "CT", "time_ran_out")]


def test_truncated_demo_starts_at_its_first_live_round() -> None:
    state = timeline(
        (100, LIVE, 0, 0, 0, False),  # demo starts mid round 1: no freeze end for it
        (800, AFTER, 1, 3, 8, False),
        (1248, FREEZE, 1, 0, 0, False),
        (2528, LIVE, 1, 0, 0, False),
        (4000, AFTER, 2, 3, 7, False),
    )
    cuts = cut_rounds(state)
    assert [c.round for c in cuts] == [2]
    assert cuts[0].reason == "bomb_defused"


def test_a_restarted_round_keeps_its_last_freeze_end() -> None:
    state = timeline(
        (65, FREEZE, 0, 0, 0, False),
        (1000, LIVE, 0, 0, 0, False),
        (1500, FREEZE, 0, 0, 0, False),  # restart: the round count does not move
        (2780, LIVE, 0, 0, 0, False),
        (6000, AFTER, 1, 2, 9, False),
    )
    assert cut_rounds(state) == [RoundCut(1, 1500, 2780, 6000, "T", "elimination")]


def test_drops_a_round_the_demo_does_not_finish_and_maps_surrender() -> None:
    state = timeline(
        (65, FREEZE, 0, 0, 0, False),
        (1000, LIVE, 0, 0, 0, False),
        (3000, AFTER, 1, 3, 17, False),  # terrorists surrender
        (3448, FREEZE, 1, 0, 0, False),
        (4728, LIVE, 1, 0, 0, False),  # demo ends before this round does
    )
    assert cut_rounds(state) == [RoundCut(1, 65, 1000, 3000, "CT", "surrender")]


def test_unknown_reason_is_other() -> None:
    state = timeline(
        (65, FREEZE, 0, 0, 0, False),
        (1000, LIVE, 0, 0, 0, False),
        (3000, AFTER, 1, 3, 99, False),
    )
    assert cut_rounds(state)[0].reason == "other"


def test_events_belong_to_the_round_window_up_to_the_next_start() -> None:
    rounds = cut_rounds(two_rounds())
    events = pl.DataFrame({"tick": pl.Series([30, 1200, 5010, 5448, 9005, 9300], dtype=pl.Int32)})
    found = event_rounds(events, rounds, last_event_tick=9200)
    # 30: before the first live round; 5010: bomb kill just after round 1 ended (kept);
    # 9300: after the end-of-match panel (dropped)
    assert found.select("tick", "round").rows() == [(1200, 1), (5010, 1), (5448, 2), (9005, 2)]


def test_without_end_panel_the_last_round_closes_at_its_end() -> None:
    rounds = cut_rounds(two_rounds())
    events = pl.DataFrame({"tick": pl.Series([9000, 9001], dtype=pl.Int32)})
    assert event_rounds(events, rounds, last_event_tick=None)["tick"].to_list() == [9000]


def test_no_round_drops_every_event() -> None:
    events = pl.DataFrame({"tick": pl.Series([1, 2], dtype=pl.Int32)})
    assert event_rounds(events, [], last_event_tick=None).height == 0
