# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The local corpus directory: `$UNTRADED_CORPUS_DIR/demos/<sha256><stored_as>`."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from untraded.corpus.manifest import CorpusDemo, Manifest
from untraded.demofile import CorruptDemoError, NotADemoError, demo_suffix, digest, zstd
from untraded.parsing import DemoHeader, read_header

HeaderReader = Callable[[Path], DemoHeader]
# Cheap and within 6 % of level 9 on CS2 demos (spike S0.6).
ZSTD_LEVEL = 3


def demos_dir(corpus_dir: Path) -> Path:
    return corpus_dir / "demos"


def stored_path(corpus_dir: Path, demo: CorpusDemo) -> Path:
    return demos_dir(corpus_dir) / demo.filename


@dataclass(frozen=True)
class Added:
    demo: CorpusDemo
    new: bool
    """False when the same demo was already in the manifest."""


def add(
    manifest: Manifest,
    corpus_dir: Path,
    file: Path,
    *,
    source: str,
    played_at: str | None = None,
    notes: str = "",
    demo_id: str | None = None,
    header_reader: HeaderReader = read_header,
) -> Added:
    """Adds a demo to the manifest and copies it into the corpus directory.

    Compressed demos are stored as received; a plain `.dem` is compressed once with zstd (ADR 0009).
    """
    received = demo_suffix(file)
    suffix = ".dem.zst" if received == ".dem" else received
    found = digest(file)
    if (existing := manifest.by_sha256(found.sha256)) is not None:
        return Added(existing, new=False)
    header = header_reader(file)
    demo = CorpusDemo(
        id=demo_id or manifest.next_id(source, played_at, header.map_name),
        source=source,
        map=header.map_name,
        played_at=played_at,
        sha256=found.sha256,
        bytes=found.size,
        stored_as=suffix,
        game_build=header.game_build,
        notes=notes,
    )
    manifest.add(demo)
    target = stored_path(corpus_dir, demo)
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name + ".part")
        if received == ".dem":
            with file.open("rb") as src, zstd.open(partial, "wb", level=ZSTD_LEVEL) as dst:
                shutil.copyfileobj(src, dst, 1 << 20)
        else:
            shutil.copyfile(file, partial)
        partial.replace(target)
    return Added(demo, new=True)


class Status(StrEnum):
    OK = "ok"
    MISSING = "missing"
    CORRUPT = "corrupt"


def verify(demo: CorpusDemo, corpus_dir: Path, *, full: bool = True) -> Status:
    """Checks the stored file. `full` re-hashes it; otherwise only its presence is checked."""
    path = stored_path(corpus_dir, demo)
    if not path.exists():
        return Status.MISSING
    if not full:
        return Status.OK
    try:
        found = digest(path)
    except (CorruptDemoError, NotADemoError):
        return Status.CORRUPT
    if (found.sha256, found.size) != (demo.sha256, demo.bytes):
        return Status.CORRUPT
    return Status.OK
