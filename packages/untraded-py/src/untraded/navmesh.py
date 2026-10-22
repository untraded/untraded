# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Reads a CS2 navigation mesh (`.nav`, versions 31 to 36): the walkable areas of a map, each a
polygon in world coordinates. Our radars are drawn from them.

Only what a drawing needs is kept: each area's corners. The layout follows awpy's parser
(`crates/awpy/src/nav.rs`, MIT, pnxenopoulos/awpy) and ValveResourceFormat's description of the
format; this is an independent implementation.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

MAGIC = 0xFEEDFACE
VERSIONS = range(31, 37)


class NavError(ValueError):
    """Not a navigation mesh this reader understands."""


@dataclass(frozen=True)
class Area:
    area_id: int
    corners: tuple[tuple[float, float, float], ...]

    @property
    def z(self) -> float:
        """Its mean height."""
        return sum(c[2] for c in self.corners) / len(self.corners)


class _Reader:
    def __init__(self, data: bytes) -> None:
        self.data, self.pos = data, 0

    def take(self, n: int) -> bytes:
        if self.pos + n > len(self.data):
            raise NavError(f"truncated at {self.pos}")
        chunk = self.data[self.pos : self.pos + n]
        self.pos += n
        return chunk

    def u8(self) -> int:
        return self.take(1)[0]

    def u32(self) -> int:
        return int(struct.unpack("<I", self.take(4))[0])

    def i32(self) -> int:
        return int(struct.unpack("<i", self.take(4))[0])

    def vec3(self) -> tuple[float, float, float]:
        x, y, z = struct.unpack("<3f", self.take(12))
        return float(x), float(y), float(z)

    def skip(self, n: int) -> None:
        self.take(n)

    def align8(self) -> None:
        self.skip((8 - self.pos % 8) % 8)

    def skip_cstring(self) -> None:
        while self.u8() != 0:
            pass


def read_nav(source: Path | bytes) -> list[Area]:
    """The areas of a `.nav` file (or its bytes)."""
    r = _Reader(source.read_bytes() if isinstance(source, Path) else source)
    if r.u32() != MAGIC:
        raise NavError("not a navigation mesh")
    version = r.u32()
    if version not in VERSIONS:
        raise NavError(f"unsupported version {version}")
    r.skip(4 + 4)  # sub-version, flags
    if version >= 36:
        _skip_kv3(r)
    polygons = _polygons(r, version)
    if version >= 32:
        r.skip(4)
    if version >= 35:
        for _ in range(r.u32()):  # named markers
            r.skip_cstring()
            r.skip(48)
    if version >= 36:
        _skip_kv3(r)
    return [_area(r, polygons) for _ in range(r.u32())]


def _polygons(r: _Reader, version: int) -> list[tuple[tuple[float, float, float], ...]]:
    corners = [r.vec3() for _ in range(r.u32())]
    polygons = []
    for _ in range(r.u32()):
        count = r.u8()
        polygon = []
        for _ in range(count):
            index = r.u32()
            if index >= len(corners):
                raise NavError(f"corner {index} out of range")
            polygon.append(corners[index])
        if version >= 35:
            r.skip(4)
        polygons.append(tuple(polygon))
    return polygons


def _area(r: _Reader, polygons: list[tuple[tuple[float, float, float], ...]]) -> Area:
    area_id = r.u32()
    r.skip(8 + 1)  # dynamic attribute flags, hull index
    index = r.u32()
    if index >= len(polygons):
        raise NavError(f"polygon {index} out of range")
    corners = polygons[index]
    r.skip(4)
    for _ in corners:  # connections, one list per edge
        r.skip(8 * r.u32())
    r.skip(5)  # legacy hiding spots and encounter paths (counts only)
    for _ in range(2):  # ladders above and below
        r.skip(4 * r.u32())
    return Area(area_id, corners)


def _skip_kv3(r: _Reader) -> None:
    """Steps over an embedded (empty) KV3 document, from its header's sizes."""
    r.align8()
    magic = r.u32()
    version = magic & 0xFF
    if magic & 0xFFFFFF00 != 0x4B563300 or not 2 <= version <= 5:
        raise NavError(f"unsupported KV3 block {magic:#010x}")
    r.skip(16)  # format GUID
    method = r.u32()
    r.skip(2 + 2 + 16 + 2 + 2)
    unc_total, cmp_total, blocks, blobs = r.i32(), r.i32(), r.i32(), r.i32()
    block_bytes = 0
    if version >= 4:
        r.skip(4)
        block_bytes = r.i32()
    if version >= 5:
        unc1, cmp1, unc2, cmp2 = r.i32(), r.i32(), r.i32(), r.i32()
        r.skip(32)
    else:
        unc1, cmp1, unc2, cmp2 = unc_total, cmp_total, 0, 0
    if method > 2 or blocks or blobs:
        raise NavError("KV3 block with data")
    size = (unc1 if method == 0 else cmp1) + (unc2 if method == 0 else cmp2) + block_bytes
    r.skip(size)
