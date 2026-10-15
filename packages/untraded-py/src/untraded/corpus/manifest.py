# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The corpus manifest (`corpus/manifest.toml`): one entry per reference demo (ADR 0010).

Demo files never go into git: the manifest records what they are, and their sha256 lets every
machine check and rebuild the same corpus.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
SOURCES = ("valve-premier", "faceit", "esea", "scrim", "pro")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_HEADER = """\
# Reference demo corpus (ADR 0010). Demo files are NEVER committed: they live in
# $UNTRADED_CORPUS_DIR/demos/<sha256><stored_as> and in the private shared store.
# Edit with `untraded corpus add`; see corpus/README.md.
#
# id          stable, human-readable
# source      valve-premier | faceit | esea | scrim | pro
# map         from the demo header
# played_at   YYYY-MM-DD, when known (the demo does not carry it)
# sha256      of the decompressed .dem
# bytes       decompressed size
# stored_as   suffix of the stored file, as received (ADR 0009)
# game_build  CS2 patch version, from the demo header
"""


class ManifestError(ValueError):
    """The manifest is malformed or inconsistent."""


@dataclass(frozen=True)
class CorpusDemo:
    id: str
    source: str
    map: str
    sha256: str
    bytes: int
    stored_as: str
    game_build: str
    played_at: str | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            raise ManifestError("demo id is empty")
        if self.source not in SOURCES:
            raise ManifestError(f"{self.id}: source {self.source!r} not in {SOURCES}")
        if not _SHA256.match(self.sha256):
            raise ManifestError(f"{self.id}: sha256 must be 64 lowercase hex characters")
        if self.bytes <= 0:
            raise ManifestError(f"{self.id}: bytes must be positive")
        if self.played_at is not None and not _DATE.match(self.played_at):
            raise ManifestError(f"{self.id}: played_at must be YYYY-MM-DD")

    @property
    def filename(self) -> str:
        """Name of the stored file: `<sha256><stored_as>`."""
        return f"{self.sha256}{self.stored_as}"


@dataclass
class Manifest:
    demos: list[CorpusDemo] = field(default_factory=list)

    def by_sha256(self, sha256: str) -> CorpusDemo | None:
        return next((d for d in self.demos if d.sha256 == sha256), None)

    def by_id(self, demo_id: str) -> CorpusDemo | None:
        return next((d for d in self.demos if d.id == demo_id), None)

    def add(self, demo: CorpusDemo) -> None:
        if self.by_id(demo.id) is not None:
            raise ManifestError(f"duplicate id {demo.id!r}")
        if (same := self.by_sha256(demo.sha256)) is not None:
            raise ManifestError(f"{demo.id}: same demo as {same.id!r}")
        self.demos.append(demo)

    def next_id(self, source: str, played_at: str | None, map_name: str) -> str:
        """`<source>-<date>-<map>-<nn>`, e.g. `faceit-2026-10-14-nuke-01`."""
        stem = f"{source}-{played_at or 'undated'}-{map_name.removeprefix('de_') or 'unknown'}"
        n = 1
        while self.by_id(f"{stem}-{n:02d}") is not None:
            n += 1
        return f"{stem}-{n:02d}"


def load(path: Path) -> Manifest:
    """Reads a manifest; a missing file is an empty manifest."""
    if not path.exists():
        return Manifest()
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    version = data.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ManifestError(f"{path}: schema_version {version!r}, expected {SCHEMA_VERSION}")
    manifest = Manifest()
    for entry in data.get("demo", []):
        try:
            manifest.add(CorpusDemo(**entry))
        except TypeError as error:
            raise ManifestError(f"{path}: invalid entry {entry.get('id')!r}: {error}") from error
    return manifest


def dumps(manifest: Manifest) -> str:
    lines = [_HEADER, f"schema_version = {SCHEMA_VERSION}"]
    for demo in manifest.demos:
        lines += ["", "[[demo]]"]
        for key, value in _fields(demo):
            lines.append(f"{key} = {_toml_value(value)}")
    return "\n".join(lines) + "\n"


def save(manifest: Manifest, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps(manifest), encoding="utf-8", newline="\n")


def _fields(demo: CorpusDemo) -> list[tuple[str, Any]]:
    fields: list[tuple[str, Any]] = [
        ("id", demo.id),
        ("source", demo.source),
        ("map", demo.map),
    ]
    if demo.played_at is not None:
        fields.append(("played_at", demo.played_at))
    fields += [
        ("sha256", demo.sha256),
        ("bytes", demo.bytes),
        ("stored_as", demo.stored_as),
        ("game_build", demo.game_build),
    ]
    if demo.notes:
        fields.append(("notes", demo.notes))
    return fields


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    # JSON string escapes are valid TOML basic-string escapes; TOML also forbids a raw DEL.
    return json.dumps(str(value), ensure_ascii=False).replace("\x7f", "\\u007F")
