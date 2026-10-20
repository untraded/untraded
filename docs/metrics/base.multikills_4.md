# `base.multikills_4`: 4K

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Reads | Code |
|---|---|---|---|---|
| 1.0.0 | value | count | `round_player` | [`multikills` in `metrics/base.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/base.py) |

## Definition

Number of rounds with exactly 4 kills.

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Against CS Demo Manager

Compared player by player on 30 matches, against equal values. The values that differ are counted and explained, each by a documented definition difference, in [validation-csdm.md](../validation-csdm.md).

## Limits


See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#32).
