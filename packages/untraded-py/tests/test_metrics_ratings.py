# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Rating metrics (metrics-v1 § 6) agree with the public rating functions."""

from __future__ import annotations

import polars as pl
import pytest

from untraded import rating_hltv_1, rating_hltv_2_approx
from untraded.metrics import Dataset, compute

# Player 1 over four rounds: 2K (survived), 0K died traded after 3 s, 1K with an assist then
# died untraded, 0K died untraded. Player 2 played no round on the CT side.
ROUND_PLAYER = pl.DataFrame(
    {
        "round": [1, 2, 3, 4, 1],
        "steamid": [1, 1, 1, 1, 2],
        "team": ["A"] * 5,
        "side": ["CT", "CT", "CT", "CT", "T"],
        "kills": [2, 0, 1, 0, 0],
        "deaths": [0, 1, 1, 1, 1],
        "assists": [0, 0, 1, 0, 0],
        "flash_assists": [0, 0, 0, 0, 0],
        "damage": [200, 30, 150, 0, 10],
        "survived": [True, False, False, False, False],
        "death_trade_delay_s": [None, 3.0, None, None, None],
    }
)


def dataset() -> Dataset:
    match = pl.DataFrame({"match_id": ["m"], "map": ["de_nuke"]})
    return Dataset.from_matches([{"match": match, "round_player": ROUND_PLAYER}])


def values(metric: str, ds: Dataset, **params: float) -> dict[int, float | None]:
    out = compute(ds, [metric], params=params or None)
    return dict(zip(out["steamid"].to_list(), out["value"].to_list(), strict=True))


def test_hltv1_matches_the_public_function() -> None:
    expected = rating_hltv_1(rounds=4, kills=3, deaths=3, multikills={1: 1, 2: 1})
    assert values("rating.hltv1", dataset())[1] == pytest.approx(expected)


def test_hltv2_approx_uses_kast_and_its_parameters() -> None:
    # KAST: rounds 1 (kill), 2 (traded in 3 s) and 3 (kill) = 3 of 4.
    expected = rating_hltv_2_approx(4, 3, 3, 1, 380, kast_rounds=3)
    assert values("rating.hltv2_approx", dataset())[1] == pytest.approx(expected)
    strict = rating_hltv_2_approx(4, 3, 3, 1, 380, kast_rounds=2)
    tighter = values("rating.hltv2_approx", dataset(), **{"trade.window_s": 2.0})
    assert tighter[1] == pytest.approx(strict)


def test_ratings_follow_splits() -> None:
    ct = dataset().split(side="CT")
    assert set(values("rating.hltv1", ct)) == {1}
    t = values("rating.hltv1", dataset().split(side="T"))
    assert t[2] == pytest.approx(rating_hltv_1(rounds=1, kills=0, deaths=1, multikills={}))


def test_hltv2_approx_formula() -> None:
    # KPR 1, DPR 0.5, APR 0.25, KAST 75 %, ADR 100: Impact = 2.13 + 0.105 - 0.41 = 1.825.
    rating = rating_hltv_2_approx(4, 4, 2, 1, 400, kast_rounds=3)
    expected = 0.0073 * 75 + 0.3591 - 0.5329 * 0.5 + 0.2372 * 1.825 + 0.32 + 0.1587
    assert rating == pytest.approx(expected)
    with pytest.raises(ValueError, match="rounds"):
        rating_hltv_2_approx(0, 0, 0, 0, 0, 0)
