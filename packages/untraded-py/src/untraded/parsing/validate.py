# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Validation on creation (docs/canonical-tables.md § 5), for the tables built so far."""

from __future__ import annotations

import polars as pl

from untraded.parsing.schema import TABLES, CanonicalError


def validate(tables: dict[str, pl.DataFrame]) -> None:
    """Raises CanonicalError on the first broken rule."""
    for name, frame in tables.items():
        if frame.schema != TABLES[name]:
            raise CanonicalError(f"{name}: schema differs from the spec")

    match, rounds, players = tables["match"], tables["round"], tables["player"]
    if match.height != 1:
        raise CanonicalError(f"match: {match.height} rows, expected 1")
    info = match.row(0, named=True)

    numbers = rounds["round"].to_list()
    first, last = numbers[0], numbers[-1]
    if numbers != list(range(first, last + 1)):
        raise CanonicalError(f"round: numbers are not consecutive: {numbers}")
    if first != info["first_round"] or len(numbers) != info["rounds_played"]:
        raise CanonicalError("match: first_round or rounds_played disagree with the round table")
    # Scores count every round, including those before a truncated start (ADR 0008).
    if info["score_a"] + info["score_b"] != last:
        raise CanonicalError(
            f"match: score {info['score_a']}-{info['score_b']} does not add up to {last} rounds"
        )
    ordered = rounds.select(
        (pl.col("start_tick") <= pl.col("freeze_end_tick"))
        & (pl.col("freeze_end_tick") < pl.col("end_tick"))
        & (pl.col("end_tick") < pl.col("start_tick").shift(-1).fill_null(2**31 - 1))
    )
    if not ordered.to_series().all():
        raise CanonicalError("round: ticks are not ordered start <= freeze end < end < next start")

    live = rounds["round"].to_list()
    for name in ("kill", "damage", "blind", "bomb", "shot", "grenade_path"):
        events = tables[name]
        if not events.height:
            continue
        if not events["tick"].is_sorted():
            raise CanonicalError(f"{name}: ticks are not increasing")
        if "round" in events.columns and (
            events["round"].null_count() or not events["round"].is_in(live).all()
        ):
            raise CanonicalError(f"{name}: an event has no live round")

    damage = tables["damage"]
    if (
        damage.height
        and not damage.select(
            pl.col("damage").is_between(0, 100) & (pl.col("damage") <= pl.col("dmg_health"))
        )
        .to_series()
        .all()
    ):
        raise CanonicalError("damage: capped damage outside 0-100 or above dmg_health")

    grenades = tables["grenade"]
    if grenades.height:
        if not grenades["throw_tick"].is_sorted():
            raise CanonicalError("grenade: throws are not in tick order")
        if grenades["round"].null_count() or not grenades["round"].is_in(live).all():
            raise CanonicalError("grenade: a throw has no live round")
        if grenades["grenade_id"].n_unique() != grenades.height:
            raise CanonicalError("grenade: duplicate grenade_id")
    known = grenades["grenade_id"].to_list()
    for name in ("grenade_path", "damage", "blind"):
        ids = tables[name]["grenade_id"].drop_nulls()
        if not ids.is_in(known).all():
            raise CanonicalError(f"{name}: grenade_id not in the grenade table")

    economy = tables["economy"]
    if economy.select("round", "steamid").is_duplicated().any():
        raise CanonicalError("economy: more than one row per player and round")

    if players["steamid"].n_unique() != players.height:
        raise CanonicalError("player: duplicate steamid")
