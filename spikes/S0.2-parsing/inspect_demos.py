# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Spike S0.2: inspect and benchmark every demo in a directory.

For each demo (.dem, .dem.bz2, .dem.zst, .dem.gz), in a fresh process so peak memory is per demo:
  - header, available game events and event counts;
  - which tick properties exist and how often they are non-null (incl. usercmd props);
  - time and peak RSS of a full-rate parse and a 16 Hz parse, and the resulting Parquet sizes.

Writes out/report.json and out/report.md next to this script.

Usage: python inspect_demos.py <demo_dir>
"""

from __future__ import annotations

import bz2
import gzip
import json
import shutil
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path
from typing import Any

import polars as pl
from compression import zstd
from demoparser2 import DemoParser

OUT_DIR = Path(__file__).parent / "out"
DEMO_SUFFIXES = (".dem", ".dem.bz2", ".dem.zst", ".dem.gz")
SAMPLE_EVERY_TICKS = 4  # 64 tick / 4 = 16 Hz

KEY_EVENTS = [
    "player_death",
    "player_hurt",
    "weapon_fire",
    "player_blind",
    "round_start",
    "round_freeze_end",
    "round_end",
    "round_officially_ended",
    "bomb_planted",
    "bomb_defused",
    "bomb_exploded",
    "flashbang_detonate",
    "hegrenade_detonate",
    "smokegrenade_detonate",
    "inferno_startburn",
    "item_purchase",
    "bullet_impact",
]

PROBE_PROPS = [
    "X", "Y", "Z", "pitch", "yaw", "velocity_X", "velocity_Y", "velocity_Z",
    "health", "armor_value", "is_alive", "team_num",
    "balance", "current_equip_value", "round_start_equip_value",
    "active_weapon_name", "inventory", "is_scoped", "shots_fired", "accuracy_penalty",
    "inaccuracy", "ducking", "is_airborne", "flash_duration", "aim_punch_angle",
    "ping", "last_place_name", "spotted", "approximate_spotted_by",
    "usercmd_viewangle_x", "usercmd_viewangle_y", "usercmd_mouse_dx", "usercmd_mouse_dy",
    "usercmd_buttonstate_1", "usercmd_subtick_moves", "usercmd_input_history",
]  # fmt: skip

BENCH_PROPS = [
    "X", "Y", "Z", "pitch", "yaw", "health", "armor_value", "is_alive", "team_num",
    "active_weapon_name", "balance", "current_equip_value", "last_place_name",
    "flash_duration", "ducking", "is_scoped",
]  # fmt: skip


def decompress(source: Path, workdir: Path) -> Path:
    name = source.name
    if name.endswith(".dem"):
        return source
    target = workdir / name.rsplit(".", 1)[0]
    opener = {".bz2": bz2.open, ".zst": zstd.open, ".gz": gzip.open}[source.suffix]
    with opener(source, "rb") as src, target.open("wb") as dst:
        shutil.copyfileobj(src, dst, length=16 * 1024 * 1024)
    return target


def peak_rss_mb() -> float:
    """Peak resident memory of the current process, in MiB (Linux, macOS and Windows)."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        # Without restype/argtypes, ctypes truncates the pseudo-handle (-1) to a 32-bit int: the
        # call then fails with ERROR_INVALID_HANDLE and every peak reads as 0.
        kernel32 = ctypes.WinDLL("kernel32")
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi")
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        if not psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        ):
            raise ctypes.WinError()
        return counters.PeakWorkingSetSize / (1024 * 1024)

    import resource

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024  # bytes vs KiB


def timed(fn: Any, *args: Any, **kwargs: Any) -> tuple[Any, float]:
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    return result, time.perf_counter() - start


def analyze(demo_path: str) -> dict[str, Any]:
    """Runs in a child process. Returns plain JSON-serializable data."""
    source = Path(demo_path)
    report: dict[str, Any] = {"file": source.name, "compressed_bytes": source.stat().st_size}
    with tempfile.TemporaryDirectory() as tmp:
        dem, report["decompress_s"] = timed(decompress, source, Path(tmp))
        report["dem_bytes"] = dem.stat().st_size
        parser = DemoParser(str(dem))

        report["header"] = parser.parse_header()
        available = set(parser.list_game_events())
        report["events_available"] = sorted(available)
        wanted = [e for e in KEY_EVENTS if e in available]
        report["events_missing"] = [e for e in KEY_EVENTS if e not in available]
        events, report["parse_events_s"] = timed(parser.parse_events, wanted)
        report["event_counts"] = {name: len(df) for name, df in events}

        # Full-rate parse of the useful props (the expensive path).
        full, report["parse_ticks_full_s"] = timed(parser.parse_ticks, BENCH_PROPS)
        full_pl = pl.from_pandas(full)
        report["ticks_full_rows"] = full_pl.height
        max_tick = int(full_pl["tick"].max())  # type: ignore[arg-type]
        report["max_tick"] = max_tick
        report["tickrate_from_header"] = report["header"].get("tickrate") or report["header"].get(
            "playback_ticks"
        )

        # 16 Hz parse (what the product would store by default).
        sampled_ticks = list(range(0, max_tick + 1, SAMPLE_EVERY_TICKS))
        sampled, report["parse_ticks_16hz_s"] = timed(
            parser.parse_ticks, BENCH_PROPS, ticks=sampled_ticks
        )
        sampled_pl = pl.from_pandas(sampled)
        for label, frame in (("full", full_pl), ("16hz", sampled_pl)):
            target = Path(tmp) / f"ticks_{label}.parquet"
            frame.write_parquet(target, compression="zstd")
            report[f"parquet_{label}_bytes"] = target.stat().st_size

        # Property probe on a 1 Hz sample: does it exist, and how often is it non-null?
        probe_ticks = list(range(0, max_tick + 1, 64))
        probes: dict[str, Any] = {}
        for prop in PROBE_PROPS:
            try:
                df = pl.from_pandas(parser.parse_ticks([prop], ticks=probe_ticks))
                if prop not in df.columns:
                    probes[prop] = {"exists": False}
                    continue
                column = df[prop]
                probes[prop] = {
                    "exists": True,
                    "non_null_pct": round(100 * (1 - column.null_count() / max(df.height, 1)), 1),
                    "example": str(column.drop_nulls().head(1).to_list()),
                }
            except Exception as error:  # demoparser2 raises on unknown props
                probes[prop] = {"exists": False, "error": str(error)[:200]}
        report["props"] = probes
    report["peak_rss_mb"] = round(peak_rss_mb(), 1)
    return report


def to_markdown(reports: list[dict[str, Any]]) -> str:
    lines = [
        "| Démo | Taille comp. / .dem (Mo) | Parse plein (s) | Parse 16 Hz (s) "
        "| Parquet 16 Hz (Mo) | RAM max (Mo) | Événements manquants |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in reports:
        if "error" in r:
            lines.append(f"| {r['file']} | erreur : {r['error']} | | | | | |")
            continue
        lines.append(
            f"| {r['file']} | {r['compressed_bytes'] / 1e6:.0f} / {r['dem_bytes'] / 1e6:.0f} "
            f"| {r['parse_ticks_full_s']:.1f} | {r['parse_ticks_16hz_s']:.1f} "
            f"| {r['parquet_16hz_bytes'] / 1e6:.1f} | {r['peak_rss_mb']:.0f} "
            f"| {', '.join(r['events_missing']) or '—'} |"
        )
    ok = [r for r in reports if "props" in r]
    if ok:
        lines += ["", "| Prop | Présente (démos) | Non-null moyen (%) |", "|---|---|---|"]
        for prop in PROBE_PROPS:
            present = [r["props"][prop] for r in ok if r["props"][prop]["exists"]]
            mean = sum(p["non_null_pct"] for p in present) / len(present) if present else 0.0
            lines.append(f"| `{prop}` | {len(present)}/{len(ok)} | {mean:.1f} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    demo_dir = Path(sys.argv[1]).expanduser()
    demos = sorted(p for p in demo_dir.iterdir() if p.name.endswith(DEMO_SUFFIXES))
    if not demos:
        sys.exit(f"no demo found in {demo_dir}")

    reports: list[dict[str, Any]] = []
    for demo in demos:
        print(f"-> {demo.name}", flush=True)  # ASCII: the Windows console may be cp1252
        # One fresh process per demo so ru_maxrss is that demo's peak.
        with ProcessPoolExecutor(max_workers=1, mp_context=get_context("spawn")) as pool:
            try:
                reports.append(pool.submit(analyze, str(demo)).result())
            except Exception as error:
                reports.append({"file": demo.name, "error": str(error)[:300]})

    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "report.json").write_text(json.dumps(reports, indent=2, default=str))
    (OUT_DIR / "report.md").write_text(to_markdown(reports))
    print(f"\nWrote {OUT_DIR / 'report.md'}")


if __name__ == "__main__":
    main()
