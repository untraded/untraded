# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Where a map's world coordinates fall on its radar (the 2D viewer's background).

A radar is a 1024 x 1024 image of the map seen from above. A world point `(x, y)` falls at pixel
`((x - pos_x) / scale, (pos_y - y) / scale)`. On maps with two levels, points below `lower_below`
(world `z`) are drawn on the lower level's radar, which uses the same transform.

These numbers come from each map's overview file in the game (`pos_x`, `pos_y`, `scale`,
`verticalsections`), as published in awpy-data's `map_data.json` (release 2000934, CS2 build of
2026-10-21). They are technical facts about the maps, not images: no radar image ships here.
"""

from __future__ import annotations

from dataclasses import dataclass

RADAR_PIXELS = 1024


@dataclass(frozen=True)
class Radar:
    pos_x: float
    pos_y: float
    scale: float
    lower_below: float | None = None
    """World `z` under which a point is on the lower level; None for one-level maps."""

    def pixel(self, x: float, y: float) -> tuple[float, float]:
        """Where the world point falls on the radar, in pixels from its top-left corner."""
        return (x - self.pos_x) / self.scale, (self.pos_y - y) / self.scale

    def level(self, z: float) -> str:
        """`lower` or `upper`: the radar to draw the point on."""
        return "lower" if self.lower_below is not None and z < self.lower_below else "upper"


RADARS: dict[str, Radar] = {
    "de_mirage": Radar(-3230, 1713, 5.0),
    "de_inferno": Radar(-2087, 3870, 4.9),
    "de_nuke": Radar(-3453, 2887, 7.0, lower_below=-495),
    "de_ancient": Radar(-2953, 2164, 5.0),
    "de_anubis": Radar(-2796, 3328, 5.22),
    "de_dust2": Radar(-2476, 3239, 4.4),
    "de_train": Radar(-2308, 2078, 4.082077, lower_below=-50),
    "de_overpass": Radar(-4831, 1781, 5.2),
    "de_vertigo": Radar(-3168, 1762, 4.0, lower_below=11700),
}
