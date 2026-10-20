# `base.assist_score`: Weighted assists

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Reads | Code |
|---|---|---|---|---|
| 1.0.0 | value | count | `round_player` | [`assist_score` in `metrics/base.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/base.py) |

## Definition

Assists + `assist.flash_weight` * flash assists: a flash assist counts, but less than an assist.

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `assist.flash_weight` | 0.5 ratio | Weight of a flash assist in `base.assist_score`, an assist weighing 1. |

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 1.5 | 2 | 2 | 0 | 2 | 0 | 3 | 1 | 3 |

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits


See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#43).
