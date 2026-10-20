<!--
SPDX-FileCopyrightText: 2026 The Untraded Authors
SPDX-License-Identifier: AGPL-3.0-only
-->

# Advice

After each session, Untraded gives up to **three priorities**. Each comes with:
- a finding against a named reference;
- the **rounds that prove it** (match, round, tick);
- an action;
- an indicator to follow.

The rules are open, like the metrics: `untraded.advice` (MIT).

## References

A session is compared with, in this order:

1. **the player's own 30 days** before it, once they hold at least 5 matches and 100 rounds (`untraded.reference`);
2. else **players of the same level**: every player of the collected matches in the same Premier rating band of 2,500 points (`level_reference`, recomputed hourly by the worker). These are anonymous aggregates, computed as follows:
   - players who opted out are left out;
   - a band needs at least 300 (player, match) rows and **20 distinct players**, and is widened one step on each side until it has them;
   - totals are compared per round (sum ÷ rounds), the other metrics by their median;
   - a match the player left in fewer than 10 rounds does not count;
3. else nothing: the report shows the session alone and says what is missing.

The report always names its reference ("your 14 matches from … to …", or "Premier players rated 15,000–22,500, 812 player-matches").

## How a rule fires

A rule watches one metric, and the metric's direction (`better`) says what "worse" means. It fires when both hold:

1. the session is worse than the reference by at least **`advice.min_gap_pct` = 15 %** (relative);
2. the session holds at least **`advice.min_events` = 3** events that prove it (2 for opening duels, opening conversion, clutches and the recurring spot).

**The evidence is what the metric counts.** Each rule's events apply the metric's own filter and parameters (trade window, isolation radius, minimum blind…), and the tests check the counts match on every fixture.

**Pattern rules** look at the session and the days before it together. For example, a zone that holds a recurring share of the player's untraded deaths (`pos.recurring_death_spot`). They show the session's deaths in that zone.

## Priorities

A finding costs the rounds it touches, weighted by those the team lost:

```
cost = rounds lost + advice.won_round_weight (0.25) × rounds won
```

The three costliest findings become the priorities. A finding whose rounds mostly repeat a kept one (over 50 %) is skipped: two rules on the same deaths make one priority. The open rating (planned) will replace this estimate of what a mistake costs.

## Rules (batch 1)

| Rule | Watches | Evidence |
|---|---|---|
| `trade.untraded_deaths` | `trade.untraded_deaths` (lower) | deaths not traded within `trade.window_s` |
| `trade.isolated_deaths` | `duel.isolated_death_pct` (lower) | untraded deaths with no teammate within `isolation.radius` |
| `trade.missed_trades` | `trade.kill_conversion_pct` (higher) | teammates killed near the player whose killer the player did not kill within the window |
| `duel.opening_deaths` | `duel.opening_success_pct` (higher) | the player's opening deaths |
| `duel.openings_lost` | `duel.opening_win_conversion_pct` (higher) | rounds lost after the player's opening kill |
| `clutch.clutches_lost` | `clutch.win_pct` (higher) | clutches lost (start of the clutch) |
| `combat.duels_without_damage` | `base.hs_pct` (higher) | deaths to an enemy the player had not damaged in that round |
| `util.wasted_utility` | `util.unused_value_at_death` (lower) | deaths with grenades still in the inventory |
| `util.team_flashes` | `util.teammates_flashed` (lower) | living teammates blinded by the player's flashes |
| `pos.recurring_death_spot` | `pos.recurring_death_spot` (pattern) | the session's untraded deaths in a recurring zone |

Rules carry a semantic version: a change of trigger or evidence bumps it, as for metrics (ADR 0003). The thresholds are to be calibrated on the testers' sessions.

## Output

A `Finding` holds:
- the rule and its version;
- the watched metric and its version;
- the session and reference values;
- the evidence: `match_id`, `round`, `tick`, `map`, `side`, plus details such as the killer, the distance or the grenades;
- rounds touched, rounds lost and cost;
- the i18n message key (`advice.<rule>`), the action ids and the indicator.

The clients render the text in the user's language and tone (coach or analyst).
