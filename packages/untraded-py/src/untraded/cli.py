# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""`untraded` command line."""

from __future__ import annotations

import argparse
import datetime as dt
import io
import os
import sys
from collections.abc import Sequence
from pathlib import Path

import polars as pl

from untraded import corpus
from untraded.corpus.sync import SftpRemote, SyncError, SyncReport, pull, push
from untraded.demofile import CorruptDemoError, NotADemoError
from untraded.derive import derive
from untraded.metrics import Dataset, compute
from untraded.parsing import MODES, CanonicalError, UnsupportedModeError, parse_demo

DEFAULT_MANIFEST = Path("corpus") / "manifest.toml"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return int(args.run(args))
    except (
        corpus.ManifestError,
        NotADemoError,
        CorruptDemoError,
        SyncError,
        CanonicalError,
        UnsupportedModeError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="untraded", description=__doc__)
    commands = parser.add_subparsers(required=True, metavar="command")

    parse = commands.add_parser("parse", help="parse a demo into canonical tables (Parquet)")
    parse.add_argument("demo", type=Path)
    parse.add_argument("--mode", required=True, choices=MODES, help="game mode of the match")
    parse.add_argument("--source", default="upload", help="where the demo came from")
    parse.add_argument("--played-at", type=dt.date.fromisoformat, metavar="YYYY-MM-DD")
    parse.add_argument("--out", type=Path, default=Path(), help="writes OUT/matches/<match_id>/")
    parse.set_defaults(run=_parse)

    analyze = commands.add_parser("analyze", help="parse a demo and print its players' metrics")
    analyze.add_argument("demo", type=Path)
    analyze.add_argument("--mode", required=True, choices=MODES, help="game mode of the match")
    analyze.add_argument("--side", choices=["CT", "T"], help="only rounds played on this side")
    analyze.add_argument("--out", type=Path, help="also write tables and metrics as Parquet")
    analyze.set_defaults(run=_analyze)

    corpus_parser = commands.add_parser("corpus", help="manage the reference demo corpus")
    corpus_parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(os.environ.get("UNTRADED_CORPUS_MANIFEST", DEFAULT_MANIFEST)),
        help="manifest file (default: $UNTRADED_CORPUS_MANIFEST or corpus/manifest.toml)",
    )
    corpus_parser.add_argument(
        "--dir",
        type=Path,
        default=os.environ.get("UNTRADED_CORPUS_DIR"),
        help="local corpus directory (default: $UNTRADED_CORPUS_DIR)",
    )
    actions = corpus_parser.add_subparsers(required=True, metavar="action")

    add = actions.add_parser("add", help="add demos to the manifest and the corpus directory")
    add.add_argument("files", nargs="+", type=Path)
    add.add_argument("--source", required=True, choices=corpus.SOURCES)
    add.add_argument("--played-at", metavar="YYYY-MM-DD")
    add.add_argument("--notes", default="")
    add.add_argument("--id", dest="demo_id", help="demo id (one file only)")
    add.set_defaults(run=_add)

    verify = actions.add_parser("verify", help="check that every demo is present and intact")
    verify.add_argument("ids", nargs="*", help="only these demos")
    verify.add_argument("--quick", action="store_true", help="check presence only, no hashing")
    verify.set_defaults(run=_verify)

    listing = actions.add_parser("list", help="list the demos in the manifest")
    listing.set_defaults(run=_list)

    for name, run, help_text in (
        ("push", _push, "upload to the shared store the demos it lacks"),
        ("pull", _pull, "download from the shared store the demos missing locally"),
    ):
        sync = actions.add_parser(name, help=help_text)
        sync.add_argument(
            "--remote",
            default=os.environ.get("UNTRADED_CORPUS_REMOTE"),
            help="shared store as ssh-host:path (default: $UNTRADED_CORPUS_REMOTE)",
        )
        sync.add_argument("--dry-run", action="store_true", help="only show what would be done")
        sync.set_defaults(run=run)
    return parser


def _parse(args: argparse.Namespace) -> int:
    match = parse_demo(args.demo, source=args.source, mode=args.mode, played_at=args.played_at)
    target = match.write(args.out)
    info = match.match.row(0, named=True)
    print(
        f"{info['map']} {info['score_a']}-{info['score_b']}, {info['rounds_played']} rounds, "
        f"{match.kill.height} kills, {match.player.height} players -> {target}"
    )
    return 0


SUMMARY = {
    "base.kills": "K",
    "base.deaths": "D",
    "base.assists": "A",
    "base.kd_diff": "+/-",
    "base.adr": "ADR",
    "base.hs_pct": "HS%",
    "base.kast": "KAST%",
}


def _analyze(args: argparse.Namespace) -> int:
    # Player names may hold characters the console cannot encode (e.g. cp1252 on Windows).
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(errors="replace")
    canonical = parse_demo(args.demo, source="upload", mode=args.mode)
    tables = {**canonical.tables(), **derive(canonical.tables()).tables()}
    dataset = Dataset.from_matches([tables])
    if args.side:
        dataset = dataset.split(side=args.side)
    results = compute(dataset)
    if args.out:
        target = canonical.write(args.out)
        for name, frame in derive(canonical.tables()).tables().items():
            frame.write_parquet(target / f"{name}.parquet", compression="zstd")
        results.write_parquet(target / "metrics.parquet", compression="zstd")
    info = canonical.match.row(0, named=True)
    side = f", {args.side} side" if args.side else ""
    print(
        f"{info['map']} {info['score_a']}-{info['score_b']} ({info['rounds_played']} rounds{side})"
    )
    wide = results.filter(pl.col("metric").is_in(list(SUMMARY))).pivot(
        on="metric", index="steamid", values="value"
    )
    rows = canonical.player.select("steamid", "team", "name").join(wide, on="steamid")
    print(f"{'team':<5}{'player':<24}" + "".join(f"{label:>7}" for label in SUMMARY.values()))
    for row in rows.sort("team", "base.kills", descending=[False, True]).iter_rows(named=True):
        cells = "".join(
            f"{row[key]:>7.0f}" if row[key] is not None else f"{'-':>7}" for key in SUMMARY
        )
        print(f"{row['team']:<5}{row['name'][:23]:<24}{cells}")
    return 0


def _corpus_dir(args: argparse.Namespace) -> Path:
    if args.dir is None:
        raise corpus.ManifestError("set UNTRADED_CORPUS_DIR or pass --dir")
    return Path(args.dir).expanduser()


def _add(args: argparse.Namespace) -> int:
    if args.demo_id and len(args.files) > 1:
        raise corpus.ManifestError("--id needs a single file")
    corpus_dir = _corpus_dir(args)
    manifest = corpus.load(args.manifest)
    for file in args.files:
        added = corpus.add(
            manifest,
            corpus_dir,
            file,
            source=args.source,
            played_at=args.played_at,
            notes=args.notes,
            demo_id=args.demo_id,
        )
        state = "added" if added.new else "already in corpus as"
        print(f"{file.name}: {state} {added.demo.id}")
        # Save after each demo so an interrupted batch keeps what was copied.
        corpus.save(manifest, args.manifest)
    return 0


def _verify(args: argparse.Namespace) -> int:
    corpus_dir = _corpus_dir(args)
    manifest = corpus.load(args.manifest)
    demos = [d for d in manifest.demos if not args.ids or d.id in args.ids]
    if unknown := set(args.ids) - {d.id for d in demos}:
        raise corpus.ManifestError(f"unknown ids: {', '.join(sorted(unknown))}")
    failures = 0
    for demo in demos:
        status = corpus.verify(demo, corpus_dir, full=not args.quick)
        failures += status is not corpus.Status.OK
        print(f"{status.value:<8} {demo.id}")
    print(f"{len(demos) - failures}/{len(demos)} ok")
    return 1 if failures else 0


def _remote(args: argparse.Namespace) -> SftpRemote:
    if not args.remote:
        raise SyncError("set UNTRADED_CORPUS_REMOTE or pass --remote (ssh-host:path)")
    return SftpRemote.parse(args.remote)


def _push(args: argparse.Namespace) -> int:
    report = push(
        corpus.load(args.manifest), _corpus_dir(args), _remote(args), dry_run=args.dry_run
    )
    return _print_report(report, "uploaded", args.dry_run)


def _pull(args: argparse.Namespace) -> int:
    report = pull(
        corpus.load(args.manifest), _corpus_dir(args), _remote(args), dry_run=args.dry_run
    )
    return _print_report(report, "downloaded", args.dry_run)


def _print_report(report: SyncReport, verb: str, dry_run: bool) -> int:
    for demo in report.done:
        print(f"{'would be ' if dry_run else ''}{verb}: {demo.id}")
    for demo, reason in report.skipped:
        print(f"skipped: {demo.id} ({reason})")
    done = f"{len(report.done)} {'to be ' if dry_run else ''}{verb}"
    print(f"{done}, {len(report.skipped)} skipped")
    return 1 if report.skipped else 0


def _list(args: argparse.Namespace) -> int:
    manifest = corpus.load(args.manifest)
    for d in manifest.demos:
        size = f"{d.bytes / 1e6:.0f} MB"
        print(f"{d.id:<40} {d.source:<14} {d.map:<12} {d.game_build:<6} {size:>7}")
    print(f"{len(manifest.demos)} demos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
