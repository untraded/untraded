# `rating.untraded_margin`: Untraded Rating margin

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Better | Reads | Code |
|---|---|---|---|---|---|
| 1.0.0 | table | table | neutral | `swing`, `round_player` | [`untraded_margin` in `metrics/ratings.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/ratings.py) |

## Definition

Half-width of the 95 % interval of `rating.untraded`: 1.96 x the standard deviation of the player's swing per round / sqrt(rounds) / k. A rating over few rounds is a rough one. Columns: `steamid`, `rounds`, `margin` (null under 2 rounds).

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| player | rounds | margin |
|---|---|---|
| A1 | 5 | 0.88 |
| A2 | 5 | 1.3 |
| A3 | 5 | 1.68 |
| A4 | 5 | 0.99 |
| A5 | 5 | 0.66 |
| B1 | 5 | 3.29 |
| B2 | 5 | 0.76 |
| B3 | 5 | 1.18 |

*First 8 of 10 rows.*

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- It only counts the spread of the player's own rounds, not the model's uncertainty.
- Ratings summarize; they hide what the other metrics explain. Read them with KAST, ADR and the duels.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version, the beta of the open rating (#137).
