# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Reads a file out of a Valve package (`.vpk`, version 2), such as a map's navigation mesh in
`game/csgo/maps/de_mirage.vpk` of a CS2 installation.

Only single-file packages whose entries live in the package itself are read (the maps' packages
are); the split `pak01_*.vpk` archives are not.
"""

from __future__ import annotations

import struct
from pathlib import Path

SIGNATURE = 0x55AA1234
EMBEDDED = 0x7FFF
"""Archive index of an entry stored in the package file itself."""


class VpkError(ValueError):
    """Not a package this reader understands, or no such file in it."""


def read_file(package: Path, name: str) -> bytes:
    """The bytes of `name` (e.g. `maps/de_mirage.nav`) in `package`."""
    data = package.read_bytes()
    signature, version, tree_size = struct.unpack_from("<3I", data, 0)
    if signature != SIGNATURE or version != 2:
        raise VpkError(f"{package.name}: not a version 2 package")
    header = 28
    wanted_dir, _, wanted_file = name.rpartition("/")
    wanted_stem, _, wanted_ext = wanted_file.rpartition(".")
    pos = header
    end = header + tree_size

    def cstring() -> str:
        nonlocal pos
        stop = data.index(b"\0", pos)
        text = data[pos:stop].decode("utf-8", "replace")
        pos = stop + 1
        return text

    while pos < end:
        ext = cstring()
        if not ext:
            break
        while True:
            directory = cstring()
            if not directory:
                break
            while True:
                stem = cstring()
                if not stem:
                    break
                _, preload, archive, offset, length, terminator = struct.unpack_from(
                    "<IHHIIH", data, pos
                )
                pos += 18
                preloaded = data[pos : pos + preload]
                pos += preload
                if terminator != 0xFFFF:
                    raise VpkError(f"{package.name}: malformed entry {directory}/{stem}.{ext}")
                path_dir = "" if directory == " " else directory
                if (path_dir, stem, ext) == (wanted_dir, wanted_stem, wanted_ext):
                    if archive != EMBEDDED:
                        raise VpkError(f"{name} is in a split archive, which is not read")
                    start = end + offset
                    return preloaded + data[start : start + length]
    raise VpkError(f"{package.name}: no {name}")
