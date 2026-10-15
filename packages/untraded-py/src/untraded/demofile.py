# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""CS2 demo files as stored: plain `.dem`, or compressed `.dem.bz2`, `.dem.gz`, `.dem.zst`.

Valve serves bz2 and FACEIT zstd; demos are kept as received (ADR 0009). A demo is identified
by the sha256 of its decompressed content, so the same match from two sources is one demo.
"""

from __future__ import annotations

import bz2
import gzip
import hashlib
import io
import shutil
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

if sys.version_info >= (3, 14):
    from compression import zstd
else:  # pragma: no cover
    from backports import zstd

DEMO_MAGIC = b"PBDEMS2\x00"
SUFFIXES = (".dem", ".dem.bz2", ".dem.gz", ".dem.zst")
_CHUNK = 1 << 20

__all__ = [
    "DEMO_MAGIC",
    "SUFFIXES",
    "CorruptDemoError",
    "DemoDigest",
    "NotADemoError",
    "demo_suffix",
    "digest",
    "open_demo",
    "plain_demo",
    "zstd",
]


class NotADemoError(ValueError):
    """The file is not a CS2 demo (wrong name or content)."""


class CorruptDemoError(ValueError):
    """The compressed file is truncated or damaged."""


@dataclass(frozen=True)
class DemoDigest:
    sha256: str
    """Hex sha256 of the decompressed `.dem`."""
    size: int
    """Size of the decompressed `.dem`, in bytes."""


def demo_suffix(path: Path) -> str:
    """Returns the demo suffix of `path` (e.g. `.dem.bz2`), or raises NotADemoError."""
    name = path.name.lower()
    for suffix in sorted(SUFFIXES, key=len, reverse=True):
        if name.endswith(suffix):
            return suffix
    raise NotADemoError(f"{path.name}: expected one of {', '.join(SUFFIXES)}")


def open_demo(path: Path) -> io.BufferedIOBase:
    """Opens a demo for reading its decompressed bytes, whatever its suffix."""
    match demo_suffix(path):
        case ".dem.bz2":
            return bz2.open(path, "rb")
        case ".dem.gz":
            return gzip.open(path, "rb")
        case ".dem.zst":
            return zstd.open(path, "rb")
        case _:
            return path.open("rb")


def digest(path: Path) -> DemoDigest:
    """Hashes the decompressed demo, checking that it starts like a CS2 demo."""
    sha = hashlib.sha256()
    size = 0
    try:
        with open_demo(path) as demo:
            chunk = demo.read(_CHUNK)
            if not chunk.startswith(DEMO_MAGIC):
                raise NotADemoError(f"{path.name}: not a CS2 demo (missing {DEMO_MAGIC!r})")
            while chunk:
                sha.update(chunk)
                size += len(chunk)
                chunk = demo.read(_CHUNK)
    except (EOFError, zstd.ZstdError, OSError) as error:
        if isinstance(error, FileNotFoundError | PermissionError):
            raise
        raise CorruptDemoError(f"{path.name}: {error}") from error
    return DemoDigest(sha256=sha.hexdigest(), size=size)


@contextmanager
def plain_demo(path: Path, *, limit: int | None = None) -> Iterator[Path]:
    """Yields a path to the decompressed `.dem`, decompressing into a temporary file if needed.

    `limit` keeps only the first bytes: enough to read the header without decompressing it all.
    """
    if demo_suffix(path) == ".dem" and limit is None:
        yield path
        return
    with TemporaryDirectory(prefix="untraded-") as tmp:
        target = Path(tmp) / "demo.dem"
        with open_demo(path) as src, target.open("wb") as dst:
            if limit is None:
                shutil.copyfileobj(src, dst, _CHUNK)
            else:
                dst.write(src.read(limit))
        yield target
