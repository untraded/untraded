# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""demoparser2 -> canonical tables (ADR 0002, 0008; docs/canonical-tables.md).

Builds `match`, `player`, `round` and `kill`. pandas frames from demoparser2 are converted to
Polars at once and never leave this module.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path

import polars as pl
from demoparser2 import DemoParser

from untraded.demofile import digest, plain_demo
from untraded.parsing.rounds import RoundCut, cut_rounds, event_rounds
from untraded.parsing.schema import KILL, MODES, SCHEMA_VERSION, CanonicalError, conform
from untraded.parsing.teams import OTHER, Teams, assign_teams
from untraded.parsing.validate import validate

REGULATION_ROUNDS = 24
"""MR12: rounds after the 24th are overtime (Premier, FACEIT, ESEA and tournaments)."""

STATE_PROPS = [
    "is_freeze_period",
    "is_warmup_period",
    "total_rounds_played",
    "round_win_status",
    "round_win_reason",
    "game_time",
]
ROUND_PROPS = ["team_num", "team_rounds_total", "team_clan_name", "rank", "comp_wins"]
KILL_PROPS = [
    "X",
    "Y",
    "Z",
    "last_place_name",
    "current_equip_value",
    "inventory",
    "flash_duration",
    "team_num",
]
SIDES = {2: "T", 3: "CT"}
# CS2 hit groups (engine HitGroup_t), as named by demoparser2
HITGROUPS = {
    "generic": 0,
    "head": 1,
    "chest": 2,
    "stomach": 3,
    "left_arm": 4,
    "right_arm": 5,
    "left_leg": 6,
    "right_leg": 7,
    "neck": 8,
    "gear": 10,
}


class UnsupportedModeError(ValueError):
    """The game mode is not analysed (e.g. Wingman, Competitive): filter it before parsing."""


@dataclass(frozen=True)
class CanonicalMatch:
    match: pl.DataFrame
    player: pl.DataFrame
    round: pl.DataFrame
    kill: pl.DataFrame

    @property
    def match_id(self) -> str:
        return str(self.match["match_id"][0])

    def tables(self) -> dict[str, pl.DataFrame]:
        return {"match": self.match, "player": self.player, "round": self.round, "kill": self.kill}

    def write(self, root: Path) -> Path:
        """Writes `root/matches/{match_id}/{table}.parquet` (zstd); returns the match directory."""
        target = root / "matches" / self.match_id
        target.mkdir(parents=True, exist_ok=True)
        for name, frame in self.tables().items():
            frame.write_parquet(target / f"{name}.parquet", compression="zstd")
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


def _frame(data: object) -> pl.DataFrame:
    return pl.from_pandas(data)


def _steamid(column: str) -> pl.Expr:
    """demoparser2 gives event steamids as strings; `0` or empty means no player."""
    text = pl.col(column).cast(pl.String)
    return (
        pl.when(text.is_in(["", "0"]) | text.is_null())
        .then(None)
        .otherwise(text)
        .cast(pl.UInt64, strict=True)
    )


def _side(column: str) -> pl.Expr:
    return pl.col(column).cast(pl.Int64, strict=False).replace_strict(SIDES, default=None)


def _event(parser: DemoParser, events: set[str], name: str, **props: list[str]) -> pl.DataFrame:
    if name not in events:
        return pl.DataFrame({"tick": pl.Series([], dtype=pl.Int32)})
    return _frame(parser.parse_event(name, **props)).with_columns(pl.col("tick").cast(pl.Int32))


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
    unavailable: list[str] = []

    state = (
        _frame(parser.parse_ticks(STATE_PROPS))
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
    probe = _frame(parser.parse_ticks(ROUND_PROPS, ticks=probe_ticks)).with_columns(
        pl.col("tick").cast(pl.Int32), _side("team_num").alias("side")
    )
    freeze_ends = pl.DataFrame(
        {
            "tick": pl.Series([c.freeze_end_tick for c in cuts], dtype=pl.Int32),
            "round": pl.Series([c.round for c in cuts], dtype=pl.Int16),
        }
    )
    on_team = probe.join(freeze_ends, on="tick").filter(pl.col("side").is_not_null())
    teams = assign_teams(on_team.select("round", "steamid", "side"))

    panel = _event(parser, events, "cs_win_panel_match")
    last_event_tick = int(panel["tick"].min()) if panel.height else None  # type: ignore[arg-type]

    rounds = _rounds(parser, events, cuts, probe, teams, last_event_tick)
    kills = _kills(parser, events, cuts, last_event_tick, unavailable)
    players = _players(parser, on_team, teams)

    first = cuts[0]
    names = probe.filter(pl.col("tick") == first.freeze_end_tick)
    team_names = {
        teams.ct_team[first.round] if side == "CT" else OTHER[teams.ct_team[first.round]]: name
        or None
        for side, name in zip(
            names["side"].to_list(), names["team_clan_name"].to_list(), strict=True
        )
        if side is not None
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
            "unavailable": pl.Series([unavailable], dtype=pl.List(pl.String)),
        }
    )
    return CanonicalMatch(
        match=conform(match, "match"),
        player=conform(players, "player"),
        round=conform(rounds, "round"),
        kill=conform(kills, "kill"),
    )


def _rounds(
    parser: DemoParser,
    events: set[str],
    cuts: list[RoundCut],
    probe: pl.DataFrame,
    teams: Teams,
    last_event_tick: int | None,
) -> pl.DataFrame:
    scores: dict[tuple[int, str], int] = {}
    for tick, side, total in (
        probe.select("tick", "side", "team_rounds_total").drop_nulls().iter_rows()
    ):
        scores[(tick, side)] = int(total)

    rows = []
    won = {"A": 0, "B": 0}
    for cut in cuts:
        ct = teams.ct_team.get(cut.round, "A")
        winner = ct if cut.winner_side == "CT" else OTHER[ct] if cut.winner_side == "T" else None
        if winner is not None:
            won[winner] += 1
        ct_score = scores.get((cut.end_tick, "CT"))
        t_score = scores.get((cut.end_tick, "T"))
        by_team = {ct: ct_score, OTHER[ct]: t_score}
        rows.append(
            {
                "round": cut.round,
                "start_tick": cut.start_tick,
                "freeze_end_tick": cut.freeze_end_tick,
                "end_tick": cut.end_tick,
                "winner_side": cut.winner_side or None,
                "winner_team": winner,
                "reason": cut.reason,
                "ct_team": ct,
                "t_team": OTHER[ct],
                # team_rounds_total, or the running count when no player of a team is left
                "score_a": by_team["A"] if by_team["A"] is not None else won["A"],
                "score_b": by_team["B"] if by_team["B"] is not None else won["B"],
                "is_overtime": cut.round > REGULATION_ROUNDS,
            }
        )
    frame = pl.DataFrame(rows).with_columns(pl.col("round").cast(pl.Int16))

    def first_per_round(name: str, **props: list[str]) -> pl.DataFrame:
        found = event_rounds(
            _event(parser, events, name, **props), cuts, last_event_tick=last_event_tick
        )
        return found.group_by("round").agg(pl.all().sort_by("tick").first())

    # The official end comes after the round end (often at the next freeze start, and duplicated):
    # it belongs to the last round that ended before it.
    ends = pl.DataFrame(
        {
            "end_tick": pl.Series([c.end_tick for c in cuts], dtype=pl.Int32),
            "round": pl.Series([c.round for c in cuts], dtype=pl.Int16),
        }
    )
    official = (
        _event(parser, events, "round_officially_ended")
        .select("tick")
        .sort("tick")
        .join_asof(ends, left_on="tick", right_on="end_tick", strategy="backward")
        .drop_nulls("round")
        .group_by("round")
        .agg(pl.col("tick").min().alias("official_end_tick"))
    )
    planted = first_per_round("bomb_planted", player=["last_place_name"])
    defused = first_per_round("bomb_defused")
    exploded = first_per_round("bomb_exploded")

    if planted.height:
        planted = planted.select(
            "round",
            pl.col("tick").alias("bomb_planted_tick"),
            pl.col("user_last_place_name").str.extract(r"Bombsite([AB])$").alias("bomb_site"),
            _steamid("user_steamid").alias("bomb_planter"),
        )
    else:
        planted = _empty_by_round(
            bomb_planted_tick=pl.Int32, bomb_site=pl.String, bomb_planter=pl.UInt64
        )
    if defused.height:
        defused = defused.select(
            "round",
            pl.col("tick").alias("bomb_defused_tick"),
            _steamid("user_steamid").alias("bomb_defuser"),
        )
    else:
        defused = _empty_by_round(bomb_defused_tick=pl.Int32, bomb_defuser=pl.UInt64)
    exploded = (
        exploded.select("round", pl.col("tick").alias("bomb_exploded_tick"))
        if exploded.height
        else _empty_by_round(bomb_exploded_tick=pl.Int32)
    )
    if not official.height:
        official = _empty_by_round(official_end_tick=pl.Int32)
    for part in (official, planted, defused, exploded):
        frame = frame.join(part, on="round", how="left")
    return frame


def _empty_by_round(**columns: type[pl.DataType] | pl.DataType) -> pl.DataFrame:
    return pl.DataFrame(schema={"round": pl.Int16, **columns})


def _kills(
    parser: DemoParser,
    events: set[str],
    cuts: list[RoundCut],
    last_event_tick: int | None,
    unavailable: list[str],
) -> pl.DataFrame:
    if "player_death" not in events:
        unavailable.append("kill: no player_death event")
        return pl.DataFrame(schema=KILL)
    raw = event_rounds(
        _event(parser, events, "player_death", player=KILL_PROPS),
        cuts,
        last_event_tick=last_event_tick,
    )
    kills = raw.select(
        "tick",
        "round",
        _steamid("attacker_steamid").alias("attacker"),
        _steamid("user_steamid").alias("victim"),
        _steamid("assister_steamid").alias("assister"),
        pl.col("assistedflash").fill_null(False).alias("flash_assist"),
        pl.col("weapon").fill_null(""),
        pl.col("headshot").fill_null(False),
        (pl.col("penetrated").fill_null(0) > 0).alias("wallbang"),
        pl.col("noscope").fill_null(False),
        pl.col("thrusmoke").fill_null(False).alias("through_smoke"),
        pl.col("attackerblind").fill_null(False).alias("attacker_blind"),
        pl.col("attackerinair").fill_null(False).alias("attacker_in_air"),
        pl.col("hitgroup")
        .cast(pl.String)
        .replace_strict(HITGROUPS, default=None)
        .alias("hitgroup"),
        pl.col("distance"),
        _side("attacker_team_num").alias("attacker_side"),
        _side("user_team_num").alias("victim_side"),
        pl.col("attacker_X").alias("attacker_x"),
        pl.col("attacker_Y").alias("attacker_y"),
        pl.col("attacker_Z").alias("attacker_z"),
        pl.col("user_X").alias("victim_x"),
        pl.col("user_Y").alias("victim_y"),
        pl.col("user_Z").alias("victim_z"),
        pl.col("attacker_last_place_name").alias("attacker_place"),
        pl.col("user_last_place_name").alias("victim_place"),
        pl.col("attacker_current_equip_value").alias("attacker_equip_value"),
        pl.col("user_current_equip_value").alias("victim_equip_value"),
        pl.col("user_inventory").alias("victim_inventory"),
        pl.col("user_flash_duration").alias("victim_flash_duration"),
    )
    return kills.with_columns(
        (pl.col("attacker") == pl.col("victim")).fill_null(False).alias("is_suicide"),
        (
            (pl.col("attacker") != pl.col("victim"))
            & (pl.col("attacker_side") == pl.col("victim_side"))
        )
        .fill_null(False)
        .alias("is_team_kill"),
    )


def _players(parser: DemoParser, on_team: pl.DataFrame, teams: Teams) -> pl.DataFrame:
    info = (
        _frame(parser.parse_player_info())
        .select(pl.col("steamid").cast(pl.UInt64), pl.col("name").cast(pl.String))
        .unique("steamid", keep="first")
    )
    first_seen = (
        on_team.sort("round")
        .group_by("steamid")
        .agg(
            pl.col("rank").first().cast(pl.Int32),
            pl.col("comp_wins").first().cast(pl.Int32),
            pl.len().cast(pl.Int16).alias("rounds_on_team"),
        )
        .with_columns(pl.col("steamid").cast(pl.UInt64))
    )
    team = pl.DataFrame(
        {
            "steamid": pl.Series(list(teams.player_team), dtype=pl.UInt64),
            "team": list(teams.player_team.values()),
        }
    )
    return (
        team.join(first_seen, on="steamid", how="left")
        .join(info, on="steamid", how="left")
        .with_columns(pl.col("name").fill_null(""))
        .sort("team", "steamid")
    )
