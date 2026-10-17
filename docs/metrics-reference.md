# Metric reference

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The human-written specification is [metrics-v1.md](metrics-v1.md).*

## Base

| ID | Version | Name | Unit | Definition | Parameters | Reads |
|---|---|---|---|---|---|---|
| `base.adr` | 1.0.0 | ADR | damage_per_round | Sum of capped damage to enemies ÷ rounds played. | — | `round_player` |
| `base.apr` | 1.0.0 | Assists per round | per_round | Assists ÷ rounds played. | — | `round_player` |
| `base.assists` | 1.0.0 | Assists | count | Enemy kills where the player is the assister, flash assists excluded. | — | `round_player` |
| `base.deaths` | 1.0.0 | Deaths | count | Number of deaths: by an enemy, a teammate, suicide, fall damage or the bomb. | — | `round_player` |
| `base.dpr` | 1.0.0 | Deaths per round | per_round | Deaths ÷ rounds played. | — | `round_player` |
| `base.flash_assists` | 1.0.0 | Flash assists | count | Enemy kills with `assistedflash` credited to the player. | — | `round_player` |
| `base.hs_pct` | 1.0.0 | HS % | pct | Headshot kills ÷ kills * 100. | — | `death`, `kill` |
| `base.kast` | 1.0.0 | KAST | pct | % of rounds played where the player got a Kill, an Assist (flash assists excluded by default), Survived, or was Traded (death traded within `trade.window_s`). | `trade.window_s = 5.0`, `kast.count_flash_assist = false` | `round_player` |
| `base.kd_diff` | 1.0.0 | K-D | count | kills - deaths. | — | `round_player` |
| `base.kills` | 1.0.0 | Kills | count | Number of kills (enemy kills only). | — | `round_player` |
| `base.kpr` | 1.0.0 | Kills per round | per_round | Kills ÷ rounds played. | — | `round_player` |
| `base.multikills_1` | 1.0.0 | 1K | count | Number of rounds with exactly 1 kill. | — | `round_player` |
| `base.multikills_2` | 1.0.0 | 2K | count | Number of rounds with exactly 2 kills. | — | `round_player` |
| `base.multikills_3` | 1.0.0 | 3K | count | Number of rounds with exactly 3 kills. | — | `round_player` |
| `base.multikills_4` | 1.0.0 | 4K | count | Number of rounds with exactly 4 kills. | — | `round_player` |
| `base.multikills_5` | 1.0.0 | 5K | count | Number of rounds with exactly 5 kills. | — | `round_player` |
| `base.rounds_with_kill_pct` | 1.0.0 | Rounds with a kill | pct | % of rounds with at least one kill. | — | `round_player` |
| `base.suicides` | 1.0.0 | Suicides | count | Deaths where the player is both attacker and victim. | — | `kill` |
| `base.survival_pct` | 1.0.0 | Survival | pct | % of rounds where the player is alive at round end. | — | `round_player` |
| `base.team_kills` | 1.0.0 | Team kills | count | Teammates killed by the player. | — | `kill` |
