# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import polars as pl

from untraded.metrics import REGISTRY
from untraded_worker.analysis import SCOPES, Analysis
from untraded_worker.load import sql_frames


def test_every_value_metric_for_every_player_and_scope(analysis: Analysis) -> None:
    players = analysis.tables["player"].height
    values = sum(1 for m in REGISTRY.values() if m.kind == "value")
    assert analysis.values.height == len(SCOPES) * players * values
    assert set(analysis.values["scope"]) == set(SCOPES)


def test_table_metrics_keep_their_own_columns_only(analysis: Analysis) -> None:
    assert set(analysis.table_values) == {m.id for m in REGISTRY.values() if m.kind == "table"}
    for frame in analysis.table_values.values():
        assert "steamid" in frame.columns
        assert not {"metric", "version", "params", "match_id"} & set(frame.columns)


def test_sql_frames_number_the_rows_of_a_tick(analysis: Analysis) -> None:
    frames = sql_frames(analysis)
    for table in ("kill", "damage", "blind"):
        frame = frames[table]
        assert frame.height == analysis.tables[table].height
        assert frame.select(pl.struct("tick", "seq").is_unique().all()).item()


def test_round_player_carries_the_team_buy_type(analysis: Analysis) -> None:
    frame = sql_frames(analysis)["round_player"]
    assert frame.height == analysis.tables["round_player"].height
    assert frame["buy_type"].null_count() == 0
