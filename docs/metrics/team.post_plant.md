# `team.post_plant`: Post-plants

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Better | Reads | Code |
|---|---|---|---|---|---|
| 1.0.0 | team | table | higher | `round`, `round_player`, `death` | [`post_plant` in `metrics/team.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/team.py) |

## Definition

Rounds the team played on T with the bomb planted, by site (`key`: `A`, `B` or `unknown`) and by the players alive at the plant (`sub_key`: `{us}v{them}`, e.g. `3v2`): `cases` rounds, `hits` won.

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| team | key | sub_key | cases | hits |
|---|---|---|---|---|
| A | A | 4v3 | 1 | 0 |
| A | B | 2v1 | 1 | 1 |
| B | B | 2v4 | 1 | 1 |

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- Players alive at the plant: those present in the round, minus those dead at the plant's tick or before. A player who left mid-round still counts as alive.
- One side of a match (`A` started on CT, `B` on T), not a team: which side is a team's is decided when the numbers are read (3 players of its roster on the match's date, on the same side), so a team's numbers only cover the matches where that rule finds it.
- Counts, not rates: a rate over several matches adds their counts up (hits ÷ cases over all their rounds), never averages the matches' rates.
- Only rounds whose winner is known count (a last round cut by the end of the demo is left out); overtime rounds count like the others.
- Team samples are small: read every rate with its number of cases.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#210).
