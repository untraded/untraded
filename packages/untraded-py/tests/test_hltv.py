# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
import pytest
from hypothesis import given
from hypothesis import strategies as st

from untraded import rating_hltv_1


def test_reference_average_player_rates_one() -> None:
    # 679 kills spread as 180 x 1K, 200 x 2K, 33 x 3K: KPR 0.679,
    # survival 0.317 and multi-kill points 1277 over 1000 rounds.
    rating = rating_hltv_1(rounds=1000, kills=679, deaths=683, multikills={1: 180, 2: 200, 3: 33})
    assert rating == pytest.approx(1.0, abs=1e-9)


def test_better_player_rates_higher() -> None:
    assert rating_hltv_1(rounds=24, kills=30, deaths=12, multikills={1: 8, 2: 5, 3: 4}) > 1.5


def test_rejects_zero_rounds() -> None:
    with pytest.raises(ValueError, match="rounds"):
        rating_hltv_1(rounds=0, kills=0, deaths=0, multikills={})


def test_rejects_invalid_multikill_key() -> None:
    with pytest.raises(ValueError, match="multikills"):
        rating_hltv_1(rounds=10, kills=6, deaths=5, multikills={6: 1})


@given(
    rounds=st.integers(min_value=1, max_value=60),
    kills=st.integers(min_value=0, max_value=60),
    deaths=st.integers(min_value=0, max_value=60),
)
def test_one_more_kill_never_lowers_rating(rounds: int, kills: int, deaths: int) -> None:
    before = rating_hltv_1(rounds, kills, deaths, {1: kills})
    after = rating_hltv_1(rounds, kills + 1, deaths, {1: kills + 1})
    assert after > before


@given(
    rounds=st.integers(min_value=1, max_value=60),
    kills=st.integers(min_value=0, max_value=60),
    deaths=st.integers(min_value=0, max_value=59),
)
def test_one_more_death_lowers_rating(rounds: int, kills: int, deaths: int) -> None:
    assert rating_hltv_1(rounds, kills, deaths + 1, {}) < rating_hltv_1(rounds, kills, deaths, {})
