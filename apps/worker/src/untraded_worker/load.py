# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Writes an analysed match to the SQL tables of ADR 0011, and who may see it (`workspace_match`).

Loading is idempotent: the match's rows are deleted first, so a reparse (new parser, new metric
versions) replaces them. Steam ids are UInt64 in Polars and bigint in PostgreSQL: they all fit
(76561197960265728 and up, below 2^63).
"""

from __future__ import annotations

import json
import math
import uuid
from collections.abc import Iterable, Sequence
from typing import Any

import polars as pl
import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from untraded.metrics import REGISTRY
from untraded_worker.analysis import Analysis

DEFAULT_PARAMS = "default"
"""`params_hash` of the values computed with every parameter at its default."""

MATCH_TABLES = (
    "kill", "damage", "blind", "grenade", "economy", "round_player", "round",
    "metric_value", "metric_table_value", "match_player",
)  # fmt: skip
"""Tables holding one match's rows, deleted before a (re)load."""


def _seq() -> pl.Expr:
    """Order of the rows on the same tick, part of the primary key."""
    return pl.int_range(pl.len(), dtype=pl.Int16).over("tick").alias("seq")


def sql_frames(analysis: Analysis) -> dict[str, pl.DataFrame]:
    """The match's rows by SQL table, with the SQL column names (`match_id` excepted)."""
    t = analysis.tables
    steam = pl.col("steamid").alias("steam_id")
    xyz = ("x", "y", "z")
    return {
        "match_player": t["player"].select(steam, "team", "name", "rounds_on_team", "rank"),
        "round": t["round"].select(
            "round",
            "start_tick",
            "freeze_end_tick",
            "end_tick",
            "official_end_tick",
            "winner_side",
            "winner_team",
            "reason",
            "ct_team",
            "score_a",
            "score_b",
            "is_overtime",
            "bomb_planted_tick",
            "bomb_site",
            "bomb_planter",
            "bomb_defused_tick",
            "bomb_exploded_tick",
        ),
        "kill": t["kill"].select(
            "tick",
            "round",
            _seq(),
            "attacker",
            "victim",
            "victim_bot",
            "assister",
            "flash_assist",
            "weapon",
            "headshot",
            "wallbang",
            "through_smoke",
            "attacker_blind",
            "attacker_side",
            "victim_side",
            "is_team_kill",
            "is_suicide",
            *(f"attacker_{a}" for a in xyz),
            *(f"victim_{a}" for a in xyz),
            "attacker_place",
            "victim_place",
        ),
        "damage": t["damage"].select(
            "tick",
            _seq(),
            "round",
            "attacker",
            "victim",
            "weapon",
            "hitgroup",
            "damage",
            "dmg_armor",
            "is_team_damage",
            "grenade_id",
        ),
        "blind": t["blind"].select(
            "tick",
            _seq(),
            "round",
            "victim",
            "flasher",
            "grenade_id",
            "duration",
            "is_teammate",
            "is_self",
        ),
        "grenade": t["grenade"].select(
            "grenade_id",
            "round",
            "thrower",
            "side",
            "type",
            "throw_tick",
            *(f"throw_{a}" for a in xyz),
            "detonate_tick",
            *(f"detonate_{a}" for a in xyz),
            "end_tick",
        ),
        "economy": t["economy"].select(
            "round",
            steam,
            "side",
            "money_start",
            "spent",
            "equip_value",
            "round_start_equip_value",
            "armor",
            "has_helmet",
            "has_defuser",
        ),
        "round_player": t["round_player"]
        .join(t["team_round"].select("round", "team", "buy_type"), on=["round", "team"], how="left")
        .select(
            "round",
            steam,
            "team",
            "side",
            "kills",
            "deaths",
            "assists",
            "flash_assists",
            "damage",
            "survived",
            "death_tick",
            "death_trade_delay_s",
            "opening_kill",
            "opening_death",
            "setup_place",
            "team_won",
            "buy_type",
        ),
    }


def _finite(value: Any) -> Any:
    """JSON and `double precision` without NaN or infinities: they become null."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: _finite(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_finite(v) for v in value]
    return value


def _copy(
    conn: psycopg.Connection[Any], table: str, columns: Sequence[str], rows: Iterable[Sequence[Any]]
) -> None:
    statement = sql.SQL("COPY {} ({}) FROM STDIN").format(
        sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, columns))
    )
    with conn.cursor().copy(statement) as copy:
        for row in rows:
            copy.write_row(row)


def _copy_frame(
    conn: psycopg.Connection[Any], table: str, match_id: uuid.UUID, frame: pl.DataFrame
) -> None:
    rows = ((match_id, *(_finite(v) for v in row)) for row in frame.iter_rows())
    _copy(conn, table, ["match_id", *frame.columns], rows)


def register_metrics(conn: psycopg.Connection[Any]) -> None:
    """Records the deployed registry: every (metric, version) the worker computes, and makes it
    the version screens read (`metric_current`).

    Until matches are recomputed after a version change, older matches only hold the previous
    version and show no value for that metric: the recompute job comes later.
    """
    for m in REGISTRY.values():
        conn.execute(
            "INSERT INTO metric_definition (metric_id, version, name, unit, kind, params, doc, "
            "better, cases, signed) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            # Metadata only (the formula is the version's): it may be corrected in place.
            "ON CONFLICT (metric_id, version) DO UPDATE SET better = EXCLUDED.better, "
            "cases = EXCLUDED.cases, signed = EXCLUDED.signed",
            (
                m.id,
                m.version,
                m.name,
                m.unit,
                m.kind,
                Jsonb(dict(m.params)),
                m.doc,
                m.better,
                list(m.cases),
                m.signed,
            ),
        )
        conn.execute(
            "INSERT INTO metric_current (metric_id, version) VALUES (%s, %s) "
            "ON CONFLICT (metric_id) DO UPDATE SET version = EXCLUDED.version",
            (m.id, m.version),
        )


def load_match(conn: psycopg.Connection[Any], match_id: uuid.UUID, analysis: Analysis) -> None:
    """Replaces the match's rows with `analysis`, and fills the match's own columns."""
    for table in MATCH_TABLES:
        conn.execute(
            sql.SQL("DELETE FROM {} WHERE match_id = %s").format(sql.Identifier(table)),
            (match_id,),
        )
    frames = sql_frames(analysis)
    players = frames["match_player"].select("steam_id", "name").iter_rows()
    conn.cursor().executemany(
        "INSERT INTO player (steam_id, last_name) VALUES (%s, %s) "
        "ON CONFLICT (steam_id) DO UPDATE SET last_name = EXCLUDED.last_name",
        list(players),
    )
    for table, frame in frames.items():
        _copy_frame(conn, table, match_id, frame)

    register_metrics(conn)
    values = analysis.values.select(
        "steamid", "scope", "metric", "version", pl.lit(DEFAULT_PARAMS), "value"
    )
    _copy(
        conn,
        "metric_value",
        ["match_id", "steam_id", "scope", "metric_id", "version", "params_hash", "value"],
        ((match_id, *(_finite(v) for v in row)) for row in values.iter_rows()),
    )
    _copy(
        conn,
        "metric_table_value",
        ["match_id", "steam_id", "metric_id", "version", "params_hash", "rows"],
        _table_rows(match_id, analysis),
    )

    info = analysis.match
    conn.execute(
        """
        UPDATE match SET sha256 = %(sha256)s, map = %(map)s, game_build = %(game_build)s,
               tickrate = %(tickrate)s, rounds_played = %(rounds_played)s,
               first_round = %(first_round)s, score_a = %(score_a)s, score_b = %(score_b)s,
               team_a_name = %(team_a_name)s, team_b_name = %(team_b_name)s,
               schema_version = %(schema_version)s, parser_version = %(parser_version)s,
               unavailable = %(unavailable)s,
               -- The collector knows the end from the Game Coordinator; otherwise, the demo's
               -- length after the start.
               ended_at = coalesce(ended_at, played_at + %(duration)s * interval '1 second')
        WHERE id = %(id)s
        """,
        {
            **{
                k: info[k]
                for k in (
                    "map",
                    "game_build",
                    "tickrate",
                    "rounds_played",
                    "first_round",
                    "score_a",
                    "score_b",
                    "team_a_name",
                    "team_b_name",
                    "schema_version",
                    "unavailable",
                )
            },
            "sha256": info["match_id"],
            "duration": float(analysis.tables["match"]["ticks"][0])
            / float(analysis.tables["match"]["tickrate"][0]),
            "parser_version": f"{info['parser']} {info['parser_version']}",
            "id": match_id,
        },
    )


def _table_rows(match_id: uuid.UUID, analysis: Analysis) -> Iterable[tuple[Any, ...]]:
    for metric_id, frame in analysis.table_values.items():
        version = REGISTRY[metric_id].version
        for (steamid,), rows in frame.group_by("steamid", maintain_order=True):
            records = _finite(rows.drop("steamid").to_dicts())
            yield (
                match_id, steamid, metric_id, version, DEFAULT_PARAMS,
                Jsonb(records, dumps=lambda o: json.dumps(o, default=str)),
            )  # fmt: skip


def refresh_access(conn: psycopg.Connection[Any], match_id: uuid.UUID) -> int:
    """Recomputes which workspaces see the match (see `workspace_match` in ADR 0011); returns
    how many do. When several reasons apply, the first of own, roster, shared is kept."""
    conn.execute("DELETE FROM workspace_match WHERE match_id = %s", (match_id,))
    params = {"match": match_id}
    conn.execute(
        """
        INSERT INTO workspace_match (workspace_id, match_id, reason)
        SELECT w.id, %(match)s, 'own'::access_reason
        FROM workspace w
        JOIN app_user u ON u.id = w.created_by AND u.deleted_at IS NULL
        JOIN match_player mp ON mp.steam_id = u.steam_id AND mp.match_id = %(match)s
        WHERE w.kind = 'personal'
        ON CONFLICT DO NOTHING
        """,
        params,
    )
    conn.execute(
        """
        INSERT INTO workspace_match (workspace_id, match_id, reason)
        SELECT DISTINCT r.workspace_id, %(match)s, 'roster'::access_reason
        FROM roster r
        JOIN roster_member rm ON rm.roster_id = r.id
        JOIN match_player mp ON mp.steam_id = rm.steam_id AND mp.match_id = %(match)s
        JOIN match m ON m.id = %(match)s
        WHERE r.active
          AND rm.valid_from <= coalesce(m.played_at::date, current_date)
          AND (rm.valid_to IS NULL OR rm.valid_to >= coalesce(m.played_at::date, current_date))
        GROUP BY r.id, r.workspace_id
        HAVING count(DISTINCT rm.steam_id) >= 3
        ON CONFLICT DO NOTHING
        """,
        params,
    )
    conn.execute(
        """
        INSERT INTO workspace_match (workspace_id, match_id, reason)
        SELECT DISTINCT wp.workspace_id, %(match)s, 'shared'::access_reason
        FROM workspace_player wp
        JOIN workspace w ON w.id = wp.workspace_id AND w.kind = 'team'
        JOIN match_player mp ON mp.steam_id = wp.steam_id AND mp.match_id = %(match)s
        WHERE wp.share_solo
        ON CONFLICT DO NOTHING
        """,
        params,
    )
    row = conn.execute(
        "SELECT count(*) FROM workspace_match WHERE match_id = %s", (match_id,)
    ).fetchone()
    return int(row[0]) if row else 0
