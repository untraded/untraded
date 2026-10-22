# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Our own radars for the 2D viewer, drawn from each map's navigation mesh.

A radar is an SVG of 1024 x 1024 pixels, in the map's radar transform (`untraded.maps`): the
walkable areas, white on a transparent background, more opaque the higher they are (four height
bands), so the viewer can tint them for a light or a dark theme. Maps with two levels get two
radars, `{map}.svg` and `{map}_lower.svg`, split at `Radar.lower_below`.

`untraded radars OUT_DIR --cs2 GAME_DIR` writes them from a CS2 installation (each map's
navigation mesh is in `game/csgo/maps/{map}.vpk`); `--navs DIR` reads `.nav` files instead.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from untraded.maps import RADAR_PIXELS, RADARS, Radar
from untraded.navmesh import Area, read_nav
from untraded.vpk import read_file

BANDS = (0.16, 0.22, 0.28, 0.34)
"""Fill opacity of each height band, lowest first."""


def radar_svgs(areas: Sequence[Area], radar: Radar, name: str = "map") -> dict[str, str]:
    """The map's radars, by level (`upper`, and `lower` for two-level maps)."""
    if radar.lower_below is None:
        return {"upper": _svg(areas, radar, name)}
    return {
        level: _svg(
            [a for a in areas if radar.level(a.z) == level],
            radar,
            name if level == "upper" else f"{name}, lower level",
        )
        for level in ("upper", "lower")
    }


def game_nav(cs2_dir: Path, name: str) -> bytes | None:
    """A map's navigation mesh in a CS2 installation, or None if the map is not installed."""
    package = cs2_dir / "game" / "csgo" / "maps" / f"{name}.vpk"
    return read_file(package, f"maps/{name}.nav") if package.is_file() else None


def nav_file(nav_dir: Path, name: str) -> bytes | None:
    """A map's navigation mesh in a directory of `.nav` files, or None."""
    source = nav_dir / f"{name}.nav"
    return source.read_bytes() if source.is_file() else None


def write_radars(
    navs: Callable[[str], bytes | None], out_dir: Path, maps: Sequence[str] | None = None
) -> list[Path]:
    """Writes the radars of `maps` (default: every map with a radar transform) whose navigation
    mesh `navs` finds; returns the files written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name in maps or sorted(RADARS):
        nav = navs(name)
        if nav is None:
            continue
        for level, svg in radar_svgs(read_nav(nav), RADARS[name], name).items():
            target = out_dir / (f"{name}.svg" if level == "upper" else f"{name}_lower.svg")
            target.write_text(svg, encoding="utf-8", newline="\n")
            written.append(target)
    return written


def _svg(areas: Sequence[Area], radar: Radar, title: str) -> str:
    heights = sorted(a.z for a in areas)
    cuts = (
        [heights[len(heights) * i // len(BANDS)] for i in range(1, len(BANDS))] if heights else []
    )
    paths: list[list[str]] = [[] for _ in BANDS]
    for area in areas:
        band = sum(area.z >= cut for cut in cuts)
        points = [radar.pixel(x, y) for x, y, _ in area.corners]
        paths[band].append("M" + "L".join(f"{_n(px)},{_n(py)}" for px, py in points) + "Z")
    groups = "".join(
        f'<path fill="#fff" fill-opacity="{opacity}" d="{"".join(d)}"/>'
        for opacity, d in zip(BANDS, paths, strict=True)
        if d
    )
    size = RADAR_PIXELS
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 {size} {size}"><title>Radar of {title}, drawn from its navigation '
        f"mesh. The Untraded Authors, CC BY 4.0</title>{groups}</svg>\n"
    )


def _n(value: float) -> str:
    """A pixel coordinate, to the tenth: well under a world unit on every map."""
    text = f"{value:.1f}"
    return text[:-2] if text.endswith(".0") else text
