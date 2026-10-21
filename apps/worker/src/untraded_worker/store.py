# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The object store of ADR 0009: raw demos and the Parquet tables of each match.

Keys are relative paths: `demos/{sha256}{suffix}` for a raw demo as received, and
`matches/{match_id}/{table}.parquet` for the canonical and derived tables. This is the local
filesystem (self-hosting); an S3-compatible store implements the same methods later.
"""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from pathlib import Path, PurePosixPath

import polars as pl


class StoreError(ValueError):
    """A key escapes the store, or an object is missing."""


class LocalStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def path(self, key: str) -> Path:
        """Where `key` lives. Refuses keys that are absolute or climb out of the store."""
        pure = PurePosixPath(key)
        if not pure.parts or pure.is_absolute() or ".." in pure.parts or "\\" in key:
            raise StoreError(f"invalid key: {key!r}")
        return self.root.joinpath(*pure.parts)

    def exists(self, key: str) -> bool:
        return self.path(key).exists()

    def put_file(self, key: str, source: Path) -> None:
        """Copies `source` under `key`, atomically: a reader never sees half a file."""
        target = self.path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name + ".part")
        shutil.copyfile(source, partial)
        partial.replace(target)

    def move_in(self, key: str, source: Path) -> None:
        """Moves `source` (a file already inside the store's volume) under `key`, atomically."""
        target = self.path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        source.replace(target)

    def delete(self, key: str) -> bool:
        """Deletes `key`; returns False if it was not there."""
        target = self.path(key)
        if not target.exists():
            return False
        target.unlink()
        return True

    def delete_prefix(self, prefix: str) -> bool:
        """Deletes everything under `prefix` (a match's tables); returns False if it was not
        there."""
        target = self.path(prefix)
        if not target.is_dir():
            return False
        shutil.rmtree(target)
        return True

    def write_tables(self, prefix: str, tables: Mapping[str, pl.DataFrame]) -> None:
        """Writes each table as `{prefix}/{name}.parquet` (zstd), atomically."""
        for name, table in tables.items():
            target = self.path(f"{prefix}/{name}.parquet")
            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_name(target.name + ".part")
            table.write_parquet(partial, compression="zstd")
            partial.replace(target)

    def read_tables(self, prefix: str) -> dict[str, pl.DataFrame]:
        """Every table under `prefix` (a match's canonical and derived tables)."""
        directory = self.path(prefix)
        tables = {
            f.name.removesuffix(".parquet"): pl.read_parquet(f) for f in directory.glob("*.parquet")
        }
        if not tables:
            raise StoreError(f"no tables under {prefix}")
        return tables

    def read_table(self, prefix: str, name: str) -> pl.DataFrame:
        source = self.path(f"{prefix}/{name}.parquet")
        if not source.exists():
            raise StoreError(f"missing: {prefix}/{name}.parquet")
        return pl.read_parquet(source)
