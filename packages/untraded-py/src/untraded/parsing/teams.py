# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Stable teams A and B across side switches (docs/canonical-tables.md § 1).

Team A is the team on CT at the first live round. Sides switch at half-time and in overtime, and
players may join late (stand-ins, reconnections), so each round is resolved from the players
already known, by majority, before new players are placed.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import polars as pl

OTHER = {"A": "B", "B": "A"}


@dataclass(frozen=True)
class Teams:
    player_team: dict[int, str]
    """steamid -> `A` or `B`."""
    ct_team: dict[int, str]
    """round -> the team on CT in that round."""


def assign_teams(sides: pl.DataFrame) -> Teams:
    """`sides`: one row per round and player on a team, columns `round`, `steamid`, `side`."""
    player_team: dict[int, str] = {}
    ct_team: dict[int, str] = {}
    for (number,), group in sides.sort("round").group_by("round", maintain_order=True):
        rows = list(zip(group["steamid"].to_list(), group["side"].to_list(), strict=True))
        votes: Counter[str] = Counter()
        for steamid, side in rows:
            if (team := player_team.get(steamid)) is not None:
                votes[team if side == "CT" else OTHER[team]] += 1
        ct = votes.most_common(1)[0][0] if votes else "A"
        ct_team[int(number)] = ct
        for steamid, side in rows:
            player_team.setdefault(steamid, ct if side == "CT" else OTHER[ct])
    return Teams(player_team=player_team, ct_team=ct_team)
