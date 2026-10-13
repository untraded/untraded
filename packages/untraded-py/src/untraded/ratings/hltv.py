# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""HLTV Rating 1.0, from HLTV's public definition."""

from collections.abc import Mapping

# Reference averages from HLTV's public Rating 1.0 definition.
_AVG_KPR = 0.679
_AVG_SPR = 0.317
_AVG_MULTIKILL = 1.277


def rating_hltv_1(
    rounds: int,
    kills: int,
    deaths: int,
    multikills: Mapping[int, int],
) -> float:
    """Compute HLTV Rating 1.0 from match totals.

    Args:
        rounds: Rounds played.
        kills: Total kills.
        deaths: Total deaths.
        multikills: Number of rounds with exactly N kills, keyed by N (1 to 5).
            Example: ``{1: 8, 2: 3, 3: 1}``.

    Returns:
        (KillRating + 0.7 * SurvivalRating + MultiKillRating) / 2.7, where each
        component is the player's per-round value divided by the reference average.
    """
    if rounds <= 0:
        raise ValueError("rounds must be positive")
    if any(n not in range(1, 6) for n in multikills):
        raise ValueError("multikills keys must be between 1 and 5")

    kill_rating = kills / rounds / _AVG_KPR
    survival_rating = (rounds - deaths) / rounds / _AVG_SPR
    multikill_points = sum(n * n * count for n, count in multikills.items())
    multikill_rating = multikill_points / rounds / _AVG_MULTIKILL
    return (kill_rating + 0.7 * survival_rating + multikill_rating) / 2.7
