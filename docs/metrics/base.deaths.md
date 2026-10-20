# `base.deaths`: Deaths

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Reads | Code |
|---|---|---|---|---|
| 1.0.0 | value | count | `round_player` | [`deaths` in `metrics/base.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/base.py) |

## Definition

Number of deaths: by an enemy, a teammate, suicide, fall damage or the bomb.

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| 5 | 4 | 5 | 4 | 5 | 2 | 4 | 4 | 4 | 4 |

## Against CS Demo Manager

Compared player by player on 30 matches (must be equal). Every remaining gap is a documented definition difference: see [validation-csdm.md](../validation-csdm.md).

## Limits


See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#32).
