<!--
SPDX-FileCopyrightText: 2026 The Untraded Authors
SPDX-License-Identifier: AGPL-3.0-only
-->

# Round replays (2D viewer)

A round as the 2D viewer replays it: one JSON document per round, built from the canonical
tables and the derived `swing` table (`untraded.replay`, MIT) when a match is parsed, and kept
gzipped next to its tables, at `matches/{id}/replay/{round}.json.gz`, where `id` is the match's
database id (`match.parquet_prefix`) (30 to 65 kB per round on a Premier match).

- **API**: `GET /matches/{id}/rounds/{round}/replay` (`/api/matches/...` through the site) (`id`: the match's database id, a UUID), for
  a user who may see the match; a 404 otherwise, or when the round has no replay. Its answer is
  the stored file as is, gzipped (`Content-Encoding: gzip`), and never changes
  (`Cache-Control: private, max-age=86400`).
  The viewer asks for its format version (`?v=2`), so the browser keeps one copy per version: a
  replay written in another version is a 404 that is not cached (`no-store`), until
  `untraded-worker replays --force` rewrites it.
- **Matches parsed before** replays existed, or after a format change: `untraded-worker replays`
  (add `--force` to rewrite the existing ones). The swings come from the match's stored `swing`
  table, else are computed with the published model; matches derived before that table existed
  get it with `untraded-worker swings` (`--force` after a new model).

## Format, version 2

| Key | Content |
|---|---|
| `version` | `2`; a change is a new version, and the replays are rewritten |
| `match_id`, `round`, `map`, `tickrate` | `match_id` is the canonical one (sha256 of the demo), not the database id |
| `radar` | where world points fall on the map's 1024-pixel radar: `pos_x`, `pos_y`, `scale`, `lower_below` (world `z` under which a point is on the lower level, or null); null for a map without known values (`untraded.maps`) |
| `start_tick`, `freeze_end_tick`, `end_tick` | the round, its freeze time ending at `freeze_end_tick` |
| `winner_side`, `reason` | `CT`, `T` or null; `round.reason` (`bomb_exploded`, `bomb_defused`, `elimination`, `time_ran_out`, `surrender`, `other`) |
| `ticks` | the shared timeline: every `player_tick` sample of the round (16 Hz, exact at kills and round boundaries) |
| `weapons` | weapon names, indexed by the players' `weapon` arrays |
| `players` | one per player with a sample in the round, by SteamID: `steamid` (string), `name` (the SteamID when unknown), `team` (`A`/`B`), `side` (`CT`/`T` in that round), and one array per state, aligned on `ticks`, `null` where the player has no sample |
| `kills` | `tick`, `attacker`, `victim`, `assister`, `weapon`, `headshot`, `wallbang`, `through_smoke`, `team_kill`, `attacker_x/y/z`, `victim_x/y/z` (integers) |
| `grenades` | `id`, `type` (`flash`, `he`, `smoke`, `molotov`, `incendiary`, `decoy`), `thrower`, `side`, `throw_tick`, `detonate_tick`, `end_tick` (smoke and fire), `detonate` (`[x, y, z]`), `path` (`ticks`, `x`, `y`, `z`) |
| `blinds` | `tick`, `victim`, `flasher`, `duration` (seconds, one decimal) |
| `bomb` | `events` (`tick`, `type`: `plant_begin`, `planted`, `defuse_begin`, `defused`, `exploded`, `dropped`, `picked_up`; `player`, `site`) and `planted_at` (`[x, y, z]`: the planter's position when it was planted) |
| `winprob` | the counter-terrorists' chance of winning the round over time ([winprob](winprob.md)): `model` (its version), `ticks` and `p_ct` (0 to 1, three decimals), and `swings` (the round's rows of the derived [`swing`](round-model.md) table: `tick`, `event`: `kill`, `plant` or `defuse`; `player`, `side`, `swing`: from -1 to 1, seen by the player's side, three decimals). The curve has a point per second of play, two points on the tick of each event (before and after, so it steps at once), and ends on the result, 1 or 0, when the round is decided. Null for a round the model does not cover (no winner, or an end such as a surrender) |

Version 2 (2026-10-26) adds `winprob`; version 1 had everything else.

Player states: `x`, `y`, `z` (world units, integers), `yaw` (whole degrees, 0 to 359), `hp`,
`armor`, `alive` (0 or 1), `flash` (seconds of blindness left, one decimal), `scoped`, `defusing`
(0 or 1), `weapon` (index into `weapons`).

SteamIDs are strings everywhere: they do not fit in a JavaScript number.

On the radar, a world point `(x, y)` falls at pixel `((x - pos_x) / scale, (pos_y - y) / scale)`.

## Radars

The viewer's backgrounds are our own radars, in `apps/web/public/radars/` (served at
`/radars/{map}.svg`, and `/radars/{map}_lower.svg` for the lower level of Nuke, Train and
Vertigo). They are licensed CC BY 4.0, credit "The Untraded Authors". The browser keeps them a
day, then uses its copy for up to a week while it checks for a new one: a redrawn radar can take
that long to reach a returning viewer.

- **What they are**: SVGs of 1024 x 1024 pixels in the radar transform above. The walkable areas
  of the map's navigation mesh are drawn white on a transparent background, more opaque the
  higher they are (four height bands), so a light or a dark theme can tint them.
- **What they are not**: Valve's radar images. Those are not in this repository.
- **Redrawing them**, after a map update, from a CS2 installation (`untraded.vpk` reads each map's
  navigation mesh out of `game/csgo/maps/{map}.vpk`):

  ```bash
  uv run untraded radars apps/web/public/radars --cs2 "C:/Program Files (x86)/Steam/steamapps/common/Counter-Strike Global Offensive"
  ```

  `--navs DIR` reads `.nav` files instead, and `--map NAME` limits it to one map.
