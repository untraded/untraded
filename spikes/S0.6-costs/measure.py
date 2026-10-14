# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Spike S0.6: storage and CPU cost per match, for every demo in one or more directories.

For each demo (.dem, .dem.bz2, .dem.zst, .dem.gz), in a fresh process:
  - decompression of the source file (CPU seconds);
  - re-compression of the .dem with zstd at levels 1, 3 and 9 (size, CPU seconds);
  - what the worker would do: parse the key events and the props at 16 Hz, write them as
    Parquet (zstd), with CPU seconds and wall time.

CPU seconds are process CPU time (user + system, all threads): what a shared server bills,
unlike wall time on a many-core machine. Writes out/costs.json next to this script.

Usage: python measure.py <demo_dir> [<demo_dir> ...]
"""

from __future__ import annotations

import bz2
import gzip
import json
import shutil
import statistics
import sys
import tempfile
import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path
from typing import Any

import polars as pl
from compression import zstd
from demoparser2 import DemoParser

OUT_DIR = Path(__file__).parent / "out"
DEMO_SUFFIXES = (".dem", ".dem.bz2", ".dem.zst", ".dem.gz")
ZSTD_LEVELS = (1, 3, 9)  # 19 reaches 0.6 but costs ~170 CPU s per demo
SAMPLE_EVERY_TICKS = 4  # 64 tick / 4 = 16 Hz

KEY_EVENTS = [
    "player_death", "player_hurt", "weapon_fire", "player_blind", "round_freeze_end",
    "round_officially_ended", "bomb_planted", "bomb_defused", "bomb_exploded",
    "flashbang_detonate", "hegrenade_detonate", "smokegrenade_detonate", "inferno_startburn",
]  # fmt: skip

# Props the metrics engine plans to store per player at 16 Hz (S0.2 bench set + usercmd).
TICK_PROPS = [
    "X", "Y", "Z", "pitch", "yaw", "velocity_X", "velocity_Y", "health", "armor_value",
    "is_alive", "team_num", "active_weapon_name", "balance", "current_equip_value",
    "round_start_equip_value", "last_place_name", "flash_duration", "ducking", "is_scoped",
    "is_airborne", "spotted", "inventory", "usercmd_viewangle_x", "usercmd_viewangle_y",
]  # fmt: skip


def measured(fn: Callable[[], Any]) -> tuple[Any, float, float]:
    """Runs fn and returns (result, CPU seconds of this process, wall seconds)."""
    cpu, wall = time.process_time(), time.perf_counter()
    result = fn()
    return result, time.process_time() - cpu, time.perf_counter() - wall


def decompress(source: Path, target: Path) -> None:
    opener = {".bz2": bz2.open, ".zst": zstd.open, ".gz": gzip.open}[source.suffix]
    with opener(source, "rb") as src, target.open("wb") as dst:
        shutil.copyfileobj(src, dst, 1 << 20)


def parse_and_store(dem: Path, workdir: Path) -> dict[str, int]:
    parser = DemoParser(str(dem))
    available = set(parser.list_game_events())
    events = parser.parse_events([e for e in KEY_EVENTS if e in available])
    sizes = {"events": 0}
    for name, frame in events:
        target = workdir / f"event_{name}.parquet"
        pl.from_pandas(frame).write_parquet(target, compression="zstd")
        sizes["events"] += target.stat().st_size
    max_tick = int(parser.parse_event("round_freeze_end")["tick"].max() or 0)
    header_ticks = int(parser.parse_header().get("playback_ticks") or 0)
    last = max(max_tick, header_ticks)
    ticks = parser.parse_ticks(TICK_PROPS, ticks=list(range(0, last + 1, SAMPLE_EVERY_TICKS)))
    target = workdir / "ticks_16hz.parquet"
    pl.from_pandas(ticks).write_parquet(target, compression="zstd")
    sizes["ticks_16hz"] = target.stat().st_size
    return sizes


def recompress(dem: Path) -> dict[str, Any]:
    raw = dem.read_bytes()
    result: dict[str, Any] = {"dem_bytes": len(raw)}
    for level in ZSTD_LEVELS:
        packed, cpu, wall = measured(lambda lvl=level: zstd.compress(raw, level=lvl))
        result[f"zstd{level}"] = {"bytes": len(packed), "cpu_s": cpu, "wall_s": wall}
    return result


def analyze(demo_path: str) -> dict[str, Any]:
    """Runs in a child process so CPU time is this demo's only."""
    source = Path(demo_path)
    report: dict[str, Any] = {"file": source.name, "source_bytes": source.stat().st_size}
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        dem = source
        if source.suffix != ".dem":
            dem = workdir / "demo.dem"
            _, report["decompress_cpu_s"], _ = measured(lambda: decompress(source, dem))
        report.update(recompress(dem))
        sizes, report["parse_cpu_s"], report["parse_wall_s"] = measured(
            lambda: parse_and_store(dem, workdir)
        )
        report["parquet_bytes"] = sizes
    return report


def summary(reports: list[dict[str, Any]]) -> str:
    ok = [r for r in reports if "error" not in r]

    def med(values: list[float]) -> str:
        return f"{statistics.median(values):.1f} / {max(values):.1f}"

    lines = [f"{len(ok)} demos (median / max)"]
    lines.append(f"  .dem MB: {med([r['dem_bytes'] / 1e6 for r in ok])}")
    for level in ZSTD_LEVELS:
        ratio = [r[f"zstd{level}"]["bytes"] / r["dem_bytes"] for r in ok]
        cpu = [r[f"zstd{level}"]["cpu_s"] for r in ok]
        ratios = f"{statistics.median(ratio):.3f} / {max(ratio):.3f}"
        lines.append(f"  zstd {level:>2}: ratio {ratios}  cpu s {med(cpu)}")
    lines.append(f"  parse+store cpu s: {med([r['parse_cpu_s'] for r in ok])}")
    lines.append(f"  parse+store wall s: {med([r['parse_wall_s'] for r in ok])}")
    parquet = [sum(r["parquet_bytes"].values()) / 1e6 for r in ok]
    lines.append(f"  parquet MB: {med(parquet)}")
    bz = [r["decompress_cpu_s"] for r in ok if r["file"].endswith(".bz2")]
    if bz:
        lines.append(f"  bz2 decompress cpu s: {med(bz)}")
    return "\n".join(lines)


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    demos = sorted(
        p
        for directory in sys.argv[1:]
        for p in Path(directory).expanduser().iterdir()
        if p.name.endswith(DEMO_SUFFIXES)
    )
    if not demos:
        sys.exit("no demo found")
    reports: list[dict[str, Any]] = []
    for demo in demos:
        print(f"-> {demo.name}", flush=True)
        with ProcessPoolExecutor(max_workers=1, mp_context=get_context("spawn")) as pool:
            try:
                reports.append(pool.submit(analyze, str(demo)).result())
            except Exception as error:
                reports.append({"file": demo.name, "error": str(error)[:300]})
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "costs.json").write_text(json.dumps(reports, indent=2))
    print(summary(reports))


if __name__ == "__main__":
    main()
