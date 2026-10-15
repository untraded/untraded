# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
import bz2
import gzip
import hashlib
from collections.abc import Callable
from pathlib import Path

import pytest
from compression import zstd

from untraded.demofile import (
    DEMO_MAGIC,
    CorruptDemoError,
    NotADemoError,
    demo_suffix,
    digest,
    plain_demo,
)

CONTENT = DEMO_MAGIC + bytes(range(256)) * 9000  # ~2.3 MB: spans several read chunks


def write(tmp_path: Path, suffix: str, content: bytes = CONTENT) -> Path:
    path = tmp_path / f"match{suffix}"
    packers: dict[str, Callable[[bytes], bytes]] = {
        ".dem.bz2": bz2.compress,
        ".dem.gz": gzip.compress,
        ".dem.zst": zstd.compress,
    }
    path.write_bytes(packers.get(suffix, bytes)(content))
    return path


@pytest.mark.parametrize("suffix", [".dem", ".dem.bz2", ".dem.gz", ".dem.zst"])
def test_digest_is_the_same_whatever_the_compression(tmp_path: Path, suffix: str) -> None:
    found = digest(write(tmp_path, suffix))
    assert found.sha256 == hashlib.sha256(CONTENT).hexdigest()
    assert found.size == len(CONTENT)


@pytest.mark.parametrize(
    ("name", "suffix"),
    [
        ("a.dem", ".dem"),
        ("a.DEM.BZ2", ".dem.bz2"),
        ("a.dem.gz", ".dem.gz"),
        ("x.dem.zst", ".dem.zst"),
    ],
)
def test_demo_suffix(name: str, suffix: str) -> None:
    assert demo_suffix(Path(name)) == suffix


@pytest.mark.parametrize("name", ["a.zip", "a.bz2", "dem", "a.dem.rar"])
def test_demo_suffix_rejects_other_files(name: str) -> None:
    with pytest.raises(NotADemoError):
        demo_suffix(Path(name))


def test_digest_rejects_a_file_that_is_not_a_demo(tmp_path: Path) -> None:
    with pytest.raises(NotADemoError, match="not a CS2 demo"):
        digest(write(tmp_path, ".dem.bz2", b"HL2DEMO\x00" + bytes(100)))


def test_digest_reports_a_truncated_archive(tmp_path: Path) -> None:
    path = write(tmp_path, ".dem.bz2")
    path.write_bytes(path.read_bytes()[: path.stat().st_size // 2])
    with pytest.raises(CorruptDemoError):
        digest(path)


def test_plain_demo_returns_a_plain_file_untouched(tmp_path: Path) -> None:
    path = write(tmp_path, ".dem")
    with plain_demo(path) as dem:
        assert dem == path


def test_plain_demo_decompresses_only_the_requested_prefix(tmp_path: Path) -> None:
    with plain_demo(write(tmp_path, ".dem.zst"), limit=1000) as dem:
        assert dem.read_bytes() == CONTENT[:1000]
    assert not dem.exists()  # temporary file is cleaned up
