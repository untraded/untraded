# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Spike S0.4: check that rounds can be cut reliably in every demo of a directory.

Run `just spike-parsing <demo_dir>` first for timings and props; this adds what S0.2 does not check:
  - round_freeze_end count vs. rounds played and final score (gamerules and team entities);
  - round index at each freeze end (a demo that starts mid round 1 has no freeze end for it);
  - freeze ends during warmup, or before any player is in game (pre-match);
  - whether flash_duration can stand in for the missing player_blind event.

Usage: python check_rounds.py <demo_dir>   (.dem files only)
"""

from __future__ import annotations

import sys
from pathlib import Path

import polars as pl
from demoparser2 import DemoParser


def check(path: Path) -> str:
    parser = DemoParser(str(path))
    header = parser.parse_header()
    freeze_ends = [int(t) for t in parser.parse_event("round_freeze_end")["tick"]]

    last = pl.from_pandas(parser.parse_ticks(["total_rounds_played", "team_rounds_total"]))
    last = last.filter(pl.col("tick") == pl.col("tick").max())
    played = int(last["total_rounds_played"].max())
    score = sorted(int(s) for s in last["team_rounds_total"].unique().to_list())

    at_freeze = pl.from_pandas(
        parser.parse_ticks(["total_rounds_played", "is_warmup_period"], ticks=freeze_ends)
    )
    per_round = at_freeze.group_by("tick").agg(
        pl.col("total_rounds_played").max(), pl.col("is_warmup_period").any()
    )
    warmup = int(per_round["is_warmup_period"].sum())
    # parse_ticks returns no row for a tick where no player exists yet.
    pre_match = len(set(freeze_ends)) - per_round.height
    live = per_round.filter(~pl.col("is_warmup_period"))
    first_round = int(live["total_rounds_played"].min()) + 1 if live.height else None

    # flash_duration is set on every blinded player right after the flashbang detonates.
    flashes = [int(t) + 2 for t in parser.parse_event("flashbang_detonate")["tick"]]
    flashed = pl.from_pandas(parser.parse_ticks(["flash_duration"], ticks=flashes))
    blinded = flashed.filter(pl.col("flash_duration") > 0).height

    ok = live.height == played == sum(score) and first_round == 1
    return (
        f"{path.name} | {header.get('map_name')} | patch {header.get('patch_version')} | "
        f"freeze_end {len(freeze_ends)} (warmup {warmup}, pre-match {pre_match}) | "
        f"played {played} | score {score} | "
        f"first live round {first_round} | {blinded} players blinded by {len(flashes)} flashes | "
        f"{'OK' if ok else 'CHECK'}"
    )


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    demos = sorted(Path(sys.argv[1]).expanduser().glob("*.dem"))
    if not demos:
        sys.exit(f"no .dem found in {sys.argv[1]}")
    for demo in demos:
        print(check(demo), flush=True)


if __name__ == "__main__":
    main()
