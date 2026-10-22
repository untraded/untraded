# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Navigation meshes, packages and radars, on hand-made files (the game's own cannot ship)."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from untraded.maps import RADARS
from untraded.navmesh import NavError, read_nav
from untraded.radars import radar_svgs, write_radars
from untraded.vpk import VpkError, read_file

SQUARES = [
    # (area id, corners): a 512-unit square on Mirage's ground, and one 600 units up.
    (
        1,
        [
            (-3230.0, 1713.0, 0.0),
            (-2718.0, 1713.0, 0.0),
            (-2718.0, 1201.0, 0.0),
            (-3230.0, 1201.0, 0.0),
        ],
    ),
    (2, [(-2718.0, 1713.0, 600.0), (-2206.0, 1713.0, 600.0), (-2206.0, 1201.0, 600.0)]),
]


def kv3() -> bytes:
    """An empty KV3 document (version 4, uncompressed), as version 36 embeds."""
    return (
        struct.pack("<I", 0x4B563304)
        + bytes(16)
        + struct.pack("<I", 0)  # uncompressed
        + bytes(2 + 2 + 16 + 2 + 2)
        + struct.pack("<4i", 0, 0, 0, 0)
        + struct.pack("<2i", 0, 0)
    )


def nav(
    version: int = 36, areas: list[tuple[int, list[tuple[float, float, float]]]] = SQUARES
) -> bytes:
    out = bytearray(struct.pack("<4I", 0xFEEDFACE, version, 0, 1))

    def aligned_kv3() -> None:
        out.extend(bytes((8 - len(out) % 8) % 8))
        out.extend(kv3())

    if version >= 36:
        aligned_kv3()
    corners = [c for _, area in areas for c in area]
    out += struct.pack("<I", len(corners))
    for c in corners:
        out += struct.pack("<3f", *c)
    out += struct.pack("<I", len(areas))
    start = 0
    for _, area in areas:
        out += struct.pack("<B", len(area))
        out += b"".join(struct.pack("<I", start + i) for i in range(len(area)))
        start += len(area)
        if version >= 35:
            out += bytes(4)
    out += bytes(4)  # version 32+
    if version >= 35:
        out += struct.pack("<I", 0)  # no markers
    if version >= 36:
        aligned_kv3()
    out += struct.pack("<I", len(areas))
    for index, (area_id, area) in enumerate(areas):
        out += struct.pack("<IqBI", area_id, 0, 0, index)
        out += bytes(4)
        out += b"".join(struct.pack("<I", 0) for _ in area)  # no connections
        out += bytes(5)
        out += struct.pack("<2I", 0, 0)  # no ladders
    return bytes(out)


def vpk(files: dict[str, bytes]) -> bytes:
    """A single-file version 2 package holding `files` (path -> bytes)."""
    tree = bytearray()
    data = bytearray()
    for path, content in files.items():
        directory, _, name = path.rpartition("/")
        stem, _, ext = name.rpartition(".")
        tree += ext.encode() + b"\0" + directory.encode() + b"\0" + stem.encode() + b"\0"
        tree += struct.pack("<IHHIIH", 0, 0, 0x7FFF, len(data), len(content), 0xFFFF)
        tree += b"\0\0"  # end of the directory's names, end of the extension's directories
        data += content
    tree += b"\0"  # end of the extensions
    return struct.pack("<7I", 0x55AA1234, 2, len(tree), 0, 0, 0, 0) + bytes(tree) + bytes(data)


@pytest.mark.parametrize("version", [35, 36])
def test_a_navigation_mesh_gives_its_areas(version: int) -> None:
    areas = read_nav(nav(version))
    assert [a.area_id for a in areas] == [1, 2]
    assert areas[0].corners[0] == (-3230.0, 1713.0, 0.0)
    assert areas[1].z == 600.0


def test_other_files_are_refused() -> None:
    with pytest.raises(NavError, match="not a navigation mesh"):
        read_nav(b"\0" * 64)
    with pytest.raises(NavError, match="version"):
        read_nav(struct.pack("<4I", 0xFEEDFACE, 99, 0, 0))
    with pytest.raises(NavError, match="truncated"):
        read_nav(nav()[:60])


def test_a_package_gives_its_files(tmp_path: Path) -> None:
    package = tmp_path / "de_mirage.vpk"
    package.write_bytes(vpk({"maps/de_mirage.nav": nav(), "maps/other.txt": b"x"}))
    assert read_file(package, "maps/de_mirage.nav") == nav()
    assert read_file(package, "maps/other.txt") == b"x"
    with pytest.raises(VpkError, match=r"no maps/missing\.nav"):
        read_file(package, "maps/missing.nav")


def test_a_radar_draws_the_areas_in_the_radar_transform() -> None:
    [svg] = radar_svgs(read_nav(nav()), RADARS["de_mirage"]).values()
    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024"')
    # The ground square spans pixels 0 to 102.4 on Mirage (5 units per pixel).
    assert "M0,0L102.4,0L102.4,102.4L0,102.4Z" in svg
    assert svg.count("<path") == 2  # two height bands


def test_two_level_maps_get_two_radars(tmp_path: Path) -> None:
    deep = [(1, [(0.0, 0.0, -600.0), (100.0, 0.0, -600.0), (100.0, 100.0, -600.0)]), *SQUARES]
    assert set(radar_svgs(read_nav(nav(areas=deep)), RADARS["de_nuke"])) == {"upper", "lower"}
    navs = {"de_nuke": nav(areas=deep), "de_mirage": nav()}
    written = write_radars(navs.get, tmp_path)
    assert sorted(p.name for p in written) == ["de_mirage.svg", "de_nuke.svg", "de_nuke_lower.svg"]
