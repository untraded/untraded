# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Anonymized canonical extracts of a match (ADR 0010), for tests and bug reports.

An extract keeps a window of consecutive rounds, so it is still a valid match: one with a
truncated start (ADR 0008), whose score is the real score after the last round kept. Players are
renumbered 1 to N (team A first, then team B, by steamid) and named `A1`, `B1`...; the server,
team names, date, rank and match id are removed, and every knife becomes `knife` (a knife skin
is close to a signature of its owner). Positions, ticks and events are unchanged.

A fixture directory holds one Parquet file per canonical table, `fixture.toml` (window, map,
mode, versions) and `expected_metrics.json` (every metric of the registry on the extract), so
the derived tables and metrics can be checked without the demo. The source demo is not named
there: the public corpus manifest would date the match and lead back to its players. The
fixture-to-demo mapping is kept privately (`UNTRADED_FIXTURE_SOURCES`, see the parser test).
"""

from __future__ import annotations

import json
import math
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import polars as pl

from untraded.derive import derive
from untraded.metrics import REGISTRY, Dataset, compute, compute_table
from untraded.parsing.schema import SCHEMA_VERSION, TABLES
from untraded.parsing.validate import validate

Tables = dict[str, pl.DataFrame]

META = "fixture.toml"
EXPECTED = "expected_metrics.json"
DECIMALS = 6

PLAYER_COLUMNS: dict[str, tuple[str, ...]] = {
    "player": ("steamid",),
    "round": ("bomb_planter", "bomb_defuser"),
    "kill": ("attacker", "victim", "assister"),
    "damage": ("attacker", "victim"),
    "blind": ("victim", "flasher"),
    "bomb": ("player",),
    "economy": ("steamid",),
    "shot": ("shooter",),
    "grenade": ("thrower",),
    "inventory_change": ("steamid",),
    "player_tick": ("steamid", "spotted_by"),
}
"""Every column holding a steamid (personal data, ADR 0010)."""

ITEM_COLUMNS: dict[str, tuple[str, ...]] = {
    "economy": ("inventory",),
    "inventory_change": ("inventory",),
    "kill": ("victim_inventory",),
}
"""Inventories (item names, such as "Butterfly Knife")."""
ITEM_NAME_COLUMNS: dict[str, tuple[str, ...]] = {
    "player_tick": ("active_weapon",),
}
"""Single item names (the weapon in hand, such as "Butterfly Knife")."""
WEAPON_COLUMNS: dict[str, tuple[str, ...]] = {
    "kill": ("weapon",),
    "damage": ("weapon",),
    "shot": ("weapon",),
}
"""Weapon class names (such as `knife_butterfly`)."""
KNIFE = "knife"


def _is_knife_item(item: pl.Expr) -> pl.Expr:
    return item.str.contains("(?i)knife|bayonet|karambit|daggers")


def _is_knife_weapon(weapon: pl.Expr) -> pl.Expr:
    return weapon.str.starts_with("knife") | weapon.str.starts_with("bayonet")


def generic_knives(tables: Mapping[str, pl.DataFrame]) -> Tables:
    """Every knife, in inventories and as a weapon, becomes `knife`."""
    out = dict(tables)
    for table, columns in ITEM_COLUMNS.items():
        out[table] = out[table].with_columns(
            pl.col(c).list.eval(
                pl.when(_is_knife_item(pl.element())).then(pl.lit(KNIFE)).otherwise(pl.element())
            )
            for c in columns
        )
    for table, columns in ITEM_NAME_COLUMNS.items():
        out[table] = out[table].with_columns(
            pl.when(_is_knife_item(pl.col(c))).then(pl.lit(KNIFE)).otherwise(pl.col(c)).alias(c)
            for c in columns
        )
    for table, columns in WEAPON_COLUMNS.items():
        out[table] = out[table].with_columns(
            pl.when(_is_knife_weapon(pl.col(c))).then(pl.lit(KNIFE)).otherwise(pl.col(c)).alias(c)
            for c in columns
        )
    return out


class FixtureError(ValueError):
    """The window or the extract is not usable."""


def extract(tables: Mapping[str, pl.DataFrame], first: int, last: int) -> Tables:
    """Rounds `first` to `last` of a match, as a valid match with a truncated start."""
    rounds = tables["round"].filter(pl.col("round").is_between(first, last))
    if rounds.height != last - first + 1:
        raise FixtureError(f"rounds {first}-{last} are not all in the match")
    out = {
        name: frame.filter(pl.col("round").is_between(first, last))
        for name, frame in tables.items()
        if "round" in frame.columns
    }
    kept = out["grenade"]["grenade_id"].to_list()
    out["grenade_path"] = tables["grenade_path"].filter(pl.col("grenade_id").is_in(kept))

    # Players on a team at the freeze end of a kept round, as the adapter counts them.
    freeze_ends = rounds.select("round", pl.col("freeze_end_tick").alias("tick"))
    on_team = (
        out["player_tick"]
        .join(freeze_ends, on=["round", "tick"], how="semi")
        .group_by("steamid")
        .agg(pl.len().cast(pl.Int16).alias("rounds_on_team"))
    )
    out["player"] = (
        tables["player"]
        .drop("rounds_on_team")
        .join(on_team, on="steamid", how="inner")
        .select(TABLES["player"].names())
    )
    last_round = rounds.row(-1, named=True)
    out["match"] = tables["match"].with_columns(
        pl.lit(first, pl.Int16).alias("first_round"),
        pl.lit(rounds.height, pl.Int16).alias("rounds_played"),
        pl.lit(last_round["score_a"], pl.Int16).alias("score_a"),
        pl.lit(last_round["score_b"], pl.Int16).alias("score_b"),
    )
    return {name: out[name] for name in TABLES}


def anonymize(tables: Mapping[str, pl.DataFrame], name: str) -> Tables:
    """Replaces steamids, names, knives and identifying match fields. Raises if a steamid of an
    event is not a player of the extract, so nothing personal can slip through."""
    players = tables["player"].sort("team", "steamid")
    ids = players["steamid"].to_list()
    mapping = {old: new for new, old in enumerate(ids, start=1)}
    counters = {"A": 0, "B": 0}
    names = []
    for team in players["team"].to_list():
        counters[team] += 1
        names.append(f"{team}{counters[team]}")

    out: Tables = {}
    for table, frame in tables.items():
        replaced = frame
        for column in PLAYER_COLUMNS.get(table, ()):
            values = frame[column].explode() if frame[column].dtype == pl.List else frame[column]
            unknown = set(values.drop_nulls().unique().to_list()) - set(mapping) - {0}
            if unknown:
                raise FixtureError(
                    f"{table}.{column}: {len(unknown)} steamid(s) not in the players"
                )
            expr = pl.col(column)
            if frame[column].dtype == pl.List:
                mapped = expr.list.eval(pl.element().replace(mapping))
            else:
                mapped = expr.replace(mapping)
            replaced = replaced.with_columns(mapped.cast(frame[column].dtype))
        out[table] = replaced
    out = generic_knives(out)
    out["player"] = (
        out["player"]
        .sort("steamid")
        .with_columns(
            pl.Series("name", names),
            pl.lit(None, pl.Int32).alias("rank"),
            pl.lit(None, pl.Int32).alias("comp_wins"),
        )
    )
    out["match"] = out["match"].with_columns(
        pl.lit(f"fixture-{name}").alias("match_id"),
        pl.lit(None, pl.Date).alias("played_at"),
        pl.lit("anonymized").alias("server_name"),
        pl.lit(None, pl.String).alias("team_a_name"),
        pl.lit(None, pl.String).alias("team_b_name"),
    )
    validate(out)
    return out


def expected_metrics(tables: Mapping[str, pl.DataFrame]) -> dict[str, Any]:
    """Every metric of the registry on the extract, by player name, rounded for stable diffs."""
    ds = Dataset.from_matches([{**tables, **derive(dict(tables)).tables()}])
    names = dict(tables["player"].select("steamid", "name").iter_rows())
    values: dict[str, dict[str, float | None]] = {}
    for row in compute(ds).sort("metric", "steamid").iter_rows(named=True):
        values.setdefault(names[row["steamid"]], {})[row["metric"]] = _round(row["value"])
    table_metrics = {}
    for metric_id in sorted(m.id for m in REGISTRY.values() if m.kind == "table"):
        frame = compute_table(ds, metric_id).drop(
            "metric", "version", "params", "match_id", strict=False
        )
        if "steamid" in frame.columns:
            frame = frame.with_columns(
                pl.col("steamid").replace_strict(names, return_dtype=pl.String)
            )
        rows = [{k: _round(v) for k, v in r.items()} for r in frame.iter_rows(named=True)]
        table_metrics[metric_id] = sorted(rows, key=lambda r: json.dumps(r, sort_keys=True))
    return {
        "versions": {m.id: m.version for m in sorted(REGISTRY.values(), key=lambda m: m.id)},
        "players": dict(sorted(values.items())),
        "tables": table_metrics,
    }


def _round(value: Any) -> Any:
    if isinstance(value, float):
        return None if math.isnan(value) else round(value, DECIMALS)
    return value


def write(directory: Path, tables: Mapping[str, pl.DataFrame], meta: Mapping[str, Any]) -> None:
    """Writes the tables, `fixture.toml` and `expected_metrics.json`."""
    directory.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        frame.write_parquet(directory / f"{name}.parquet", compression="zstd", compression_level=22)
    lines = [f"{key} = {json.dumps(value)}" for key, value in meta.items()]
    (directory / META).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    write_expected(directory, tables)


def write_expected(directory: Path, tables: Mapping[str, pl.DataFrame]) -> None:
    text = json.dumps(expected_metrics(tables), indent=1, ensure_ascii=False) + "\n"
    (directory / EXPECTED).write_text(text, encoding="utf-8", newline="\n")


def read(directory: Path) -> Tables:
    """The tables of a fixture, validated."""
    tables = {name: pl.read_parquet(directory / f"{name}.parquet") for name in TABLES}
    validate(tables)
    return tables


def read_meta(directory: Path) -> dict[str, Any]:
    return tomllib.loads((directory / META).read_text(encoding="utf-8"))


def read_expected(directory: Path) -> dict[str, Any]:
    result: dict[str, Any] = json.loads((directory / EXPECTED).read_text(encoding="utf-8"))
    return result


def metadata(*, first: int, last: int, tables: Mapping[str, pl.DataFrame]) -> dict[str, Any]:
    """What `fixture.toml` records. Not the source demo: see the module docstring."""
    info = tables["match"].row(0, named=True)
    return {
        "rounds": [first, last],
        "mode": info["mode"],
        "map": info["map"],
        "schema_version": SCHEMA_VERSION,
        "parser": f"{info['parser']} {info['parser_version']}",
    }
