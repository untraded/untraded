# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Metric registry, datasets, splits and the base metrics, on hand-made rounds."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl
import pytest

from untraded.metrics import REGISTRY, Dataset, compute
from untraded.metrics.docs import render


def round_player(rows: list[dict[str, Any]]) -> pl.DataFrame:
    defaults = {
        "kills": 0,
        "deaths": 0,
        "assists": 0,
        "flash_assists": 0,
        "damage": 0,
        "survived": False,
        "death_trade_delay_s": None,
        "team": "A",
    }
    return pl.DataFrame([{**defaults, **row} for row in rows])


def match(match_id: str, map_name: str, rows: list[dict[str, Any]]) -> dict[str, pl.DataFrame]:
    return {
        "match": pl.DataFrame({"match_id": [match_id], "map": [map_name]}),
        "round_player": round_player(rows),
        "kill": pl.DataFrame(
            schema={
                "round": pl.Int16,
                "tick": pl.Int32,
                "attacker": pl.Int64,
                "victim": pl.Int64,
                "headshot": pl.Boolean,
                "is_team_kill": pl.Boolean,
                "is_suicide": pl.Boolean,
            }
        ),
        "death": pl.DataFrame(
            schema={
                "round": pl.Int16,
                "tick": pl.Int32,
                "victim": pl.Int64,
                "killer": pl.Int64,
                "is_enemy_kill": pl.Boolean,
            }
        ),
    }


ONE = match(
    "m1",
    "de_nuke",
    [
        # player 1: kill + survive (CT), traded death after 4 s (T), nothing (T)
        {"round": 1, "steamid": 1, "side": "CT", "kills": 2, "survived": True, "damage": 150},
        {"round": 2, "steamid": 1, "side": "T", "deaths": 1, "death_trade_delay_s": 4.0},
        {"round": 3, "steamid": 1, "side": "T", "deaths": 1, "damage": 30},
    ],
)


def values(ds: Dataset, metric: str, **params: Any) -> dict[int, float | None]:
    out = compute(ds, [metric], params=params or None)
    return dict(zip(out["steamid"].to_list(), out["value"].to_list(), strict=True))


def test_totals_rates_and_multikills() -> None:
    ds = Dataset.from_matches([ONE])
    assert values(ds, "base.kills") == {1: 2.0}
    assert values(ds, "base.adr") == {1: 60.0}
    assert values(ds, "base.multikills_2") == {1: 1.0}
    assert values(ds, "base.kd_diff") == {1: 0.0}


def test_kast_uses_the_trade_window_parameter() -> None:
    ds = Dataset.from_matches([ONE])
    # rounds 1 (kill, survived) and 2 (traded after 4 s) count, round 3 does not
    assert values(ds, "base.kast") == {1: pytest.approx(200 / 3)}
    assert values(ds, "base.kast", **{"trade.window_s": 3.0}) == {1: pytest.approx(100 / 3)}


def test_a_flash_assist_counts_less_than_an_assist() -> None:
    ds = Dataset.from_matches(
        [
            match(
                "m",
                "de_nuke",
                [{"round": 1, "steamid": 1, "side": "CT", "assists": 2, "flash_assists": 2}],
            )
        ]
    )
    assert values(ds, "base.assist_score") == {1: 3.0}
    assert values(ds, "base.assist_score", **{"assist.flash_weight": 1.0}) == {1: 4.0}


def test_results_record_version_and_parameters() -> None:
    out = compute(Dataset.from_matches([ONE]), ["base.kast"], params={"trade.window_s": 3.0})
    assert out["version"][0] == REGISTRY["base.kast"].version
    assert '"trade.window_s": 3.0' in out["params"][0]
    with pytest.raises(ValueError, match="unknown parameters"):
        compute(Dataset.from_matches([ONE]), params={"trade.windw_s": 3.0})


def test_side_split_keeps_the_player_rounds_on_that_side() -> None:
    ds = Dataset.from_matches([ONE])
    assert values(ds.split(side="CT"), "base.adr") == {1: 150.0}
    assert values(ds.split(side="T"), "base.adr") == {1: 15.0}


def test_several_matches_are_recomputed_over_all_rounds() -> None:
    two = match("m2", "de_dust2", [{"round": 1, "steamid": 1, "side": "CT", "damage": 0}])
    ds = Dataset.from_matches([ONE, two])
    # (150 + 0 + 30 + 0) / 4 rounds, not the mean of 60 and 0
    assert values(ds, "base.adr") == {1: 45.0}
    assert values(ds.split(map="de_dust2"), "base.adr") == {1: 0.0}


def test_undefined_ratios_are_null() -> None:
    assert values(Dataset.from_matches([ONE]), "base.hs_pct") == {1: None}


def test_reference_documentation_is_up_to_date() -> None:
    reference = Path(__file__).parents[3] / "docs" / "metrics-reference.md"
    assert reference.read_text(encoding="utf-8") == render(), (
        "run `python -m untraded.metrics.docs` from the repository root"
    )
