# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from untraded_worker.store import LocalStore, StoreError


@pytest.mark.parametrize("key", ["", "/etc/passwd", "../outside", "demos/../../x", "demos\\x"])
def test_keys_cannot_escape_the_store(tmp_path: Path, key: str) -> None:
    with pytest.raises(StoreError):
        LocalStore(tmp_path).path(key)


def test_put_exists_delete(tmp_path: Path) -> None:
    store = LocalStore(tmp_path / "store")
    source = tmp_path / "match.dem"
    source.write_bytes(b"demo")
    store.put_file("demos/abc.dem", source)
    assert store.exists("demos/abc.dem")
    assert store.path("demos/abc.dem").read_bytes() == b"demo"
    assert not list(store.root.rglob("*.part"))
    assert store.delete("demos/abc.dem")
    assert not store.delete("demos/abc.dem")
    assert not store.exists("demos/abc.dem")


def test_put_file_replaces_an_existing_object(tmp_path: Path) -> None:
    store = LocalStore(tmp_path / "store")
    source = tmp_path / "match.dem"
    for content in (b"first", b"second"):
        source.write_bytes(content)
        store.put_file("demos/abc.dem", source)
    assert store.path("demos/abc.dem").read_bytes() == b"second"


def test_tables_round_trip(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    kills = pl.DataFrame({"round": [1, 2], "attacker": ["a", "b"]})
    store.write_tables("matches/42", {"kills": kills})
    assert store.exists("matches/42/kills.parquet")
    assert store.read_table("matches/42", "kills").equals(kills)
    with pytest.raises(StoreError, match="missing"):
        store.read_table("matches/42", "damages")
