# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""`untraded` command line."""

from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from tempfile import TemporaryDirectory

import polars as pl

from untraded import corpus, fixtures, reference, report, resources
from untraded.corpus.sync import SftpRemote, SyncError, SyncReport, pull, push
from untraded.demofile import CorruptDemoError, NotADemoError
from untraded.derive import derive
from untraded.metrics import REGISTRY, Dataset, compute, compute_table
from untraded.parsing import (
    MODES,
    CanonicalError,
    CanonicalMatch,
    UnsupportedModeError,
    parse_demo,
)
from untraded.validation import csdm

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
        fixtures.FixtureError,
        reference.ReferenceError,
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
    analyze.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="report on stdout: terminal table (default) or JSON",
    )
    analyze.add_argument(
        "--out", type=Path, help="also write tables and metrics as Parquet: OUT/matches/<id>/"
    )
    analyze.set_defaults(run=_analyze)

    ref = commands.add_parser(
        "reference",
        help="compare a session with the player's own reference (the 30 days before it)",
    )
    ref.add_argument(
        "matches",
        nargs="+",
        type=Path,
        help="match directories written by `untraded parse --out` (session and history)",
    )
    ref.add_argument("--player", required=True, type=int, help="SteamID64 of the player")
    ref.add_argument(
        "--session",
        required=True,
        action="append",
        metavar="MATCH_ID",
        help="a match of the session (its directory name); repeat for each match",
    )
    ref.add_argument("--format", choices=["table", "json"], default="table")
    ref.set_defaults(run=_reference)

    check = commands.add_parser(
        "compare-csdm", help="compare our stats with CS Demo Manager's analyzer, demo by demo"
    )
    check.add_argument("demos", nargs="+", type=Path)
    check.add_argument("--csda", required=True, type=Path, help="cs-demo-analyzer executable")
    check.add_argument("--mode", required=True, choices=MODES, help="game mode of the matches")
    check.add_argument("--out", type=Path, help="also write the comparison as Parquet")
    check.add_argument(
        "--jobs",
        type=_positive_int,
        help="demos compared at once (default: as many as the free RAM allows, adjusted live)",
    )
    check.set_defaults(run=_compare_csdm)

    fixture = commands.add_parser(
        "fixture", help="anonymized extract of a few rounds, for tests and bug reports"
    )
    fixture_actions = fixture.add_subparsers(required=True, metavar="action")
    extract = fixture_actions.add_parser(
        "extract", help="parse a demo and write an anonymized window of rounds"
    )
    extract.add_argument("demo", type=Path)
    extract.add_argument("--mode", required=True, choices=MODES, help="game mode of the match")
    extract.add_argument("--rounds", required=True, type=_round_range, metavar="FIRST-LAST")
    extract.add_argument("--name", required=True, help="fixture name, also its match id")
    extract.add_argument("--out", required=True, type=Path, help="fixture directory to write")
    extract.set_defaults(run=_fixture_extract)
    expect = fixture_actions.add_parser(
        "expect", help="recompute expected_metrics.json after an intended metric change"
    )
    expect.add_argument("dirs", nargs="+", type=Path)
    expect.set_defaults(run=_fixture_expect)

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


def _positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1, got {number}")
    return number


def _parse(args: argparse.Namespace) -> int:
    match = parse_demo(args.demo, source=args.source, mode=args.mode, played_at=args.played_at)
    target = match.write(args.out)
    info = match.match.row(0, named=True)
    print(
        f"{info['map']} {info['score_a']}-{info['score_b']}, {info['rounds_played']} rounds, "
        f"{match.kill.height} kills, {match.player.height} players -> {target}"
    )
    return 0


def _analyze(args: argparse.Namespace) -> int:
    # Player names may hold characters the console cannot encode (e.g. cp1252 on Windows).
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(errors="replace")
    canonical = parse_demo(args.demo, source="upload", mode=args.mode)
    derived = derive(canonical.tables()).tables()
    tables = {**canonical.tables(), **derived}
    if args.out:
        dataset = Dataset.from_matches([tables])
        if args.side:
            dataset = dataset.split(side=args.side)
        target = canonical.write(args.out)
        for name, frame in derived.items():
            frame.write_parquet(target / f"{name}.parquet", compression="zstd")
        compute(dataset).write_parquet(target / "metrics.parquet", compression="zstd")
        for metric_id in sorted(m.id for m in REGISTRY.values() if m.kind == "table"):
            compute_table(dataset, metric_id).write_parquet(
                target / f"metric_{metric_id}.parquet", compression="zstd"
            )
    match_report = report.build_report(tables, side=args.side)
    if args.format == "json":
        print(json.dumps(report.to_json(match_report), ensure_ascii=False, indent=2))
    else:
        print(report.render_table(match_report))
    return 0


REFERENCE_TABLE = (
    "base.kast",
    "base.adr",
    "base.kpr",
    "base.dpr",
    "duel.opening_success_pct",
    "trade.traded_death_pct",
    "trade.untraded_deaths",
    "duel.isolated_death_pct",
    "util.blind_per_flash",
    "rating.hltv1",
)
"""Metrics of the terminal table of `untraded reference` (JSON has them all)."""


def _reference(args: argparse.Namespace) -> int:
    matches = []
    for directory in args.matches:
        canonical = CanonicalMatch.read(directory)
        tables = canonical.tables()
        matches.append({**tables, **derive(tables).tables()})
    result = reference.compare_to_self(matches, args.player, set(args.session))
    if args.format == "json":
        payload = {
            "player": str(result.player),
            "session": {"matches": result.session_matches, "rounds": result.session_rounds},
            "reference": {
                "from": result.reference_from.isoformat(),
                "to": result.reference_to.isoformat(),
                "matches": result.reference_matches,
                "rounds": result.reference_rounds,
                "enough": result.enough,
            },
            "values": result.values.to_dicts(),
        }
        print(json.dumps(payload, indent=2))
        return 0
    print(
        f"Session: {result.session_matches} match(es), {result.session_rounds} rounds. "
        f"Reference {result.reference_from} to {result.reference_to}: "
        f"{result.reference_matches} match(es), {result.reference_rounds} rounds."
    )
    if not result.enough:
        print(
            f"Not enough matches yet for a reference (at least {reference.MIN_MATCHES} matches "
            f"and {reference.MIN_ROUNDS} rounds)."
        )
    print(f"{'metric':<28}{'basis':>10}{'session':>10}{'reference':>11}{'delta':>9}")
    rows = result.values.filter(pl.col("metric").is_in(REFERENCE_TABLE))
    for row in rows.iter_rows(named=True):
        cells = [row[k] for k in ("session", "reference", "delta")]
        text = [f"{v:.2f}" if v is not None else "-" for v in cells]
        print(f"{row['metric']:<28}{row['basis']:>10}{text[0]:>10}{text[1]:>11}{text[2]:>9}")
    return 0


def _compare_csdm(args: argparse.Namespace) -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(errors="replace")
    demos: list[Path] = args.demos

    def started(index: int, running: int, threads: int) -> None:
        detail = f", {running} running, {threads} threads" if threads else ""
        print(f"{demos[index].name}: started{detail}", flush=True)

    failed: dict[int, str] = {}

    def failure(error: resources.TaskError) -> None:
        failed[error.index] = str(error).partition(": ")[2] or str(error)
        print(f"{demos[error.index].name}: FAILED, {failed[error.index]}", flush=True)

    tasks = [(demo, args.csda, args.mode) for demo in demos]
    frames: dict[int, pl.DataFrame] = {}
    for index, frame in resources.run_adaptive(
        _compare_one, tasks, jobs=args.jobs, on_start=started, on_error=failure
    ):
        frames[index] = frame
        done = len(frames) + len(failed)
        print(f"[{done}/{len(demos)}] {demos[index].name}: compared", flush=True)
    if not frames:
        print("error: no demo could be compared", file=sys.stderr)
        return 1
    # Input order, whatever the completion order, so the output does not depend on the workers.
    comparison = pl.concat([frames[i] for i in sorted(frames)])
    if args.out is not None:
        args.out.mkdir(parents=True, exist_ok=True)
        comparison.write_parquet(args.out / "comparison.parquet")
    print(f"{'field':<22}{'rule':>6}{'players':>9}{'gaps':>6}{'max diff':>10}")
    for row in csdm.summary(comparison).iter_rows(named=True):
        print(
            f"{row['field']:<22}{row['rule']:>6}{row['players']:>9}{row['gaps']:>6}"
            f"{row['max_abs_diff'] if row['max_abs_diff'] is not None else float('nan'):>10.2f}"
        )
    if failed:
        print(f"{len(failed)} demo(s) failed and are not in the comparison:", file=sys.stderr)
        for index in sorted(failed):
            print(f"  {demos[index]}: {failed[index]}", file=sys.stderr)
        return 1
    return 0


def _compare_one(task: tuple[Path, Path, str]) -> pl.DataFrame:
    """One demo of `compare-csdm`; module-level so it can run in a worker process."""
    demo, csda_path, mode = task
    canonical = parse_demo(demo, source="upload", mode=mode)
    tables = canonical.tables()
    ds = Dataset.from_matches([{**tables, **derive(tables).tables()}])
    with TemporaryDirectory(prefix="untraded-compare-") as tmp:
        export = csdm.load_export(csdm.run_csda(csda_path, demo, Path(tmp) / "export.json"))
    match_id = canonical.match["match_id"][0]
    return csdm.compare(csdm.our_values(ds), csdm.csdm_values(export)).with_columns(
        pl.lit(match_id).alias("match_id")
    )


def _round_range(value: str) -> tuple[int, int]:
    first, _, last = value.partition("-")
    try:
        bounds = int(first), int(last or first)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected FIRST-LAST, got {value!r}") from None
    if not 1 <= bounds[0] <= bounds[1]:
        raise argparse.ArgumentTypeError(f"expected 1 <= FIRST <= LAST, got {value!r}")
    return bounds


def _fixture_extract(args: argparse.Namespace) -> int:
    first, last = args.rounds
    canonical = parse_demo(args.demo, source="upload", mode=args.mode)
    window = fixtures.anonymize(fixtures.extract(canonical.tables(), first, last), args.name)
    meta = fixtures.metadata(first=first, last=last, tables=window)
    fixtures.write(args.out, window, meta)
    size = sum(f.stat().st_size for f in args.out.iterdir() if f.is_file())
    print(
        f"{args.name}: rounds {first}-{last}, {window['player'].height} players, "
        f"{size / 1e6:.2f} MB -> {args.out}"
    )
    print(
        f'Record the source privately: {args.name} = "<corpus demo id>" in the file named by '
        "UNTRADED_FIXTURE_SOURCES (never in this repository)."
    )
    return 0


def _fixture_expect(args: argparse.Namespace) -> int:
    for directory in args.dirs:
        fixtures.write_expected(directory, fixtures.read(directory))
        print(f"{directory}: {fixtures.EXPECTED} rewritten")
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
