# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""`untraded` command line."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from untraded import corpus
from untraded.demofile import CorruptDemoError, NotADemoError

DEFAULT_MANIFEST = Path("corpus") / "manifest.toml"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return int(args.run(args))
    except (corpus.ManifestError, NotADemoError, CorruptDemoError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="untraded", description=__doc__)
    commands = parser.add_subparsers(required=True, metavar="command")

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
    return parser


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


def _list(args: argparse.Namespace) -> int:
    manifest = corpus.load(args.manifest)
    for d in manifest.demos:
        size = f"{d.bytes / 1e6:.0f} MB"
        print(f"{d.id:<40} {d.source:<14} {d.map:<12} {d.game_build:<6} {size:>7}")
    print(f"{len(manifest.demos)} demos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
