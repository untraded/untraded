# Metric reference

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The human-written specification is [metrics-v1.md](metrics-v1.md).*

## Base

| ID | Version | Name | Kind | Unit | Definition | Parameters | Reads |
|---|---|---|---|---|---|---|---|
| `base.adr` | 1.0.0 | ADR | value | damage_per_round | Sum of capped damage to enemies ÷ rounds played. | — | `round_player` |
| `base.apr` | 1.0.0 | Assists per round | value | per_round | Assists ÷ rounds played. | — | `round_player` |
| `base.assists` | 1.0.0 | Assists | value | count | Enemy kills where the player is the assister, flash assists excluded. | — | `round_player` |
| `base.deaths` | 1.0.0 | Deaths | value | count | Number of deaths: by an enemy, a teammate, suicide, fall damage or the bomb. | — | `round_player` |
| `base.dpr` | 1.0.0 | Deaths per round | value | per_round | Deaths ÷ rounds played. | — | `round_player` |
| `base.flash_assists` | 1.0.0 | Flash assists | value | count | Enemy kills with `assistedflash` credited to the player. | — | `round_player` |
| `base.hs_pct` | 1.0.0 | HS % | value | pct | Headshot kills ÷ kills * 100. | — | `death`, `kill` |
| `base.kast` | 1.0.0 | KAST | value | pct | % of rounds played where the player got a Kill, an Assist (flash assists excluded by default), Survived, or was Traded (death traded within `trade.window_s`). | `trade.window_s = 5.0`, `kast.count_flash_assist = false` | `round_player` |
| `base.kd_diff` | 1.0.0 | K-D | value | count | kills - deaths. | — | `round_player` |
| `base.kills` | 1.0.0 | Kills | value | count | Number of kills (enemy kills only). | — | `round_player` |
| `base.kpr` | 1.0.0 | Kills per round | value | per_round | Kills ÷ rounds played. | — | `round_player` |
| `base.multikills_1` | 1.0.0 | 1K | value | count | Number of rounds with exactly 1 kill. | — | `round_player` |
| `base.multikills_2` | 1.0.0 | 2K | value | count | Number of rounds with exactly 2 kills. | — | `round_player` |
| `base.multikills_3` | 1.0.0 | 3K | value | count | Number of rounds with exactly 3 kills. | — | `round_player` |
| `base.multikills_4` | 1.0.0 | 4K | value | count | Number of rounds with exactly 4 kills. | — | `round_player` |
| `base.multikills_5` | 1.0.0 | 5K | value | count | Number of rounds with exactly 5 kills. | — | `round_player` |
| `base.rounds_with_kill_pct` | 1.0.0 | Rounds with a kill | value | pct | % of rounds with at least one kill. | — | `round_player` |
| `base.suicides` | 1.0.0 | Suicides | value | count | Deaths where the player is both attacker and victim. | — | `kill` |
| `base.survival_pct` | 1.0.0 | Survival | value | pct | % of rounds where the player is alive at round end. | — | `round_player` |
| `base.team_kills` | 1.0.0 | Team kills | value | count | Teammates killed by the player. | — | `kill` |

## Duels

| ID | Version | Name | Kind | Unit | Definition | Parameters | Reads |
|---|---|---|---|---|---|---|---|
| `duel.isolated_death_pct` | 1.0.0 | Isolated death % | value | pct | Isolated deaths ÷ deaths * 100. | `trade.window_s = 5.0`, `isolation.radius = 1000.0` | `death`, `round_player` |
| `duel.isolated_deaths` | 1.0.0 | Isolated deaths | value | count | **Untraded** deaths where the nearest living teammate was more than `isolation.radius` away. A death with no living teammate (last player alive) is not isolated. | `trade.window_s = 5.0`, `isolation.radius = 1000.0` | `death` |
| `duel.nearest_teammate_at_death` | 1.0.0 | Spacing at death | value | units | Median, over deaths with a living teammate, of the distance to the nearest one. | — | `death` |
| `duel.opening_attempt_pct` | 1.0.0 | Opening frequency | value | pct | Opening duels ÷ rounds played * 100. | — | `round_player` |
| `duel.opening_attempts` | 1.0.0 | Opening duels | value | count | Opening kills + opening deaths. | — | `round_player` |
| `duel.opening_deaths` | 1.0.0 | Opening deaths | value | count | Rounds where the player is the opening victim. | — | `round_player` |
| `duel.opening_kills` | 1.0.0 | Opening kills | value | count | Rounds where the player makes the opening kill (first enemy kill after freeze end). | — | `round_player` |
| `duel.opening_success_pct` | 1.0.0 | Opening success | value | pct | Opening kills ÷ opening duels * 100. | — | `round_player` |
| `duel.opening_win_conversion_pct` | 1.0.0 | Opening conversion | value | pct | % of rounds with an opening kill by the player that the team wins. | — | `round_player` |

## Trades

| ID | Version | Name | Kind | Unit | Definition | Parameters | Reads |
|---|---|---|---|---|---|---|---|
| `trade.death_opportunities` | 1.0.0 | Tradable deaths | value | count | The player's deaths where at least one teammate had a trade opportunity. | `trade.opportunity_distance = 1000.0` | `trade_opportunity` |
| `trade.kill_conversion_pct` | 1.0.0 | Opportunity conversion | value | pct | Trade kills ÷ trade opportunities * 100. | `trade.window_s = 5.0`, `trade.opportunity_distance = 1000.0` | `death`, `trade_opportunity` |
| `trade.kill_opportunities` | 1.0.0 | Trade opportunities | value | count | Times a teammate of the player was killed while the player was alive and within `trade.opportunity_distance` of the killer. | `trade.opportunity_distance = 1000.0` | `trade_opportunity` |
| `trade.trade_kills` | 1.0.0 | Trade kills (5 s) | value | count | Kills of an enemy who killed a teammate of the player within `trade.window_s` before. | `trade.window_s = 5.0` | `death` |
| `trade.trade_kills_w3` | 1.0.0 | Trade kills (3 s) | value | count | Kills of an enemy who killed a teammate of the player within `trade.window_w3_s` before. | `trade.window_w3_s = 3.0` | `death` |
| `trade.traded_death_pct` | 1.0.0 | Traded death % (5 s) | value | pct | Traded deaths ÷ deaths * 100. | `trade.window_s = 5.0` | `death`, `round_player` |
| `trade.traded_death_pct_w3` | 1.0.0 | Traded death % (3 s) | value | pct | Traded deaths ÷ deaths * 100. | `trade.window_w3_s = 3.0` | `death`, `round_player` |
| `trade.traded_deaths` | 1.0.0 | Traded deaths (5 s) | value | count | The player's deaths whose killer was killed by a teammate within `trade.window_s`. | `trade.window_s = 5.0` | `death` |
| `trade.traded_deaths_w3` | 1.0.0 | Traded deaths (3 s) | value | count | The player's deaths whose killer was killed by a teammate within `trade.window_w3_s`. | `trade.window_w3_s = 3.0` | `death` |
| `trade.untraded_deaths` | 1.0.0 | Untraded deaths (5 s) | value | count | Deaths - traded deaths (the product's signature metric). | `trade.window_s = 5.0` | `death`, `round_player` |
| `trade.untraded_deaths_w3` | 1.0.0 | Untraded deaths (3 s) | value | count | Deaths - traded deaths (the product's signature metric). | `trade.window_w3_s = 3.0` | `death`, `round_player` |

## Clutches

| ID | Version | Name | Kind | Unit | Definition | Parameters | Reads |
|---|---|---|---|---|---|---|---|
| `clutch.attempts_1v1` | 1.0.0 | 1v1 attempts | value | count | Rounds where the player becomes the last one alive on the team, facing 1 living enemy. | — | `clutch` |
| `clutch.attempts_1v2` | 1.0.0 | 1v2 attempts | value | count | Rounds where the player becomes the last one alive on the team, facing 2 living enemies. | — | `clutch` |
| `clutch.attempts_1v3` | 1.0.0 | 1v3 attempts | value | count | Rounds where the player becomes the last one alive on the team, facing 3 living enemies. | — | `clutch` |
| `clutch.attempts_1v4` | 1.0.0 | 1v4 attempts | value | count | Rounds where the player becomes the last one alive on the team, facing 4 living enemies. | — | `clutch` |
| `clutch.attempts_1v5` | 1.0.0 | 1v5 attempts | value | count | Rounds where the player becomes the last one alive on the team, facing 5 living enemies. | — | `clutch` |
| `clutch.win_pct` | 1.0.0 | Clutch success | value | pct | Clutch wins ÷ clutch attempts * 100, over all N. | — | `clutch` |
| `clutch.wins_1v1` | 1.0.0 | 1v1 wins | value | count | 1v1 clutches the team wins. | — | `clutch` |
| `clutch.wins_1v2` | 1.0.0 | 1v2 wins | value | count | 1v2 clutches the team wins. | — | `clutch` |
| `clutch.wins_1v3` | 1.0.0 | 1v3 wins | value | count | 1v3 clutches the team wins. | — | `clutch` |
| `clutch.wins_1v4` | 1.0.0 | 1v4 wins | value | count | 1v4 clutches the team wins. | — | `clutch` |
| `clutch.wins_1v5` | 1.0.0 | 1v5 wins | value | count | 1v5 clutches the team wins. | — | `clutch` |

## Positioning

| ID | Version | Name | Kind | Unit | Definition | Parameters | Reads |
|---|---|---|---|---|---|---|---|
| `pos.death_zones` | 1.0.0 | Death zones | table | table | Deaths by zone, per map and side, with the traded % in each zone. Columns: `steamid`, `map`, `side`, `zone`, `deaths`, `traded_pct`. | `trade.window_s = 5.0` | `death`, `kill` |
| `pos.heatmap_points` | 1.0.0 | Heatmap points | table | table | Raw kill and death positions per map and side (rendering comes in phase 2). Columns: `steamid`, `match_id`, `round`, `map`, `side`, `role` (`kill`, `death`), `zone`, `x`, `y`, `z`. | — | `death`, `kill` |
| `pos.kill_zones` | 1.0.0 | Kill zones | table | table | Enemy kills by the killer's zone, per map and side. Columns: `steamid`, `map`, `side`, `zone`, `kills`. | — | `death`, `kill` |
| `pos.recurring_death_spot` | 1.0.0 | Recurring death spot | table | table | Per map and side: zones holding at least `pos.recurring_death_share` of the player's **untraded** deaths, when the player played at least `pos.recurring_min_rounds` rounds there. Columns: `steamid`, `map`, `side`, `zone`, `untraded_deaths`, `share_pct`, `rounds`. | `trade.window_s = 5.0`, `pos.recurring_death_share = 0.25`, `pos.recurring_min_rounds = 8` | `death`, `kill`, `round_player` |
| `pos.setup_diversity` | 1.0.0 | Predictability | table | table | Normalized entropy of the T+20 s zone distribution, per map and side: 0 = always the same zone, 1 = spread evenly over the zones used (entropy ÷ ln of the number of distinct zones; 0 with a single zone). Columns: `steamid`, `map`, `side`, `rounds`, `zones`, `diversity`. | — | `round_player` |
| `pos.setup_zone_t20` | 1.0.0 | Position at T+20 s | table | table | The player's zone 20 s after freeze-time end (rounds where they are alive then), per map and side: CT setups, T defaults. Columns: `steamid`, `map`, `side`, `zone`, `rounds`, `share_pct`. | — | `round_player` |

## Utility

| ID | Version | Name | Kind | Unit | Definition | Parameters | Reads |
|---|---|---|---|---|---|---|---|
| `util.blind_per_flash` | 1.0.0 | Flash efficiency | value | seconds | Enemy blind time dealt ÷ flashes thrown. | — | `blind`, `death`, `grenade` |
| `util.enemies_flashed` | 1.0.0 | Enemies flashed | value | count | Living enemies blinded by the player's flashes for at least `flash.min_blind_s`. | `flash.min_blind_s = 1.0` | `blind`, `death` |
| `util.enemy_blind_time` | 1.0.0 | Blind time dealt | value | seconds | Sum of the blind durations of living enemies (every blind, no minimum). | — | `blind`, `death` |
| `util.fire_damage` | 1.0.0 | Fire damage | value | hp | Capped damage of the player's molotovs and incendiaries (fire and impact) to enemies, counting only damage linked to one of the player's own grenades (demoparser2 #317). | — | `damage` |
| `util.flash_to_kill` | 1.0.0 | Decisive flashes | value | count | Enemies blinded by the player and killed by the player's team (the player included) while still blind: blind tick ≤ kill tick ≤ blind tick + duration. One count per kill, for each player whose flash was still active. | — | `blind`, `death`, `round_player`, `match` |
| `util.he_damage` | 1.0.0 | HE damage | value | hp | Capped damage of the player's HE grenades to enemies. | — | `damage` |
| `util.he_team_damage` | 1.0.0 | HE team damage | value | hp | Capped damage of the player's HE grenades to teammates (self-damage excluded). | — | `damage` |
| `util.self_flashed` | 1.0.0 | Self-flashes | value | count | Times the player blinded themselves for at least `flash.min_blind_s`. | `flash.min_blind_s = 1.0` | `blind`, `death` |
| `util.team_blind_time` | 1.0.0 | Team blind time | value | seconds | Sum of the blind durations of living teammates (every blind, no minimum). | — | `blind`, `death` |
| `util.teammates_flashed` | 1.0.0 | Teammates flashed | value | count | Living teammates (not the player) blinded by the player's flashes for at least `flash.min_blind_s`. | `flash.min_blind_s = 1.0` | `blind`, `death` |
| `util.thrown_decoy` | 1.0.0 | Decoy thrown | value | count | Grenades of type `decoy` thrown. | — | `grenade` |
| `util.thrown_flash` | 1.0.0 | Flash thrown | value | count | Grenades of type `flash` thrown. | — | `grenade` |
| `util.thrown_he` | 1.0.0 | HE thrown | value | count | Grenades of type `he` thrown. | — | `grenade` |
| `util.thrown_molotov` | 1.0.0 | Molotov thrown | value | count | Grenades of type `molotov` thrown (molotov and incendiary merged). | — | `grenade` |
| `util.thrown_per_round` | 1.0.0 | Utility per round | value | per_round | Grenades thrown (all types) ÷ rounds played. | — | `grenade`, `round_player` |
| `util.thrown_smoke` | 1.0.0 | Smoke thrown | value | count | Grenades of type `smoke` thrown. | — | `grenade` |
| `util.unused_value_at_death` | 1.0.0 | Wasted utility | value | dollars | Buy value of the grenades in the player's inventory at death, averaged over their deaths (flash 200, HE 300, smoke 300, molotov 400, incendiary 500, decoy 50). | — | `death`, `kill` |

## Economy

| ID | Version | Name | Kind | Unit | Definition | Parameters | Reads |
|---|---|---|---|---|---|---|---|
| `eco.buy_type` | 1.0.0 | Buy type | table | table | Rounds played per team buy type (`pistol`, `eco`, `semi`, `force`, `full`), with the % won. The buy type is also a split: `Dataset.split(buy=...)`. Columns: `steamid`, `buy_type`, `rounds`, `win_pct`. | — | `team_round`, `round_player` |
| `eco.equipment_lost_at_death` | 1.0.0 | Equipment lost | value | dollars | The player's equipment value at the tick of death, averaged over their deaths. | — | `death`, `kill` |
| `eco.kills_vs_buy` | 1.0.0 | Kills by economy | table | table | The player's enemy kills per (killer weapon class, victim weapon class). The class is the best weapon held: `awp`, `rifle` (other snipers included), `heavy` (shotguns and machine guns), `smg`, else `pistol`. The killer's inventory is the last change before the kill, the victim's is read at the kill. Columns: `steamid`, `killer_class`, `victim_class`, `kills`. | — | `death`, `kill`, `inventory_change` |
| `eco.win_pct_by_matchup` | 1.0.0 | Win % by economy | table | table | % of rounds won per (team buy type, opponent buy type) pair. Columns: `steamid`, `buy_type`, `opponent_buy_type`, `rounds`, `win_pct`. | — | `team_round`, `round_player` |
