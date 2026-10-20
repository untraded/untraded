# `base.dpr`: Deaths per round

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Reads | Code |
|---|---|---|---|---|
| 1.0.0 | value | per_round | `round_player` | [`dpr` in `metrics/base.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/base.py) |

## Definition

Deaths ÷ rounds played.

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 0.8 | 1 | 0.8 | 1 | 0.4 | 0.8 | 0.8 | 0.8 | 0.8 |

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits


See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#32).
