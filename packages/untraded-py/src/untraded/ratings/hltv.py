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


def rating_hltv_2_approx(
    rounds: int,
    kills: int,
    deaths: int,
    assists: int,
    damage: int,
    kast_rounds: int,
) -> float:
    """Community approximation of HLTV Rating 2.0 (HLTV does not publish the formula).

    Always present it as "approx.": its error against HLTV's published values is not known.

    Args:
        rounds: Rounds played.
        kills: Total kills.
        deaths: Total deaths.
        assists: Total assists.
        damage: Total damage dealt to enemies.
        kast_rounds: Rounds with a kill, an assist, survival or a traded death.

    Returns:
        0.0073 * KAST + 0.3591 * KPR - 0.5329 * DPR + 0.2372 * Impact + 0.0032 * ADR + 0.1587,
        with KAST in % and Impact = 2.13 * KPR + 0.42 * APR - 0.41.
    """
    if rounds <= 0:
        raise ValueError("rounds must be positive")
    kpr, dpr, apr = kills / rounds, deaths / rounds, assists / rounds
    kast = kast_rounds / rounds * 100
    impact = 2.13 * kpr + 0.42 * apr - 0.41
    return (
        0.0073 * kast
        + 0.3591 * kpr
        - 0.5329 * dpr
        + 0.2372 * impact
        + 0.0032 * damage / rounds
        + 0.1587
    )
