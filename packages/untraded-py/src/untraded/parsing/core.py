# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The `round`, `kill` and `player` tables."""

from __future__ import annotations

import polars as pl

from untraded.parsing._context import Context, frame, side, steamid
from untraded.parsing.schema import KILL
from untraded.parsing.teams import OTHER

REGULATION_ROUNDS = 24
"""MR12: rounds after the 24th are overtime (Premier, FACEIT, ESEA and tournaments)."""

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


def hitgroup(column: str) -> pl.Expr:
    return pl.col(column).cast(pl.String).replace_strict(HITGROUPS, default=None)


def build_rounds(ctx: Context, probe: pl.DataFrame) -> pl.DataFrame:
    """`probe`: `team_rounds_total` and `side` of each player at every round end tick."""
    scores: dict[tuple[int, str], int] = {}
    for tick, team_side, total in (
        probe.select("tick", "side", "team_rounds_total").drop_nulls().iter_rows()
    ):
        scores[(tick, team_side)] = int(total)

    rows = []
    won = {"A": 0, "B": 0}
    for cut in ctx.cuts:
        ct = ctx.teams.ct_team.get(cut.round, "A")
        winner = ct if cut.winner_side == "CT" else OTHER[ct] if cut.winner_side == "T" else None
        if winner is not None:
            won[winner] += 1
        by_team = {ct: scores.get((cut.end_tick, "CT")), OTHER[ct]: scores.get((cut.end_tick, "T"))}
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
    rounds = pl.DataFrame(rows).with_columns(pl.col("round").cast(pl.Int16))

    def first_per_round(name: str, **props: list[str]) -> pl.DataFrame:
        found = ctx.in_rounds(ctx.event(name, **props))
        return found.group_by("round").agg(pl.all().sort_by("tick").first())

    # The official end comes after the round end (often at the next freeze start, and duplicated):
    # it belongs to the last round that ended before it.
    ends = pl.DataFrame(
        {
            "end_tick": pl.Series([c.end_tick for c in ctx.cuts], dtype=pl.Int32),
            "round": pl.Series([c.round for c in ctx.cuts], dtype=pl.Int16),
        }
    )
    official = (
        ctx.event("round_officially_ended")
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

    planted = (
        planted.select(
            "round",
            pl.col("tick").alias("bomb_planted_tick"),
            bomb_site("user_last_place_name").alias("bomb_site"),
            steamid("user_steamid").alias("bomb_planter"),
        )
        if planted.height
        else _by_round(bomb_planted_tick=pl.Int32, bomb_site=pl.String, bomb_planter=pl.UInt64)
    )
    defused = (
        defused.select(
            "round",
            pl.col("tick").alias("bomb_defused_tick"),
            steamid("user_steamid").alias("bomb_defuser"),
        )
        if defused.height
        else _by_round(bomb_defused_tick=pl.Int32, bomb_defuser=pl.UInt64)
    )
    exploded = (
        exploded.select("round", pl.col("tick").alias("bomb_exploded_tick"))
        if exploded.height
        else _by_round(bomb_exploded_tick=pl.Int32)
    )
    if not official.height:
        official = _by_round(official_end_tick=pl.Int32)
    for part in (official, planted, defused, exploded):
        rounds = rounds.join(part, on="round", how="left")
    return rounds


def bomb_site(column: str) -> pl.Expr:
    """The bomb events carry a site entity id, not A/B: the planter's place name does."""
    return pl.col(column).str.extract(r"Bombsite([AB])$")


def _by_round(**columns: type[pl.DataType] | pl.DataType) -> pl.DataFrame:
    return pl.DataFrame(schema={"round": pl.Int16, **columns})


def build_kills(ctx: Context) -> pl.DataFrame:
    if "player_death" not in ctx.events:
        ctx.unavailable.append("kill: no player_death event")
        return pl.DataFrame(schema=KILL)
    raw = ctx.in_rounds(ctx.event("player_death", player=KILL_PROPS))
    kills = raw.select(
        "tick",
        "round",
        steamid("attacker_steamid").alias("attacker"),
        steamid("user_steamid").alias("victim"),
        steamid("assister_steamid").alias("assister"),
        pl.col("assistedflash").fill_null(False).alias("flash_assist"),
        pl.col("weapon").fill_null(""),
        pl.col("headshot").fill_null(False),
        (pl.col("penetrated").fill_null(0) > 0).alias("wallbang"),
        pl.col("noscope").fill_null(False),
        pl.col("thrusmoke").fill_null(False).alias("through_smoke"),
        pl.col("attackerblind").fill_null(False).alias("attacker_blind"),
        pl.col("attackerinair").fill_null(False).alias("attacker_in_air"),
        hitgroup("hitgroup").alias("hitgroup"),
        pl.col("distance"),
        side("attacker_team_num").alias("attacker_side"),
        side("user_team_num").alias("victim_side"),
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


def build_players(ctx: Context) -> pl.DataFrame:
    info = (
        frame(ctx.parser.parse_player_info())
        .select(pl.col("steamid").cast(pl.UInt64), pl.col("name").cast(pl.String))
        .unique("steamid", keep="first")
    )
    first_seen = (
        ctx.on_team.sort("round")
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
            "steamid": pl.Series(list(ctx.teams.player_team), dtype=pl.UInt64),
            "team": list(ctx.teams.player_team.values()),
        }
    )
    return (
        team.join(first_seen, on="steamid", how="left")
        .join(info, on="steamid", how="left")
        .with_columns(pl.col("name").fill_null(""))
        .sort("team", "steamid")
    )
