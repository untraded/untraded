# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Comparison with CS Demo Manager's analyzer (workstream E8).

`cs-demo-analyzer` (`csda`, MIT, https://github.com/akiver/cs-demo-analyzer) exports a match as
JSON. Its per-player stats are matched with ours, player by player; docs/validation-csdm.md
explains every remaining gap.

Rules: counts must be equal; ratios (ADR, KAST, ratings) must be within 1 %.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Literal

import polars as pl

from untraded.demofile import plain_demo
from untraded.metrics import Dataset, compute

Rule = Literal["exact", "1%"]


@dataclass(frozen=True)
class Field:
    csdm: str
    """Per-player field of the export."""
    ours: str
    """Column of `our_values`."""
    rule: Rule


FIELDS = (
    Field("killCount", "kills", "exact"),
    Field("deathCount", "deaths", "exact"),
    Field("assistCount", "assists", "exact"),
    Field("headshotCount", "headshots", "exact"),
    *(
        Field(f"{word}KillCount", f"multikills_{n}", "exact")
        for n, word in enumerate(("one", "two", "three", "four", "five"), start=1)
    ),
    Field("firstKillCount", "opening_kills", "exact"),
    Field("firstDeathCount", "opening_deaths", "exact"),
    Field("tradeKillCount", "trade_kills", "exact"),
    Field("tradeDeathCount", "traded_deaths", "exact"),
    Field("utilityDamage", "grenade_damage", "exact"),
    Field("averageDamagePerRound", "adr", "1%"),
    Field("kast", "kast", "1%"),
    Field("hltvRating", "hltv1", "1%"),
    Field("hltvRating2", "hltv2_approx", "1%"),
)
CLUTCH_FIELDS = tuple(
    Field(f"clutch_{kind}_1v{n}", f"clutch_{kind}_1v{n}", "exact")
    for n in range(1, 6)
    for kind in ("attempts", "wins")
)
"""From the export's `clutches` list: its per-player clutch counters do not add up (a player
can have more 1vN attempts than rounds played)."""

_METRICS = {
    "kills": "base.kills",
    "deaths": "base.deaths",
    "adr": "base.adr",
    "kast": "base.kast",
    "opening_kills": "duel.opening_kills",
    "opening_deaths": "duel.opening_deaths",
    "trade_kills": "trade.trade_kills",
    "traded_deaths": "trade.traded_deaths",
    "hltv1": "rating.hltv1",
    "hltv2_approx": "rating.hltv2_approx",
    **{f"multikills_{n}": f"base.multikills_{n}" for n in range(1, 6)},
    **{f"clutch_{k}_1v{n}": f"clutch.{k}_1v{n}" for n in range(1, 6) for k in ("attempts", "wins")},
}
GRENADES = ("hegrenade", "inferno", "molotov", "incgrenade", "smokegrenade", "flashbang", "decoy")


def run_csda(csda: Path, demo: Path, target: Path) -> Path:
    """Runs the analyzer on `demo` (decompressed first if needed) and writes its JSON export to
    `target`."""
    with plain_demo(demo) as dem, TemporaryDirectory(prefix="untraded-csda-") as tmp:
        subprocess.run(
            [str(csda), "-demo-path", str(dem), "-format", "json", "-output", tmp],
            check=True,
            capture_output=True,
        )
        (exported,) = Path(tmp).glob("*.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        exported.replace(target)
    return target


def csdm_values(export: Mapping[str, Any]) -> pl.DataFrame:
    """One row per player: `steamid`, `name`, and one column per compared field."""
    rows = []
    for player in export["players"].values():
        row: dict[str, Any] = {"steamid": player["steamId"], "name": player["name"]}
        row.update({f.ours: float(player[f.csdm]) for f in FIELDS})
        row.update(dict.fromkeys((f.ours for f in CLUTCH_FIELDS), 0.0))
        rows.append(row)
    by_player = {row["steamid"]: row for row in rows}
    for clutch in export.get("clutches") or []:
        clutcher = by_player.get(clutch["clutcherSteamId"])
        if clutcher is None:
            continue
        n = clutch["opponentCount"]
        clutcher[f"clutch_attempts_1v{n}"] += 1
        clutcher[f"clutch_wins_1v{n}"] += 1 if clutch["hasWon"] else 0
    return pl.DataFrame(rows).with_columns(pl.col("steamid").cast(pl.UInt64))


def our_values(ds: Dataset) -> pl.DataFrame:
    """Our stats of one match, under the names of `csdm_values` (CSDM's definitions where they
    only differ by scope: assists include flash assists, utility damage every grenade)."""
    ids = sorted({*_METRICS.values(), "base.assists", "base.flash_assists", "base.hs_pct"})
    wide = compute(ds, ids).pivot(on="metric", index="steamid", values="value")
    grenade = (
        ds["damage"]
        .filter(pl.col("weapon").is_in(GRENADES) & ~pl.col("is_team_damage"))
        .filter(pl.col("attacker") != pl.col("victim"))
        .group_by(pl.col("attacker").alias("steamid"))
        .agg(pl.col("damage").sum().cast(pl.Float64).alias("grenade_damage"))
    )
    return (
        wide.select(
            "steamid",
            *(pl.col(metric).alias(name) for name, metric in _METRICS.items()),
            (pl.col("base.assists") + pl.col("base.flash_assists")).alias("assists"),
            (pl.col("base.hs_pct") * pl.col("base.kills") / 100)
            .round(0)
            .fill_null(0.0)
            .alias("headshots"),
        )
        .join(grenade, on="steamid", how="left")
        .with_columns(pl.col("grenade_damage").fill_null(0.0))
    )


def compare(ours: pl.DataFrame, csdm: pl.DataFrame) -> pl.DataFrame:
    """Long table: `steamid`, `name`, `field`, `rule`, `csdm`, `ours`, `diff`, `gap`.

    A player missing on one side has null values and counts as a gap.
    """
    frames = []
    for f in (*FIELDS, *CLUTCH_FIELDS):
        frames.append(
            csdm.select("steamid", "name", pl.col(f.ours).alias("csdm"))
            .join(ours.select("steamid", pl.col(f.ours).alias("ours")), on="steamid", how="full")
            .select(
                pl.coalesce("steamid", "steamid_right").alias("steamid"),
                "name",
                pl.lit(f.ours).alias("field"),
                pl.lit(f.rule).alias("rule"),
                "csdm",
                "ours",
            )
        )
    long = pl.concat(frames).with_columns((pl.col("ours") - pl.col("csdm")).alias("diff"))
    tolerance = pl.when(pl.col("rule") == "exact").then(0.0).otherwise(pl.col("csdm").abs() * 0.01)
    return long.with_columns((pl.col("diff").abs() > tolerance + 1e-6).fill_null(True).alias("gap"))


def summary(comparison: pl.DataFrame) -> pl.DataFrame:
    """Per field: players compared, gaps, and the largest difference."""
    return comparison.group_by("field", "rule", maintain_order=True).agg(
        pl.len().alias("players"),
        pl.col("gap").sum().alias("gaps"),
        pl.col("diff").abs().max().alias("max_abs_diff"),
    )


def load_export(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data
