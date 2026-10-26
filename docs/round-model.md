# Round model (derived tables)

*Version 1, 2026-10-17; the `swing` table was added on 2026-10-26. Workstream E4. Implemented by `untraded.derive.derive()`, with strict schemas in `untraded.derive.schema.TABLES`. The worker stores the derived tables next to the canonical ones, one Parquet file each.*

The round model is computed from the [canonical tables](canonical-tables.md) of one match, without the demo. It turns events into what the metrics of [metrics-v1](metrics-v1.md) count: who was alive, who opened the round, whose death was traded, who clutched, how each team bought.

**Facts, not thresholds.** Derived tables store what happened, measured: delays in seconds, distances in Hammer units. Adjustable thresholds (the 5 s trade window and its 3 s variant, the 1,300 u trade-opportunity distance, the 1,000 u isolation radius) are applied by the metrics, so changing a parameter never requires deriving again. Buy types are the exception, with their thresholds as explicit parameters (`derive(..., buy_thresholds=BuyThresholds())`). The `swing` table depends on the win-probability model (`derive(..., winprob=...)`, the published one by default).

## Tables

### `round_player` — one row per player and round played

A round is played when the player is on a team at freeze-time end (the `economy` rows, metrics-v1 § 0).

| Column | Type | Definition |
|---|---|---|
| `round`, `steamid`, `team`, `side` | Int16, UInt64, Enum A/B, Enum CT/T | key; side at that round |
| `kills` | Int16 | enemy kills (team kills and suicides excluded) |
| `deaths` | Int16 | 0 or 1, any cause |
| `assists`, `flash_assists` | Int16 | enemy kills assisted, split by the `assistedflash` flag |
| `damage` | Int32 | capped damage dealt to enemies |
| `survived` | Boolean | alive at `round.end_tick` and no death in the round, including after its end: an exit frag drops the weapons |
| `death_tick`, `death_trade_delay_s` | Int32?, Float32? | when the player died, and how long until the killer was killed by the player's team (null: never in that round) |
| `opening_kill`, `opening_death` | Boolean | the player made, or was the victim of, the round's opening kill |
| `setup_place` | String? | zone 20 s after freeze-time end (⚙ `setup.offset_s`), null if dead by then |
| `team_won` | Boolean | |

### `death` — one row per death (the `kill` table, in context)

| Column | Type | Definition |
|---|---|---|
| `tick`, `round`, `victim`, `victim_team`, `killer`, `killer_team` | Int32, Int16, UInt64?, Enum A/B, UInt64?, Enum A/B? | from `kill`; killer null for the bomb or the world |
| `victim_bot` | Boolean | the victim is a bot (`kill.victim_bot`): `victim` is then null, since the death is nobody's, and `victim_team` is the team of the bot (its controller's, or the killer's opposite). The kill still counts for the killer |
| `is_enemy_kill` | Boolean | killer on the other team |
| `is_opening` | Boolean | first enemy kill of the round after freeze-time end |
| `trade_delay_s`, `trader` | Float32?, UInt64? | the killer is then killed by the victim's team in the round, later or on the same tick (delay 0): after this delay, by this player. When the victim and the killer kill each other on the same tick, nobody is traded; the victim's own grenade or fire killing the killer later does trade the death. **Traded** = delay ≤ W |
| `avenges_delay_s` | Float32? | this kill's victim had killed a teammate of the killer this long before (the latest such kill). **Trade kill** = delay ≤ W |
| `nearest_teammate_distance` | Float32? | distance from the victim to the nearest living teammate, at the death tick |

### `trade_opportunity` — one row per enemy kill and living teammate of the victim

`tick` (Int32), `round` (Int16), `victim`, `killer`, `teammate` (UInt64), `distance_to_killer` (Float32: 3D distance from the teammate to the killer, at the kill tick). A teammate has a trade opportunity when that distance is within ⚙🎯 `trade.opportunity_distance` (1,300 u by default), applied by the metrics.

### `clutch` — one row per clutch

`round` (Int16), `steamid` (UInt64), `team` (Enum A/B), `side` (Enum CT/T), `enemies` (Int8: the N of 1vN), `start_tick` (Int32), `won` (Boolean). Starting lineups are the players alive at freeze-time end. Deaths up to the round end are applied tick by tick, deaths on the same tick together, and a player who leaves the server mid-round (no longer alive in `player_tick`, without a death) leaves the lineup at that tick; a team left with one player facing at least one enemy starts a clutch, at most once per team and round. When both teams are down to one player on the same tick, both players are in a 1v1.

### `team_round` — one row per team and round

`round` (Int16), `team` (Enum A/B), `side` (Enum CT/T), `won` (Boolean), `equip_value` (Float32: team average per player of `economy.equip_value`, at freeze-time end + 7 s), `buy_type` (Enum, first rule that applies):

| Type | Rule (metrics-v1 § 5) |
|---|---|
| `pistol` | first round of each regulation half (rounds 1 and 13 in MR12) |
| `eco` | ≤ $1,000 |
| `full` | ≥ $4,500 on CT, ≥ $4,000 on T |
| `force` | previous round lost, and neither eco nor full |
| `semi` | everything else |

### `swing` — one row per credit of a kill, a plant or a defuse

How much each action moved the round, by the open win-probability model ([winprob](winprob.md), `untraded.winprob.swings`): `round` (Int16), `tick` (Int32), `event` (Enum: `kill`, `plant`, `defuse`), `steamid` (UInt64), `side` (Enum CT/T, the player's), `swing` (Float32: the change in their side's chance of winning the round, from -1 to 1), `p_ct_before` and `p_ct_after` (Float32: the counter-terrorists' chance just before and just after the event; 1 or 0 after an event that decides the round).

- **Kill**: the victim is debited the swing, seen by their side. The enemies who damaged the victim in the round share it, by damage dealt (the killer at least); a flash assist takes 10% of it first. A team kill debits the killer instead, and a death to the world or a suicide only debits the victim.
- **Plant**: the planter (T) gets the swing, while a counter-terrorist is alive. **Defuse**: the defuser (CT) gets it, the round being won.
- Not credited: the death of a bot, kills before freeze-time end, and anything once the round is decided (the bomb's victims, exit frags). The time passing between events is credited to no one.

The table depends on the model's version, unlike the others: a new model means deriving it again (`untraded-worker swings --force`, or `untraded.derive.swing_table` for one match).

## Invariants checked on creation

One `round_player` row per player and round; at most one death per player and round; at most 5 players per team and round; at most one opening per round; at most one clutch per team and round; one `team_round` row per team and round.
