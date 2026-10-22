# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Round replays for the 2D viewer, built from the `premier-half` fixture, and map radars."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

import pytest

from untraded import fixtures
from untraded.maps import RADARS, Radar
from untraded.replay import REPLAY_VERSION, build_replays, to_json_gz

FIXTURE = Path(__file__).parent / "fixtures" / "premier-half"


@pytest.fixture(scope="module")
def replays() -> dict[int, dict[str, Any]]:
    return build_replays(fixtures.read(FIXTURE))


def test_one_replay_per_round_with_its_frame(replays: dict[int, dict[str, Any]]) -> None:
    assert sorted(replays) == [11, 12, 13, 14, 15]
    first = replays[11]
    assert first["version"] == REPLAY_VERSION
    assert first["round"] == 11
    assert first["start_tick"] <= first["freeze_end_tick"] <= first["end_tick"]
    assert first["ticks"] == sorted(first["ticks"])
    assert first["radar"] is None  # de_cache is not in the map pool


def test_every_player_state_is_aligned_on_the_timeline(
    replays: dict[int, dict[str, Any]],
) -> None:
    replay = replays[12]
    assert len(replay["players"]) == 10
    for player in replay["players"]:
        assert isinstance(player["steamid"], str)
        assert player["side"] in ("CT", "T")
        for key in ("x", "y", "z", "yaw", "hp", "armor", "alive", "flash", "weapon"):
            assert len(player[key]) == len(replay["ticks"]), key
        assert all(v is None or 0 <= v < 360 for v in player["yaw"])
        assert all(w is None or 0 <= w < len(replay["weapons"]) for w in player["weapon"])
    assert {p["side"] for p in replay["players"]} == {"CT", "T"}


def test_events_name_players_as_strings(replays: dict[int, dict[str, Any]]) -> None:
    for replay in replays.values():
        players = {p["steamid"] for p in replay["players"]}
        for kill in replay["kills"]:
            assert kill["victim"] in players
            assert kill["attacker"] is None or isinstance(kill["attacker"], str)
        for grenade in replay["grenades"]:
            assert grenade["thrower"] in players
            assert len(grenade["path"]["ticks"]) == len(grenade["path"]["x"])


def test_the_planted_bomb_has_a_position(replays: dict[int, dict[str, Any]]) -> None:
    planted = [
        r for r in replays.values() if any(e["type"] == "planted" for e in r["bomb"]["events"])
    ]
    assert planted
    assert all(r["bomb"]["planted_at"] is not None for r in planted)


def test_a_replay_is_small_once_gzipped(replays: dict[int, dict[str, Any]]) -> None:
    for replay in replays.values():
        packed = to_json_gz(replay)
        assert len(packed) < 120_000
        assert json.loads(gzip.decompress(packed)) == replay
    assert to_json_gz(replays[11]) == to_json_gz(replays[11])  # reproducible


def test_radars_map_world_points_to_pixels() -> None:
    mirage = RADARS["de_mirage"]
    assert mirage.pixel(-3230, 1713) == (0, 0)
    assert mirage.pixel(-3230 + 5.0 * 512, 1713 - 5.0 * 512) == (512, 512)
    assert RADARS["de_nuke"].level(-600) == "lower"
    assert RADARS["de_nuke"].level(0) == "upper"
    assert Radar(0, 0, 1).level(-10_000) == "upper"
    assert {"de_mirage", "de_inferno", "de_nuke", "de_ancient", "de_anubis", "de_dust2"} <= set(
        RADARS
    )
