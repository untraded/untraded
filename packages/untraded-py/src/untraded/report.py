# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The match report of `untraded analyze` (workstream E7): per player, per side, key rounds.

`build_report` works on one match's canonical and derived tables; `render_table` and `to_json`
are its two outputs (terminal and machine-readable).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import polars as pl

from untraded.metrics import REGISTRY, Dataset, compute

SUMMARY = {
    "base.kills": "K",
    "base.deaths": "D",
    "base.assists": "A",
    "base.kd_diff": "+/-",
    "base.adr": "ADR",
    "base.hs_pct": "HS%",
    "base.kast": "KAST%",
    "duel.opening_kills": "OK",
    "trade.untraded_deaths": "UD",
    "rating.hltv1": "HLTV1",
    "rating.hltv2_approx": "HLTV2~",
}
"""Columns of the terminal table."""
BY_SIDE = {
    "base.kills": "K",
    "base.deaths": "D",
    "base.adr": "ADR",
    "base.kast": "KAST%",
    "rating.hltv1": "HLTV1",
}
DECIMALS = {"rating.hltv1": 2, "rating.hltv2_approx": 2}
MULTI_KILL = {3: "3K", 4: "4K", 5: "ACE"}
UPSET_BUYS = ("eco", "force")
"""A team wins with this buy against a full buy: a key round."""
APPROX_NOTE = "HLTV2~: community approximation of HLTV Rating 2.0 (approx.)"


@dataclass(frozen=True)
class KeyRound:
    round: int
    score_a: int
    score_b: int
    winner_team: str | None
    winner_side: str | None
    reason: str | None
    events: tuple[str, ...]


@dataclass(frozen=True)
class Report:
    match: dict[str, Any]
    side: str | None
    """The rounds kept: `CT`, `T`, or None for all."""
    players: pl.DataFrame
    """One row per player: `steamid`, `name`, `team`, then one column per value metric."""
    sides: pl.DataFrame
    """One row per player and side: `steamid`, `name`, `team`, `side`, then the metrics."""
    key_rounds: tuple[KeyRound, ...]


def build_report(tables: Mapping[str, pl.DataFrame], *, side: str | None = None) -> Report:
    """`tables`: one match's canonical tables and its round model (`derive(...).tables()`)."""
    full = Dataset.from_matches([tables])
    dataset = full.split(side=side) if side else full
    names = tables["player"].select("steamid", "name", "team")
    players = names.join(_wide(compute(dataset)), on="steamid")
    sides = pl.concat(
        [
            names.join(_wide(compute(full.split(side=s), list(BY_SIDE))), on="steamid").select(
                "steamid", "name", "team", pl.lit(s).alias("side"), *BY_SIDE
            )
            for s in ((side,) if side else ("CT", "T"))
        ]
    )
    players = players.sort("team", "base.kills", descending=[False, True])
    order = players.select("steamid").with_row_index("order")
    return Report(
        match=tables["match"].drop("unavailable", "events_available").row(0, named=True),
        side=side,
        players=players,
        sides=sides.join(order, on="steamid").sort("order", "side").drop("order"),
        key_rounds=_key_rounds(tables, dict(names.select("steamid", "name").iter_rows())),
    )


def _wide(results: pl.DataFrame) -> pl.DataFrame:
    return results.pivot(on="metric", index="steamid", values="value")


def _key_rounds(tables: Mapping[str, pl.DataFrame], names: dict[int, str]) -> tuple[KeyRound, ...]:
    events: dict[int, list[str]] = {}
    for row in tables["round_player"].filter(pl.col("kills") >= 3).iter_rows(named=True):
        label = MULTI_KILL[min(row["kills"], 5)]
        events.setdefault(row["round"], []).append(f"{names.get(row['steamid'], '?')} {label}")
    for row in tables["clutch"].filter(pl.col("won")).iter_rows(named=True):
        who = names.get(row["steamid"], "?")
        events.setdefault(row["round"], []).append(f"{who} wins a 1v{row['enemies']}")
    buys = tables["team_round"].select("round", "team", "won", pl.col("buy_type").cast(pl.String))
    opponents = buys.select(
        "round", pl.col("team").alias("opponent"), pl.col("buy_type").alias("opponent_buy")
    )
    upsets = buys.join(opponents, on="round").filter(
        (pl.col("team") != pl.col("opponent"))
        & pl.col("won")
        & pl.col("buy_type").is_in(UPSET_BUYS)
        & (pl.col("opponent_buy") == "full")
    )
    for row in upsets.iter_rows(named=True):
        events.setdefault(row["round"], []).append(
            f"team {row['team']} wins {'an' if row['buy_type'] == 'eco' else 'a'} "
            f"{row['buy_type']} round against a full buy"
        )
    rounds = tables["round"].filter(pl.col("round").is_in(list(events))).sort("round")
    return tuple(
        KeyRound(
            round=row["round"],
            score_a=row["score_a"],
            score_b=row["score_b"],
            winner_team=row["winner_team"],
            winner_side=row["winner_side"],
            reason=row["reason"],
            events=tuple(events[row["round"]]),
        )
        for row in rounds.iter_rows(named=True)
    )


def _cell(value: float | None, metric: str) -> str:
    return f"{value:>7.{DECIMALS.get(metric, 0)}f}" if value is not None else f"{'-':>7}"


def render_table(report: Report) -> str:
    info = report.match
    side = f", {report.side} side" if report.side else ""
    lines = [
        f"{info['map']} {info['score_a']}-{info['score_b']} ({info['rounds_played']} rounds{side})",
        "",
        f"{'team':<5}{'player':<24}" + "".join(f"{label:>7}" for label in SUMMARY.values()),
    ]
    for row in report.players.iter_rows(named=True):
        cells = "".join(_cell(row.get(key), key) for key in SUMMARY)
        lines.append(f"{row['team']:<5}{row['name'][:23]:<24}{cells}")
    lines += [
        APPROX_NOTE,
        "",
        "By side",
        f"{'team':<5}{'player':<24}{'side':>5}" + "".join(f"{lbl:>7}" for lbl in BY_SIDE.values()),
    ]
    for row in report.sides.iter_rows(named=True):
        cells = "".join(_cell(row[key], key) for key in BY_SIDE)
        lines.append(f"{row['team']:<5}{row['name'][:23]:<24}{row['side']:>5}{cells}")
    lines += ["", "Key rounds"]
    if not report.key_rounds:
        lines.append("(none)")
    for kr in report.key_rounds:
        won = f"{kr.winner_side or '?'} ({kr.reason or '?'})"
        lines.append(
            f"R{kr.round:<3} {kr.score_a:>2}-{kr.score_b:<2}  {won:<26} " + "; ".join(kr.events)
        )
    return "\n".join(lines)


def to_json(report: Report) -> dict[str, Any]:
    """JSON-ready report. Steam ids are strings (64-bit integers lose precision in JavaScript);
    metrics are keyed by their registry id, with their versions alongside."""
    metric_ids = [c for c in report.players.columns if c in REGISTRY]
    by_side: dict[int, dict[str, dict[str, float | None]]] = {}
    for row in report.sides.iter_rows(named=True):
        by_side.setdefault(row["steamid"], {})[row["side"]] = {k: row[k] for k in BY_SIDE}
    match = {k: v.isoformat() if hasattr(v, "isoformat") else v for k, v in report.match.items()}
    return {
        "match": match,
        "side": report.side,
        "metric_versions": {m: REGISTRY[m].version for m in metric_ids},
        "players": [
            {
                "steamid": str(row["steamid"]),
                "name": row["name"],
                "team": row["team"],
                "metrics": {m: row[m] for m in metric_ids},
                "by_side": by_side.get(row["steamid"], {}),
            }
            for row in report.players.iter_rows(named=True)
        ],
        "key_rounds": [
            {
                "round": kr.round,
                "score": [kr.score_a, kr.score_b],
                "winner_team": kr.winner_team,
                "winner_side": kr.winner_side,
                "reason": kr.reason,
                "events": list(kr.events),
            }
            for kr in report.key_rounds
        ],
    }
