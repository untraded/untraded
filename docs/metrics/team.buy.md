# `team.buy`: Rounds by buy type

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Better | Reads | Code |
|---|---|---|---|---|---|
| 1.0.0 | team | table | higher | `team_round`, `round` | [`buy` in `metrics/team.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/team.py) |

## Definition

Rounds by the team's buy type (`key`: `pistol`, `eco`, `semi`, `force`, `full`, from the round model) and the enemy's (`sub_key`): `cases` rounds, `hits` won.

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| team | key | sub_key | cases | hits |
|---|---|---|---|---|
| A | force | semi | 1 | 1 |
| A | full | eco | 1 | 0 |
| A | full | full | 1 | 0 |
| A | pistol | pistol | 1 | 0 |
| A | semi | full | 1 | 0 |
| B | eco | full | 1 | 1 |
| B | full | full | 1 | 1 |
| B | full | semi | 1 | 1 |

*First 8 of 10 rows.*

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- Buy types come from the round model (`BuyThresholds`, parameters on [parameters.md](parameters.md)); overtime rounds are never pistol rounds.
- One side of a match (`A` started on CT, `B` on T), not a team: which side is a team's is decided when the numbers are read (3 players of its roster on the match's date, on the same side), so a team's numbers only cover the matches where that rule finds it.
- Counts, not rates: a rate over several matches adds their counts up (hits ÷ cases over all their rounds), never averages the matches' rates.
- Only rounds whose winner is known count (a last round cut by the end of the demo is left out); overtime rounds count like the others.
- Team samples are small: read every rate with its number of cases.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#210).
