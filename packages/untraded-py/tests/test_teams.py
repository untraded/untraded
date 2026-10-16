# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Stable teams A and B across side switches and late joiners."""

from __future__ import annotations

import polars as pl

from untraded.parsing.teams import assign_teams


def sides(*rows: tuple[int, int, str]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "round": [r[0] for r in rows],
            "steamid": [r[1] for r in rows],
            "side": [r[2] for r in rows],
        }
    )


def test_team_a_starts_on_ct_and_keeps_its_name_after_the_switch() -> None:
    teams = assign_teams(
        sides(
            (1, 1, "CT"), (1, 2, "CT"), (1, 3, "T"), (1, 4, "T"),
            (13, 1, "T"), (13, 2, "T"), (13, 3, "CT"), (13, 4, "CT"),
        )
    )  # fmt: skip
    assert teams.player_team == {1: "A", 2: "A", 3: "B", 4: "B"}
    assert teams.ct_team == {1: "A", 13: "B"}


def test_a_stand_in_joins_the_team_of_the_side_he_plays() -> None:
    teams = assign_teams(
        sides(
            (1, 1, "CT"), (1, 2, "T"),
            (13, 1, "T"), (13, 2, "CT"), (13, 9, "CT"),  # player 9 joins on CT after the switch
        )
    )  # fmt: skip
    assert teams.player_team[9] == "B"


def test_majority_wins_when_a_known_player_is_misplaced() -> None:
    teams = assign_teams(
        sides(
            (1, 1, "CT"), (1, 2, "CT"), (1, 3, "CT"), (1, 4, "T"),
            (2, 1, "CT"), (2, 2, "CT"), (2, 3, "T"), (2, 4, "T"),  # player 3 switched team
        )
    )  # fmt: skip
    assert teams.ct_team[2] == "A"
