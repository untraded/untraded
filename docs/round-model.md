# Round model (derived tables)

*Version 1, 2026-10-17. Workstream E4. Implemented by `untraded.derive.derive()`.*

The round model is computed from the [canonical tables](canonical-tables.md) of one match, without the demo. It turns events into what the metrics of [metrics-v1](metrics-v1.md) count: who was alive, who opened the round, whose death was traded, who clutched, how each team bought.

**Facts, not thresholds.** Derived tables store what happened, measured: delays in seconds, distances in Hammer units. Adjustable thresholds (the 5 s trade window and its 3 s variant, the 1,000 u trade-opportunity distance, the isolation radius) are applied by the metrics, so changing a parameter never requires deriving again. Buy types are the exception, with their thresholds as explicit parameters (`BuyThresholds`).

## Tables

### `round_player` — one row per player and round played

A round is played when the player is on a team at freeze-time end (the `economy` rows, metrics-v1 § 0).

| Column | Type | Definition |
|---|---|---|
| `round`, `steamid`, `team`, `side` | | key; side at that round |
| `kills` | Int16 | enemy kills (team kills and suicides excluded) |
| `deaths` | Int16 | 0 or 1, any cause |
| `assists`, `flash_assists` | Int16 | enemy kills assisted, split by the `assistedflash` flag |
| `damage` | Int32 | capped damage dealt to enemies |
| `survived` | Boolean | alive at `round.end_tick` |
| `death_tick`, `death_trade_delay_s` | Int32?, Float32? | when the player died, and how long until the killer was killed by the player's team (null: never in that round) |
| `opening_kill`, `opening_death` | Boolean | the player made, or was the victim of, the round's opening kill |
| `setup_place` | String? | zone 20 s after freeze-time end (⚙ `setup.offset_s`), null if dead by then |
| `team_won` | Boolean | |

### `death` — one row per death (the `kill` table, in context)

| Column | Type | Definition |
|---|---|---|
| `tick`, `round`, `victim`, `victim_team`, `killer`, `killer_team` | | from `kill`; killer null for the bomb or the world |
| `victim_bot` | Boolean | the victim is a bot (`kill.victim_bot`): `victim` is then null, since the death is nobody's, and `victim_team` is the team of the bot (its controller's, or the killer's opposite). The kill still counts for the killer |
| `is_enemy_kill` | Boolean | killer on the other team |
| `is_opening` | Boolean | first enemy kill of the round after freeze-time end |
| `trade_delay_s`, `trader` | Float32?, UInt64? | the killer is then killed by the victim's team in the round, later or on the same tick (delay 0): after this delay, by this player. When the victim and the killer kill each other on the same tick, nobody is traded. **Traded** = delay ≤ W |
| `avenges_delay_s` | Float32? | this kill's victim had killed a teammate of the killer this long before (the latest such kill). **Trade kill** = delay ≤ W |
| `nearest_teammate_distance` | Float32? | distance from the victim to the nearest living teammate, at the death tick |

### `trade_opportunity` — one row per enemy kill and living teammate of the victim

`tick`, `round`, `victim`, `killer`, `teammate`, `distance_to_killer`. A teammate has a trade opportunity when that distance is within ⚙🎯 `trade.opportunity_distance` (1,000 u by default).

### `clutch` — one row per clutch

`round`, `steamid`, `team`, `side`, `enemies` (N), `start_tick`, `won`. Starting lineups are the players alive at freeze-time end. Deaths up to the round end are applied tick by tick, deaths on the same tick together; a team left with one player facing at least one enemy starts a clutch, at most once per team and round. When both teams are down to one player on the same tick, both players are in a 1v1.

### `team_round` — one row per team and round

`round`, `team`, `side`, `won`, `equip_value` (team average per player at freeze-time end + 7 s), `buy_type`:

| Type | Rule (metrics-v1 § 5) |
|---|---|
| `pistol` | first round of each regulation half (rounds 1 and 13 in MR12) |
| `eco` | ≤ $1,000 |
| `full` | ≥ $4,500 on CT, ≥ $4,000 on T |
| `force` | previous round lost, and neither eco nor full |
| `semi` | everything else |

## Invariants checked on creation

One `round_player` row per player and round; at most one death per player and round; at most 5 players per team and round; at most one opening per round; at most one clutch per team and round; one `team_round` row per team and round.
