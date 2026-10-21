<!--
SPDX-FileCopyrightText: 2026 The Untraded Authors
SPDX-License-Identifier: AGPL-3.0-only
-->

# Round replays (2D viewer)

A round as the 2D viewer replays it: one JSON document per round, built from the canonical
tables (`untraded.replay`, MIT) when a match is parsed, and kept gzipped next to its tables, at
`matches/{match_id}/replay/{round}.json.gz` (30 to 65 kB per round on a Premier match).

- **API**: `GET /matches/{match_id}/rounds/{round}/replay`, for a user who may see the match. Its
  answer is gzipped (`Content-Encoding: gzip`) and never changes (`Cache-Control: private`).
- **Matches parsed before** replays existed, or after a format change: `untraded-worker replays`
  (add `--force` to rewrite the existing ones).

## Format, version 1

| Key | Content |
|---|---|
| `version` | `1`; a change is a new version, and the replays are rewritten |
| `match_id`, `round`, `map`, `tickrate` | |
| `radar` | where world points fall on the map's 1024-pixel radar: `pos_x`, `pos_y`, `scale`, `lower_below` (world `z` under which a point is on the lower level, or null); null for a map without known values (`untraded.maps`) |
| `start_tick`, `freeze_end_tick`, `end_tick` | the round, its freeze time ending at `freeze_end_tick` |
| `winner_side`, `reason` | `CT` or `T`; `bomb_exploded`, `bomb_defused`, `elimination`, `time_ran_out`... |
| `ticks` | the shared timeline: every `player_tick` sample of the round (16 Hz, exact at kills and round boundaries) |
| `weapons` | weapon names, indexed by the players' `weapon` arrays |
| `players` | one per player: `steamid` (string), `name`, `team` (`A`/`B`), `side` (`CT`/`T`), and one array per state, aligned on `ticks`, `null` where the player has no sample |
| `kills` | `tick`, `attacker`, `victim`, `assister`, `weapon`, `headshot`, `wallbang`, `through_smoke`, `team_kill`, `attacker_x/y/z`, `victim_x/y/z` |
| `grenades` | `id`, `type` (`flash`, `he`, `smoke`, `molotov`, `incendiary`, `decoy`), `thrower`, `side`, `throw_tick`, `detonate_tick`, `end_tick` (smoke and fire), `detonate` (`[x, y, z]`), `path` (`ticks`, `x`, `y`, `z`) |
| `blinds` | `tick`, `victim`, `flasher`, `duration` (seconds) |
| `bomb` | `events` (`tick`, `type`: `plant_begin`, `planted`, `defuse_begin`, `defused`, `exploded`, `dropped`, `picked_up`; `player`, `site`) and `planted_at` (`[x, y, z]`: the planter's position when it was planted) |

Player states: `x`, `y`, `z` (world units, integers), `yaw` (whole degrees, 0 to 359), `hp`,
`armor`, `alive` (0 or 1), `flash` (seconds of blindness left, one decimal), `scoped`, `defusing`
(0 or 1), `weapon` (index into `weapons`).

SteamIDs are strings everywhere: they do not fit in a JavaScript number.

On the radar, a world point `(x, y)` falls at pixel `((x - pos_x) / scale, (pos_y - y) / scale)`.
Radar images are not part of this repository (see the maps' notes in `untraded.maps`).
