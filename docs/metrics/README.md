# Metrics

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

85 metrics, each with its own page. Parameters, their defaults and the calibrated thresholds are on [parameters.md](parameters.md).

## Shared conventions

- Per-round values divide by the rounds the player **played** (connected and on a team at freeze-time end), not by the rounds of the match (metrics-v1 § 0).
- A dead player who takes over a bot of their team gets the bot's kills and damage, as on the in-game scoreboard; the bot's death is not theirs.

## Base

| Metric | Name | Version | Unit | Better | vs. CS Demo Manager |
|---|---|---|---|---|---|
| [`base.adr`](base.adr.md) | ADR | 1.0.0 | damage_per_round | higher | compared (1 %) |
| [`base.apr`](base.apr.md) | Assists per round | 1.0.0 | per_round | higher | — |
| [`base.assist_score`](base.assist_score.md) | Weighted assists | 1.0.0 | count | higher | — |
| [`base.assists`](base.assists.md) | Assists | 1.0.0 | count | higher | indirectly |
| [`base.deaths`](base.deaths.md) | Deaths | 1.0.0 | count | lower | compared (equal) |
| [`base.dpr`](base.dpr.md) | Deaths per round | 1.0.0 | per_round | lower | — |
| [`base.flash_assists`](base.flash_assists.md) | Flash assists | 1.0.0 | count | higher | indirectly |
| [`base.hs_pct`](base.hs_pct.md) | HS % | 1.0.0 | pct | higher | — |
| [`base.kast`](base.kast.md) | KAST | 1.1.0 | pct | higher | compared (1 %) |
| [`base.kd_diff`](base.kd_diff.md) | K-D | 1.0.0 | count | higher | — |
| [`base.kills`](base.kills.md) | Kills | 1.0.0 | count | higher | compared (equal) |
| [`base.kpr`](base.kpr.md) | Kills per round | 1.0.0 | per_round | higher | — |
| [`base.multikills_1`](base.multikills_1.md) | 1K | 1.0.0 | count | neutral | compared (equal) |
| [`base.multikills_2`](base.multikills_2.md) | 2K | 1.0.0 | count | higher | compared (equal) |
| [`base.multikills_3`](base.multikills_3.md) | 3K | 1.0.0 | count | higher | compared (equal) |
| [`base.multikills_4`](base.multikills_4.md) | 4K | 1.0.0 | count | higher | compared (equal) |
| [`base.multikills_5`](base.multikills_5.md) | 5K | 1.0.0 | count | higher | compared (equal) |
| [`base.rounds_with_kill_pct`](base.rounds_with_kill_pct.md) | Rounds with a kill | 1.0.0 | pct | higher | — |
| [`base.suicides`](base.suicides.md) | Suicides | 1.0.0 | count | lower | — |
| [`base.survival_pct`](base.survival_pct.md) | Survival | 1.1.0 | pct | higher | — |
| [`base.team_kills`](base.team_kills.md) | Team kills | 1.0.0 | count | lower | — |

## Duels

| Metric | Name | Version | Unit | Better | vs. CS Demo Manager |
|---|---|---|---|---|---|
| [`duel.isolated_death_pct`](duel.isolated_death_pct.md) | Isolated death % | 1.1.0 | pct | lower | — |
| [`duel.isolated_deaths`](duel.isolated_deaths.md) | Isolated deaths | 1.1.0 | count | lower | — |
| [`duel.nearest_teammate_at_death`](duel.nearest_teammate_at_death.md) | Spacing at death | 1.0.0 | units | lower | — |
| [`duel.opening_attempt_pct`](duel.opening_attempt_pct.md) | Opening frequency | 1.0.0 | pct | neutral | — |
| [`duel.opening_attempts`](duel.opening_attempts.md) | Opening duels | 1.0.0 | count | neutral | — |
| [`duel.opening_deaths`](duel.opening_deaths.md) | Opening deaths | 1.0.0 | count | lower | compared (equal) |
| [`duel.opening_kills`](duel.opening_kills.md) | Opening kills | 1.0.0 | count | higher | compared (equal) |
| [`duel.opening_success_pct`](duel.opening_success_pct.md) | Opening success | 1.0.0 | pct | higher | — |
| [`duel.opening_win_conversion_pct`](duel.opening_win_conversion_pct.md) | Opening conversion | 1.0.0 | pct | higher | — |

## Trades

| Metric | Name | Version | Unit | Better | vs. CS Demo Manager |
|---|---|---|---|---|---|
| [`trade.death_opportunities`](trade.death_opportunities.md) | Tradable deaths | 1.1.0 | count | neutral | — |
| [`trade.kill_conversion_pct`](trade.kill_conversion_pct.md) | Opportunity conversion | 1.2.0 | pct | higher | — |
| [`trade.kill_opportunities`](trade.kill_opportunities.md) | Trade opportunities | 1.1.0 | count | neutral | — |
| [`trade.trade_kills`](trade.trade_kills.md) | Trade kills (5 s) | 1.1.0 | count | higher | compared (equal) |
| [`trade.trade_kills_w3`](trade.trade_kills_w3.md) | Trade kills (3 s) | 1.1.0 | count | higher | — |
| [`trade.traded_death_pct`](trade.traded_death_pct.md) | Traded death % (5 s) | 1.1.0 | pct | higher | indirectly |
| [`trade.traded_death_pct_w3`](trade.traded_death_pct_w3.md) | Traded death % (3 s) | 1.1.0 | pct | higher | — |
| [`trade.traded_deaths`](trade.traded_deaths.md) | Traded deaths (5 s) | 1.1.0 | count | neutral | compared (equal) |
| [`trade.traded_deaths_w3`](trade.traded_deaths_w3.md) | Traded deaths (3 s) | 1.1.0 | count | neutral | — |
| [`trade.untraded_deaths`](trade.untraded_deaths.md) | Untraded deaths (5 s) | 1.1.0 | count | lower | indirectly |
| [`trade.untraded_deaths_w3`](trade.untraded_deaths_w3.md) | Untraded deaths (3 s) | 1.1.0 | count | lower | — |

## Clutches

| Metric | Name | Version | Unit | Better | vs. CS Demo Manager |
|---|---|---|---|---|---|
| [`clutch.attempts_1v1`](clutch.attempts_1v1.md) | 1v1 attempts | 1.1.0 | count | neutral | compared (equal) |
| [`clutch.attempts_1v2`](clutch.attempts_1v2.md) | 1v2 attempts | 1.1.0 | count | neutral | compared (equal) |
| [`clutch.attempts_1v3`](clutch.attempts_1v3.md) | 1v3 attempts | 1.1.0 | count | neutral | compared (equal) |
| [`clutch.attempts_1v4`](clutch.attempts_1v4.md) | 1v4 attempts | 1.1.0 | count | neutral | compared (equal) |
| [`clutch.attempts_1v5`](clutch.attempts_1v5.md) | 1v5 attempts | 1.1.0 | count | neutral | compared (equal) |
| [`clutch.win_pct`](clutch.win_pct.md) | Clutch success | 1.1.0 | pct | higher | — |
| [`clutch.wins_1v1`](clutch.wins_1v1.md) | 1v1 wins | 1.1.0 | count | higher | compared (equal) |
| [`clutch.wins_1v2`](clutch.wins_1v2.md) | 1v2 wins | 1.1.0 | count | higher | compared (equal) |
| [`clutch.wins_1v3`](clutch.wins_1v3.md) | 1v3 wins | 1.1.0 | count | higher | compared (equal) |
| [`clutch.wins_1v4`](clutch.wins_1v4.md) | 1v4 wins | 1.1.0 | count | higher | compared (equal) |
| [`clutch.wins_1v5`](clutch.wins_1v5.md) | 1v5 wins | 1.1.0 | count | higher | compared (equal) |

## Positioning

| Metric | Name | Version | Unit | Better | vs. CS Demo Manager |
|---|---|---|---|---|---|
| [`pos.death_zones`](pos.death_zones.md) | Death zones | 1.1.0 | table | neutral | — |
| [`pos.heatmap_points`](pos.heatmap_points.md) | Heatmap points | 1.0.0 | table | neutral | — |
| [`pos.kill_zones`](pos.kill_zones.md) | Kill zones | 1.0.0 | table | neutral | — |
| [`pos.recurring_death_spot`](pos.recurring_death_spot.md) | Recurring death spot | 1.2.0 | table | neutral | — |
| [`pos.setup_diversity`](pos.setup_diversity.md) | Predictability | 1.0.0 | table | neutral | — |
| [`pos.setup_zone_t20`](pos.setup_zone_t20.md) | Position at T+20 s | 1.0.0 | table | neutral | — |

## Utility

| Metric | Name | Version | Unit | Better | vs. CS Demo Manager |
|---|---|---|---|---|---|
| [`util.blind_per_flash`](util.blind_per_flash.md) | Flash efficiency | 1.0.0 | seconds | higher | — |
| [`util.enemies_flashed`](util.enemies_flashed.md) | Enemies flashed | 1.0.0 | count | higher | — |
| [`util.enemy_blind_time`](util.enemy_blind_time.md) | Blind time dealt | 1.0.0 | seconds | higher | — |
| [`util.fire_damage`](util.fire_damage.md) | Fire damage | 1.0.0 | hp | higher | — |
| [`util.flash_to_kill`](util.flash_to_kill.md) | Decisive flashes | 1.0.0 | count | higher | — |
| [`util.he_damage`](util.he_damage.md) | HE damage | 1.0.0 | hp | higher | — |
| [`util.he_team_damage`](util.he_team_damage.md) | HE team damage | 1.0.0 | hp | lower | — |
| [`util.self_flashed`](util.self_flashed.md) | Self-flashes | 1.0.0 | count | lower | — |
| [`util.team_blind_time`](util.team_blind_time.md) | Team blind time | 1.0.0 | seconds | lower | — |
| [`util.teammates_flashed`](util.teammates_flashed.md) | Teammates flashed | 1.0.0 | count | lower | — |
| [`util.thrown_decoy`](util.thrown_decoy.md) | Decoy thrown | 1.0.0 | count | neutral | — |
| [`util.thrown_flash`](util.thrown_flash.md) | Flash thrown | 1.0.0 | count | neutral | — |
| [`util.thrown_he`](util.thrown_he.md) | HE thrown | 1.0.0 | count | neutral | — |
| [`util.thrown_molotov`](util.thrown_molotov.md) | Molotov thrown | 1.0.0 | count | neutral | — |
| [`util.thrown_per_round`](util.thrown_per_round.md) | Utility per round | 1.0.0 | per_round | higher | — |
| [`util.thrown_smoke`](util.thrown_smoke.md) | Smoke thrown | 1.0.0 | count | neutral | — |
| [`util.unused_value_at_death`](util.unused_value_at_death.md) | Wasted utility | 1.0.0 | dollars | lower | — |

## Economy

| Metric | Name | Version | Unit | Better | vs. CS Demo Manager |
|---|---|---|---|---|---|
| [`eco.buy_type`](eco.buy_type.md) | Buy type | 1.0.0 | table | neutral | — |
| [`eco.equipment_lost_at_death`](eco.equipment_lost_at_death.md) | Equipment lost | 1.0.0 | dollars | lower | — |
| [`eco.kills_vs_buy`](eco.kills_vs_buy.md) | Kills by economy | 1.0.0 | table | neutral | — |
| [`eco.win_pct_by_matchup`](eco.win_pct_by_matchup.md) | Win % by economy | 1.0.0 | table | neutral | — |

## Ratings

| Metric | Name | Version | Unit | Better | vs. CS Demo Manager |
|---|---|---|---|---|---|
| [`rating.hltv1`](rating.hltv1.md) | HLTV Rating 1.0 | 1.0.0 | ratio | higher | compared (1 %) |
| [`rating.hltv2_approx`](rating.hltv2_approx.md) | HLTV 2.0 (approx.) | 1.1.0 | ratio | higher | compared (1 %) |
| [`rating.swing`](rating.swing.md) | Win-probability swing | 1.1.0 | pct | higher | — |
| [`rating.untraded`](rating.untraded.md) | Untraded Rating | 1.0.0 | ratio | higher | — |
| [`rating.untraded_margin`](rating.untraded_margin.md) | Untraded Rating margin | 1.0.0 | table | neutral | — |
| [`rating.untraded_parts`](rating.untraded_parts.md) | Untraded Rating by action | 1.0.0 | table | neutral | — |
