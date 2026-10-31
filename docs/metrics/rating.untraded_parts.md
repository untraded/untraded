# `rating.untraded_parts`: Untraded Rating by action

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Better | Reads | Code |
|---|---|---|---|---|---|
| 1.0.0 | table | table | neutral | `swing`, `round_player` | [`untraded_parts` in `metrics/ratings.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/ratings.py) |

## Definition

Where `rating.untraded` comes from, in rating points: `kills` (the kill credits that helped the player's side: the shares of the kills they made or helped, by damage and flash), `deaths` (the kill credits that hurt it: their deaths, and team kills), `plants`, `defuses`, and `baseline` (1 - m / k), so that the parts add up to the rating. Columns: `steamid`, `part`, `points`.

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| player | part | points |
|---|---|---|
| A1 | baseline | 0.97 |
| A1 | deaths | -0.88 |
| A1 | defuses | 0 |
| A1 | kills | 0.4 |
| A1 | plants | 0.05 |
| A2 | baseline | 0.97 |
| A2 | deaths | -0.97 |
| A2 | defuses | 0 |

*First 8 of 50 rows.*

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- Ratings summarize; they hide what the other metrics explain. Read them with KAST, ADR and the duels.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version, the beta of the open rating (#137).
