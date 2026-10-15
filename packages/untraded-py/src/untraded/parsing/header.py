# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Demo header: map and game build. It carries neither the tickrate nor the game mode (ADR 0008)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from demoparser2 import DemoParser

from untraded.demofile import plain_demo

# The header is the first message of the demo: the first MiB is enough to read it.
_HEADER_BYTES = 1 << 20


@dataclass(frozen=True)
class DemoHeader:
    map_name: str
    """E.g. `de_mirage`."""
    game_build: str
    """CS2 patch version, e.g. `14190`."""
    server_name: str
    """Free text set by the server; identifies some organizers, not reliable (S0.4)."""


def read_header(path: Path) -> DemoHeader:
    """Reads the header of a demo, plain or compressed, without decompressing it all."""
    with plain_demo(path, limit=_HEADER_BYTES) as dem:
        raw = DemoParser(str(dem)).parse_header()
    return DemoHeader(
        map_name=str(raw.get("map_name", "")),
        game_build=str(raw.get("patch_version", "")),
        server_name=str(raw.get("server_name", "")),
    )
