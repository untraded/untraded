# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""demoparser2 -> canonical tables (ADR 0002, 0008; docs/canonical-tables.md).

pandas frames from demoparser2 are converted to Polars at once and never leave this package.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, fields
from importlib.metadata import version
from pathlib import Path

import polars as pl
from demoparser2 import DemoParser

from untraded.demofile import digest, plain_demo
from untraded.parsing._context import Context, frame, side
from untraded.parsing.bomb import build_bomb
from untraded.parsing.combat import build_blind, build_damage
from untraded.parsing.core import build_kills, build_players, build_rounds
from untraded.parsing.economy import build_economy
from untraded.parsing.rounds import cut_rounds
from untraded.parsing.schema import MODES, SCHEMA_VERSION, CanonicalError, conform
from untraded.parsing.teams import OTHER, assign_teams
from untraded.parsing.validate import validate

STATE_PROPS = [
    "is_freeze_period",
    "is_warmup_period",
    "total_rounds_played",
    "round_win_status",
    "round_win_reason",
    "game_time",
]
ROUND_PROPS = ["team_num", "team_rounds_total", "team_clan_name", "rank", "comp_wins"]


class UnsupportedModeError(ValueError):
    """The game mode is not analysed (e.g. Wingman, Competitive): filter it before parsing."""


@dataclass(frozen=True)
class CanonicalMatch:
    match: pl.DataFrame
    player: pl.DataFrame
    round: pl.DataFrame
    kill: pl.DataFrame
    damage: pl.DataFrame
    blind: pl.DataFrame
    bomb: pl.DataFrame
    economy: pl.DataFrame

    @property
    def match_id(self) -> str:
        return str(self.match["match_id"][0])

    def tables(self) -> dict[str, pl.DataFrame]:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    def write(self, root: Path) -> Path:
        """Writes `root/matches/{match_id}/{table}.parquet` (zstd); returns the match directory."""
        target = root / "matches" / self.match_id
        target.mkdir(parents=True, exist_ok=True)
        for name, table in self.tables().items():
            table.write_parquet(target / f"{name}.parquet", compression="zstd")
        return target


def parse_demo(
    path: Path,
    *,
    source: str,
    mode: str,
    played_at: dt.date | None = None,
    match_id: str | None = None,
) -> CanonicalMatch:
    """Parses a demo (plain or compressed) into validated canonical tables.

    `source`, `mode` and `played_at` come from ingestion: the demo carries none of them.
    `match_id` defaults to the sha256 of the decompressed demo (pass it when already known).
    """
    if mode not in MODES:
        raise UnsupportedModeError(f"mode {mode!r} is not analysed (supported: {', '.join(MODES)})")
    match_id = match_id or digest(path).sha256
    with plain_demo(path) as dem:
        parser = DemoParser(str(dem))
        canonical = _build(parser, match_id=match_id, source=source, mode=mode, played_at=played_at)
    validate(canonical.tables())
    return canonical


def _build(
    parser: DemoParser,
    *,
    match_id: str,
    source: str,
    mode: str,
    played_at: dt.date | None,
) -> CanonicalMatch:
    header = parser.parse_header()
    events = set(parser.list_game_events())

    state = (
        frame(parser.parse_ticks(STATE_PROPS))
        .group_by("tick")
        .agg(pl.col(name).first() for name in STATE_PROPS)
        .sort("tick")
        .with_columns(
            pl.col("tick").cast(pl.Int32),
            pl.col("is_freeze_period", "is_warmup_period").fill_null(False),
            pl.col("total_rounds_played", "round_win_status", "round_win_reason")
            .fill_null(0)
            .cast(pl.Int32),
        )
    )
    cuts = cut_rounds(state)
    if not cuts:
        raise CanonicalError("no live round found in the demo")
    timed = state.drop_nulls("game_time")
    tickrate = (timed["tick"][-1] - timed["tick"][0]) / (
        timed["game_time"][-1] - timed["game_time"][0]
    )

    probe_ticks = sorted({c.freeze_end_tick for c in cuts} | {c.end_tick for c in cuts})
    probe = frame(parser.parse_ticks(ROUND_PROPS, ticks=probe_ticks)).with_columns(
        pl.col("tick").cast(pl.Int32), side("team_num").alias("side")
    )
    freeze_ends = pl.DataFrame(
        {
            "tick": pl.Series([c.freeze_end_tick for c in cuts], dtype=pl.Int32),
            "round": pl.Series([c.round for c in cuts], dtype=pl.Int16),
        }
    )
    on_team = probe.join(freeze_ends, on="tick").filter(pl.col("side").is_not_null())
    panel = (
        frame(parser.parse_event("cs_win_panel_match")) if "cs_win_panel_match" in events else None
    )
    ctx = Context(
        parser=parser,
        events=events,
        cuts=cuts,
        teams=assign_teams(on_team.select("round", "steamid", "side")),
        tickrate=tickrate,
        last_event_tick=int(panel["tick"].min()) if panel is not None and panel.height else None,  # type: ignore[arg-type]
        on_team=on_team,
    )

    rounds = build_rounds(ctx, probe)
    tables = {
        "player": build_players(ctx),
        "round": rounds,
        "kill": build_kills(ctx),
        "damage": build_damage(ctx),
        "blind": build_blind(ctx),
        "bomb": build_bomb(ctx, rounds),
        "economy": build_economy(ctx),
    }

    first = cuts[0]
    ct_first = ctx.teams.ct_team[first.round]
    names = probe.filter(pl.col("tick") == first.freeze_end_tick)
    team_names = {
        ct_first if team_side == "CT" else OTHER[ct_first]: name or None
        for team_side, name in zip(
            names["side"].to_list(), names["team_clan_name"].to_list(), strict=True
        )
        if team_side is not None
    }
    last = rounds.row(-1, named=True)
    match = pl.DataFrame(
        {
            "match_id": [match_id],
            "schema_version": [SCHEMA_VERSION],
            "parser": ["demoparser2"],
            "parser_version": [version("demoparser2")],
            "source": [source],
            "mode": [mode],
            "played_at": pl.Series([played_at], dtype=pl.Date),
            "map": [header.get("map_name", "")],
            "game_build": [header.get("patch_version", "")],
            "server_name": [header.get("server_name", "")],
            "tickrate": [tickrate],
            "ticks": [int(state["tick"].max())],  # type: ignore[arg-type]
            "rounds_played": [len(cuts)],
            "score_a": [last["score_a"]],
            "score_b": [last["score_b"]],
            "team_a_name": [team_names.get("A")],
            "team_b_name": [team_names.get("B")],
            "first_round": [first.round],
            "events_available": [sorted(events)],
            "unavailable": pl.Series([ctx.unavailable], dtype=pl.List(pl.String)),
        }
    )
    return CanonicalMatch(
        match=conform(match, "match"),
        **{name: conform(table, name) for name, table in tables.items()},
    )
