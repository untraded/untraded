# Canonical tables v1 (specification)

*Version 1, accepted 2026-10-15. The parsing adapter (workstream E3) implements all 13 tables (`untraded.parsing.parse_demo`, `untraded parse`). A 30-round Premier match takes about 34 s and 1.4 GB of memory at peak on a desktop x86 CPU (bz2 decompression and hashing included), and 6.1 MB of Parquet, 5.9 MB of it `player_tick`.*

The canonical tables are what the parsing adapter produces from a demo (ADR 0002), what metrics read, and the **long-term record** of a match: metrics are recomputed from them, and the raw demo may be deleted after parsing (ADR 0009). Anything left out here is lost for every match whose demo is gone. Each column is therefore listed with **its source** and **why it is kept**.

Sources were checked on Premier, FACEIT, LAN and online tournament demos (spikes S0.2 and S0.4). Rounds come from game state, events are optional (ADR 0008).

## 1. Conventions

| Topic | Rule |
|---|---|
| Storage | One Parquet file per table and match, `matches/{match_id}/{table}.parquet`, zstd. Polars schemas are strict and validated on creation. |
| Identifiers | `match_id` = sha256 of the decompressed demo (one map = one demo = one match). Players are `steamid` (UInt64). Names live only in `player`. |
| Ticks | `tick` is Int32, as in the demo. Durations are converted with the match `tickrate`, never assumed (ADR 0008). |
| Rounds | `round` is the 1-based round number from game state (`total_rounds_played + 1`). Rows outside a live round (warmup, pre-match) are dropped. |
| Sides and teams | `side` is `CT` or `T` at that moment. `team` is `A` (started the match on CT) or `B`: stable across the half-time and overtime side switches. |
| Positions | `x`, `y`, `z` in Hammer units, Float32. `place` is the engine navmesh place name (`last_place_name`). |
| Missing data | A table whose source is missing in a demo is rebuilt by its documented fallback, or is empty with the reason recorded in `match.unavailable`. It is never silently empty. |
| Versioning | `match.schema_version` records the version of this spec. Adding a column is a minor bump, changing or removing one a major bump with a migration (ADR 0009). |

## 2. Tables

### `match` — one row

| Column | Type | Source | Why |
|---|---|---|---|
| `match_id` | String | sha256 of the decompressed demo | identity, deduplication |
| `schema_version` | String | this spec | recomputation (ADR 0003, 0009) |
| `parser`, `parser_version` | String | adapter | traceability |
| `source`, `mode`, `played_at` | String, String, Date? | **ingestion input** (the demo carries none of them) | splits, filtering (ADR 0008) |
| `map`, `game_build`, `server_name` | String | header | splits, patch analysis |
| `tickrate` | Float32 | computed: ticks ÷ elapsed `game_time` | every duration |
| `ticks` | Int32 | last tick | |
| `rounds_played`, `score_a`, `score_b` | Int16 | game state at the last tick | validation, win rates |
| `team_a_name`, `team_b_name` | String? | `team_clan_name` (empty on online servers) | display |
| `first_round` | Int16 | first live round | **`incomplete_start`** when > 1 (ADR 0008) |
| `events_available` | List[String] | `list_game_events()` | which fallbacks were used |
| `unavailable` | List[String] | adapter | tables or columns that could not be built, with the reason |

### `player` — one row per player

| Column | Type | Source | Why |
|---|---|---|---|
| `steamid` | UInt64 | `parse_player_info` | identity |
| `name` | String | `parse_player_info` | display (personal data: replaced in fixtures, ADR 0010) |
| `team` | Enum A/B | side at the first live round | stable team |
| `rank`, `comp_wins` | Int32? | props `rank`, `comp_wins` at the first live round | **rank-based references later** (vision § 8); tiny |
| `rounds_on_team` | Int16 | rounds where the player was on a team at freeze end | "rounds played" (metrics-v1 § 0) |

### `round` — one row per live round

| Column | Type | Source | Why |
|---|---|---|---|
| `round` | Int16 | `total_rounds_played + 1` | key |
| `start_tick` | Int32 | `is_freeze_period` turning true | economy, round timeline |
| `freeze_end_tick` | Int32 | `is_freeze_period` turning false (cross-checked with `round_freeze_end`) | openings, setups, "rounds played" |
| `end_tick` | Int32 | `total_rounds_played` incrementing | survival, clutches, trade windows |
| `official_end_tick` | Int32? | `round_officially_ended` when present | — |
| `winner_side`, `winner_team` | Enum | `round_win_status` | win rates, conversion, clutches |
| `reason` | Enum | `round_win_reason` mapped: `bomb_exploded`, `bomb_defused`, `elimination`, `time_ran_out`, `surrender`, `other` | post-plant and retake stats |
| `ct_team`, `t_team` | Enum A/B | `team_num` at freeze end | sides per round |
| `score_a`, `score_b` | Int16 | `team_rounds_total` after the round | match state |
| `is_overtime` | Boolean | round number vs. regulation length | pistol rounds, splits |
| `bomb_planted_tick`, `bomb_site`, `bomb_planter` | Int32?, Enum A/B?, UInt64? | `bomb_planted`; the site from the planter's `last_place_name` (`BombsiteA`/`BombsiteB`), since the event only carries an entity id | post-plant, retakes |
| `bomb_defused_tick`, `bomb_defuser` | Int32?, UInt64? | `bomb_defused` | |
| `bomb_exploded_tick` | Int32? | `bomb_exploded` | |

### `kill` — one row per `player_death`

| Column | Type | Source | Why |
|---|---|---|---|
| `tick`, `round` | Int32, Int16 | event | key |
| `attacker`, `victim`, `assister` | UInt64? | event (attacker null for world, bomb, fall) | base, duels, trades |
| `flash_assist` | Boolean | `assistedflash` (credited to `assister`) | `base.flash_assists`, KAST |
| `weapon` | String | event | splits, `eco.kills_vs_buy` |
| `headshot`, `wallbang`, `noscope`, `through_smoke`, `attacker_blind`, `attacker_in_air` | Boolean | event (`penetrated` > 0 for wallbang) | HS %, display, later metrics |
| `hitgroup`, `distance` | Int8?, Float32 | event; `hitgroup` is the engine code (0 generic, 1 head, 2 chest, 3 stomach, 4-5 arms, 6-7 legs, 8 neck, 10 gear), null when none (world, bomb) | display, later metrics |
| `attacker_side`, `victim_side` | Enum | `team_num` at the tick | splits; team kills |
| `is_team_kill`, `is_suicide` | Boolean | derived | `base.team_kills`, `base.suicides` |
| `victim_bot` | Boolean | the victim is a bot (see below) | kills of bots count, their deaths do not |
| `attacker_x/y/z`, `victim_x/y/z` | Float32 | props at the tick | kill and death zones, heatmaps, trade opportunities |
| `attacker_place`, `victim_place` | String | `last_place_name` at the tick | `pos.*` |
| `attacker_equip_value`, `victim_equip_value` | Int32 | `current_equip_value` at the tick | `eco.equipment_lost_at_death`, `eco.kills_vs_buy` |
| `victim_inventory` | List[String] | `inventory` at the tick | `util.unused_value_at_death` |
| `victim_flash_duration` | Float32 | `flash_duration` at the tick | `util.flash_to_kill` |

**Bots** (`victim_bot`, Boolean): after a disconnection, a bot replaces the player. A kill of a bot counts for the killer, but the death is nobody's, and `match.unavailable` counts these kills.
- A bot nobody controls has no steamid, name or side in the event: `victim` is null, and `victim_side` is the killer's opposite (a team kill on such a bot cannot be told apart).
- A dead teammate can take the bot over: the bot's kills are credited to that teammate, as on the in-game scoreboard, and the bot's death shows as a second death of the teammate in the round. `victim` keeps the teammate's steamid, flagged `victim_bot`.

**Disconnections**: the game records a `world` suicide at the tick a player disconnects (their `player_disconnect`). Leaving is not a death: these rows are dropped and counted in `match.unavailable`. Seen in 4 of 18 matchmaking demos, 3 of them after the last round's end.

### `damage` — one row per `player_hurt`

| Column | Type | Source | Why |
|---|---|---|---|
| `tick`, `round` | Int32, Int16 | event | key |
| `attacker`, `victim` | UInt64? | event | ADR, utility damage |
| `weapon`, `hitgroup` | String, Int8 | event | HE and fire damage, later aim metrics |
| `dmg_health`, `dmg_armor` | Int16 | event (raw) | |
| `health_after`, `armor_after` | Int16 | event | |
| `damage` | Int16 | **capped**: the health the hit removed, `health before − health_after`. The health before is the `health_after` of the previous hit on that victim in the round, or 100: health only goes down within a round, and the `health` prop at the event tick is already updated for about a third of the hits. `dmg_health` is rounded down, so health often drops by one more point than it says; CS Demo Manager also counts the health lost. Without `health_after`: `min(dmg_health, health before)` | ADR (metrics-v1 § 0) |
| `is_team_damage` | Boolean | sides at the tick | team damage |
| `grenade_id` | Int32? | the attacker's grenade of the damage's kind (HE, fire, impact) whose throw-to-end window (+1 s) holds the hit | fire ownership check (demoparser2 #317) |

### `shot` — one row per `weapon_fire`

| Column | Type | Source | Why |
|---|---|---|---|
| `tick`, `round`, `shooter`, `weapon`, `silenced` | | event (`weapon` without its `weapon_` prefix; grenade throws and knife swings included) | shot counts |
| `x/y/z`, `pitch`, `yaw`, `velocity_x/y/z` | Float32 | props at the tick | **aim and movement metrics later** (not in v1): lost if not kept |
| `is_scoped`, `ducking`, `is_airborne`, `is_walking`, `accuracy_penalty` | | props at the tick | same |

### `grenade` — one row per grenade thrown

| Column | Type | Source | Why |
|---|---|---|---|
| `grenade_id` | Int32 | sequential within the match by throw tick; one throw is a run of consecutive ticks of a projectile entity (entity ids are reused) | key |
| `entity_id`, `round`, `thrower`, `side` | | `parse_grenades` | |
| `type` | Enum: `flash`, `he`, `smoke`, `molotov`, `incendiary`, `decoy` | projectile class from `parse_grenades`; molotov vs. incendiary from the thrower's `weapon_fire` | `util.thrown_*` |
| `throw_tick`, `throw_x/y/z` | | first trajectory point | lineups, display |
| `detonate_tick`, `detonate_x/y/z` | | detonate event of the projectile's entity (`decoy_started` for decoys); for fire, `inferno_startburn` one tick after the projectile ends, from the same thrower (the fire has its own entity id); last trajectory point as fallback | utility metrics |
| `end_tick` | Int32? | `smokegrenade_expired`, `inferno_expire` | smoke and fire timelines |

### `grenade_path` — grenade trajectories at 16 Hz *(see § 4)*

`grenade_id`, `tick`, `x`, `y`, `z`. For the 2D viewer and lineups. The projectile's flight from the throw to the detonation, at 16 Hz plus its last point: about 17,000 rows and 0.2 MB of Parquet for a 30-round Premier match (the projectile entity stays still for seconds after detonating, and grenades held in hand have no position: neither is kept).

### `blind` — one row per player blinded

| Column | Type | Source | Why |
|---|---|---|---|
| `tick`, `round`, `victim`, `flasher`, `grenade_id` | | `player_blind`; **fallback**: rises of `flash_duration` at the `flashbang_detonate` tick, attributed to its thrower (ADR 0008). On a matchmaking demo with both, the fallback finds 156 of 161 blinds with the same tick, duration and flasher, and no false positive (the missed ones were already blinded). `grenade_id` is the flasher's flash detonating on that tick | `util.enemies_flashed`, blind time |
| `duration` | Float32 (s) | `blind_duration`, or `flash_duration` | |
| `is_teammate`, `is_self` | Boolean | sides at the tick | team and self flashes |
| `from_fallback` | Boolean | adapter | traceability |

### `bomb` — one row per bomb event

`tick`, `round`, `type` (`plant_begin`, `planted`, `defuse_begin`, `defused`, `exploded`, `dropped`, `picked_up`), `player`, `site`. From the bomb events, when present. `site` comes from the player's place for plant events, and from the round's plant for defuses and explosions. Kept for post-plant and retake analysis (team phase).

### `economy` — one row per player and round

| Column | Type | Source | Why |
|---|---|---|---|
| `round`, `steamid`, `side` | | | key |
| `money_start` | Int32 | `balance` at `start_tick` | buy decisions |
| `spent` | Int32 | `cash_spent_this_round` at freeze end + 7 s | |
| `equip_value` | Int32 | `current_equip_value` at freeze end + 7 s (metrics-v1 § 5) | `eco.buy_type` |
| `round_start_equip_value` | Int32 | prop | saved equipment |
| `armor`, `has_helmet`, `has_defuser` | | props at freeze end + 7 s | buy type details |
| `inventory` | List[String] | `inventory` at freeze end + 7 s | primary weapon class, utility bought |

### `inventory_change` — one row each time a player's inventory changes

`tick`, `round`, `steamid`, `inventory` (List[String]). Purchases, drops and pickups are derived from consecutive rows (ADR 0008: no purchase event). Storing changes instead of the inventory at every tick keeps `player_tick` small. Changes are detected on the `player_tick` samples (16 Hz): a change undone within one interval (62 ms) is not seen. There were 4 such changes of 2,363 on a 30-round match, while reading the inventory at every tick doubled the peak memory of a parse (about 2 GB).

### `player_tick` — player state, sampled

Rows at **16 Hz** (one tick in four at 64 ticks/s, ⚙ adapter parameter) within each round, from `start_tick` to `end_tick`, **plus every kill tick and every round's `freeze_end_tick` and `end_tick`**, so that kill-time and round-boundary states are exact. Only players on a team are kept. About 500,000 rows for a 30-round match.

| Column | Type | Source | Why |
|---|---|---|---|
| `tick`, `round`, `steamid`, `side` | | | key |
| `x`, `y`, `z`, `pitch`, `yaw` | Float32 | props | positioning, spacing, setups, 2D viewer |
| `velocity_x`, `velocity_y`, `velocity_z` | Float32 | props | movement (later), viewer |
| `health`, `armor`, `has_helmet`, `is_alive` | | props | survival, clutches, capped damage |
| `place` | String (dictionary-encoded) | `last_place_name` | `pos.setup_zone_t20`, zones |
| `active_weapon` | String | `active_weapon_name` | viewer, later metrics |
| `balance`, `equip_value` | Int32 | `balance`, `current_equip_value` | economy timeline |
| `flash_duration` | Float32 | prop | blind state |
| `is_scoped`, `ducking`, `is_airborne`, `is_walking`, `is_defusing`, `has_defuser` | Boolean | props | viewer, later metrics |
| `spotted` | Boolean | prop | v1 visibility proxy (vision § 15) |
| `spotted_by` | List[UInt64] | `approximate_spotted_by` | who sees whom: later metrics |

## 3. Coverage of the v1 metric catalog

| Metrics (metrics-v1) | Tables used |
|---|---|
| § 1 Base (K, D, A, flash assists, ADR, HS %, KAST, multi-kills, survival) | `kill`, `damage`, `round`, `player`, `player_tick` (alive at `end_tick`) |
| § 2 Openings, trades, trade opportunities, isolated deaths, spacing | `kill`, `player_tick` at kill ticks (living teammates and their positions) |
| § 2 Clutches | `kill`, `player_tick` at kill ticks, `round.winner_team` |
| § 3 Death and kill zones, heatmaps | `kill` positions and places |
| § 3 Position at T+20 s, predictability, recurring death spot | `player_tick` (nearest sample after `freeze_end_tick` + 20 s), `kill` |
| § 4 Utility thrown, flashes, blind time, decisive flashes | `grenade`, `blind`, `kill.victim_flash_duration` |
| § 4 HE and fire damage | `damage` (+ `grenade_id` for fire ownership) |
| § 4 Wasted utility | `kill.victim_inventory` |
| § 5 Buy types, win rate by economy, equipment lost, kills by economy | `economy`, `round`, `kill` equipment values and weapons |
| § 6 HLTV 1.0, 2.0 (approx.) | from the base metrics |

Every v1 metric is computable from these tables alone: no metric needs the raw demo.

## 4. Choices beyond v1

Kept although no v1 metric needs them, because a deleted demo cannot be re-parsed (confirmed 2026-10-15):

1. **`shot` context** (position, angles, velocity, stance, accuracy penalty at each shot): aim and movement metrics in later phases. Cost: one extra tick parse at about 4,000 shot ticks per match.
2. **`grenade_path` at 16 Hz**: 2D viewer and lineups (team phase). Cost: roughly +1 to 2 MB of Parquet per match.
3. **`player.rank`**: rank-based references later. Negligible.
4. **`player_tick.spotted_by`**: visibility analysis later. Moderate (a list per row).

Left out on purpose:

- **usercmd** (raw inputs, sub-tick view angles, mouse deltas): heavy, and mainly useful for aim forensics, close to cheat detection, which is out of scope.
- **`ping`**: session hygiene is out of scope.
- **`crosshair_code`, chat messages, footsteps, reloads, weapon zoom events**: no planned use, or personal data.
- **Full-rate (64 Hz) player state**: 4 times the size, and no planned metric needs it (ADR 0009). The adapter can still produce it on demand for analysis.

## 5. Validation on creation

- Schemas and types are strict; ticks increase within each table.
- Live freeze ends = rounds played = `score_a + score_b`, unless `incomplete_start` (ADR 0008).
- Every event row has a round, or is dropped as warmup or pre-match.
- Each player has at most one row per sampled tick; at most 5 players per side are alive.
- Capped damage is between 0 and 100, and never exceeds `dmg_health` + 1.
