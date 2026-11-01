# `rating.untraded_parts`: Untraded Rating by action

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Better | Reads | Code |
|---|---|---|---|---|---|
| 2.0.0 | table | table | neutral | `ledger`, `round_player` | [`untraded_parts` in `metrics/ratings.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/ratings.py) |

## Definition

Where `rating.untraded` comes from, in rating points: `shooting` (damage and kills with guns, the player's shares of the kills they made or helped), `utility` (grenade damage and kills, flashes on the victims), `trade` (the share given back when a teammate trades the player's killer), `objective` (plants and defuses, and their cost to the other side), `taken` (damage and deaths suffered), `team` (harm to one's own side), `balance` (the recentring that keeps the round's average player at zero) and `baseline` (1.00), so that the parts add up to the rating. Columns: `steamid`, `part`, `points`.

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| player | part | points |
|---|---|---|
| A1 | balance | 0 |
| A1 | baseline | 1 |
| A1 | objective | -0.09 |
| A1 | shooting | 0.37 |
| A1 | taken | -0.97 |
| A1 | team | 0 |
| A1 | trade | 0.04 |
| A1 | utility | 0.02 |

*First 8 of 80 rows.*

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- Ratings summarize; they hide what the other metrics explain. Read them with KAST, ADR and the duels.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version, the beta of the open rating (#137).
- **2.0.0**: The parts of the rating 2.0: shooting, utility, trade, objective, taken, team, balance and baseline.
