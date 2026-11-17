# `team.retake`: Retakes

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Better | Reads | Code |
|---|---|---|---|---|---|
| 1.0.0 | team | table | higher | `round`, `round_player`, `death` | [`retake` in `metrics/team.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/team.py) |

## Definition

Rounds the team played on CT where the enemy planted the bomb, by site (`key`: `A`, `B` or `unknown`) and by the players alive at the plant (`sub_key`: `{us}v{them}`): `cases` rounds, `hits` won.

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| team | key | sub_key | cases | hits |
|---|---|---|---|---|
| A | B | 4v2 | 1 | 0 |
| B | A | 3v4 | 1 | 1 |
| B | B | 1v2 | 1 | 0 |

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- Players alive at the plant, as for `team.post_plant`; a retake is any CT round with an enemy plant, saves included.
- One side of a match (`A` started on CT, `B` on T), not a team: which side is a team's is decided when the numbers are read (3 players of its roster on the match's date, on the same side), so a team's numbers only cover the matches where that rule finds it.
- Counts, not rates: a rate over several matches adds their counts up (hits ÷ cases over all their rounds), never averages the matches' rates.
- Only rounds whose winner is known count (a last round cut by the end of the demo is left out); overtime rounds count like the others.
- Team samples are small: read every rate with its number of cases.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#210).
