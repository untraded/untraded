# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""How much each action moved the round: its swing, credited to players.

An event changes the round's state; the model gives the counter-terrorists' win probability just
before it and just after it, and the difference is the event's swing:

- **a kill**: the victim's side loses a player (their health, armor, equipment and, for a
  counter-terrorist, kit). The swing, seen by the killer's side, is shared among the enemies
  who damaged the victim this round, by damage dealt (the killer at least has the last hit). A
  flash assist takes `FLASH_SHARE` of it first. The victim is debited the same swing, seen by
  their side. A team kill debits the killer instead; a death to the world debits the victim.
  The death of a bot (`kill.victim` null) is not credited.
- **the plant**: the bomb goes down with `BOMB_SECONDS` to go; the planter gets the swing.
- **the defuse**: the counter-terrorists win; the defuser gets the swing.

When an event decides the round (the last enemy dies, the defuse), the probability after it is
the result, 1 or 0. The time passing between events is credited to no one.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import polars as pl

from untraded.winprob.features import BOMB_SECONDS, state_at
from untraded.winprob.model import Model

FLASH_SHARE = 0.1
"""Share of a kill's swing credited to the flash assist, when the kill has one."""

SCHEMA = {
    "round": pl.Int16,
    "tick": pl.Int32,
    "event": pl.String,
    "steamid": pl.UInt64,
    "side": pl.String,
    "swing": pl.Float64,
    "p_ct_before": pl.Float64,
    "p_ct_after": pl.Float64,
}


@dataclass(frozen=True)
class _Credit:
    steamid: int
    side: str
    swing: float


def _after_kill(before: pl.DataFrame, victim: Mapping[str, Any], side: str) -> pl.DataFrame:
    """The state once the victim is gone."""
    s = "ct" if side == "CT" else "t"
    health = float(victim.get("health") or 0) / 100
    armor = float(victim.get("armor") or 0) / 100
    equip = float(victim.get("equip_value") or 0) / 1000
    changes = [
        (pl.col(f"alive_{s}") - 1).clip(0).alias(f"alive_{s}"),
        (pl.col(f"hp_{s}") - health).clip(0).alias(f"hp_{s}"),
        (pl.col(f"armor_{s}") - armor).clip(0).alias(f"armor_{s}"),
        (pl.col(f"equip_{s}") - equip).clip(0).alias(f"equip_{s}"),
    ]
    if side == "CT" and victim.get("has_defuser"):
        changes.append((pl.col("kits") - 1).clip(0).alias("kits"))
    out = before.with_columns(changes)
    return out.with_columns(
        (pl.col("alive_ct") * pl.col("planted")).alias("alive_ct_planted"),
        (pl.col("alive_t") * pl.col("planted")).alias("alive_t_planted"),
    )


def _decided(state: pl.DataFrame) -> float | None:
    """The result when the state leaves no round to play, else None."""
    row = state.row(0, named=True)
    if row["alive_ct"] <= 0:
        return 0.0
    if row["alive_t"] <= 0 and row["planted"] <= 0:
        return 1.0
    return None


def swings(tables: Mapping[str, pl.DataFrame], model: Model) -> pl.DataFrame:
    """Every credit of every kill, plant and defuse of a match (columns `SCHEMA`); `swing` is
    seen by the player's side: positive helped their team, negative hurt it."""
    rows: list[dict[str, object]] = []
    rounds = {r["round"]: r for r in tables["round"].iter_rows(named=True)}
    damage = tables["damage"].filter(~pl.col("is_team_damage"))
    ticks = tables["player_tick"]

    def add(
        round_number: int,
        tick: int,
        event: str,
        before: float,
        after: float,
        credits: list[_Credit],
    ) -> None:
        for c in credits:
            rows.append(
                {
                    "round": round_number,
                    "tick": tick,
                    "event": event,
                    "steamid": c.steamid,
                    "side": c.side,
                    "swing": c.swing,
                    "p_ct_before": before,
                    "p_ct_after": after,
                }
            )

    for kill in tables["kill"].iter_rows(named=True):
        rnd = rounds.get(kill["round"])
        if rnd is None or rnd["freeze_end_tick"] is None or kill["tick"] < rnd["freeze_end_tick"]:
            continue
        if kill["victim"] is None:  # a bot: no state of its own to take away
            continue
        try:
            before = state_at(tables, kill["round"], kill["tick"])
        except ValueError:
            continue
        victim_side = str(kill["victim_side"])
        victim = (
            ticks.filter(
                pl.col("round") == kill["round"],
                pl.col("steamid") == kill["victim"],
                pl.col("tick") < kill["tick"],
            )
            .sort("tick")
            .tail(1)
            .to_dicts()
        )
        if not victim or not victim[0]["is_alive"]:
            continue
        after_state = _after_kill(before, victim[0], victim_side)
        p_before = float(model.predict(before)[0])
        decided = _decided(after_state)
        p_after = decided if decided is not None else float(model.predict(after_state)[0])
        # The swing seen by the victim's enemies (positive when the victim's side lost ground).
        gain = (p_after - p_before) if victim_side == "T" else (p_before - p_after)
        enemy = "CT" if victim_side == "T" else "T"
        credits: list[_Credit] = []
        if kill["is_team_kill"] and kill["attacker"] is not None:
            credits.append(_Credit(kill["attacker"], victim_side, -gain))
        else:
            credits.append(_Credit(kill["victim"], victim_side, -gain))
            if kill["attacker"] is not None and not kill["is_suicide"]:
                share = gain
                if kill["flash_assist"] and kill["assister"] is not None:
                    credits.append(_Credit(kill["assister"], enemy, gain * FLASH_SHARE))
                    share = gain * (1 - FLASH_SHARE)
                dealt = (
                    damage.filter(
                        pl.col("round") == kill["round"],
                        pl.col("victim") == kill["victim"],
                        pl.col("tick") <= kill["tick"],
                        pl.col("attacker").is_not_null(),
                    )
                    .group_by("attacker")
                    .agg(pl.col("damage").sum())
                )
                by_player = {a: float(d) for a, d in dealt.iter_rows()}
                by_player.setdefault(kill["attacker"], 0.0)
                total = sum(by_player.values())
                for player, amount in by_player.items():
                    part = (
                        amount / total
                        if total > 0
                        else (1.0 if player == kill["attacker"] else 0.0)
                    )
                    if part > 0:
                        credits.append(_Credit(player, enemy, share * part))
        add(kill["round"], kill["tick"], "kill", p_before, p_after, credits)

    for rnd in rounds.values():
        number = rnd["round"]
        if rnd["bomb_planted_tick"] is not None and rnd["bomb_planter"] is not None:
            planted_before: pl.DataFrame | None
            try:
                planted_before = state_at(tables, number, rnd["bomb_planted_tick"])
            except ValueError:
                planted_before = None
            if planted_before is not None and planted_before["alive_ct"][0] > 0:
                after = planted_before.with_columns(
                    pl.lit(1.0).alias("planted"),
                    pl.lit(0.0).alias("time_left"),
                    pl.lit(BOMB_SECONDS / 10).alias("time_left_planted"),
                    pl.col("alive_ct").alias("alive_ct_planted"),
                    pl.col("alive_t").alias("alive_t_planted"),
                )
                p0, p1 = float(model.predict(planted_before)[0]), float(model.predict(after)[0])
                add(
                    number,
                    rnd["bomb_planted_tick"],
                    "plant",
                    p0,
                    p1,
                    [_Credit(rnd["bomb_planter"], "T", p0 - p1)],
                )
        if rnd["bomb_defused_tick"] is not None and rnd["bomb_defuser"] is not None:
            try:
                before = state_at(tables, number, rnd["bomb_defused_tick"])
            except ValueError:
                continue
            p0 = float(model.predict(before)[0])
            add(
                number,
                rnd["bomb_defused_tick"],
                "defuse",
                p0,
                1.0,
                [_Credit(rnd["bomb_defuser"], "CT", 1.0 - p0)],
            )

    return pl.DataFrame(rows, schema=SCHEMA).sort("round", "tick")
