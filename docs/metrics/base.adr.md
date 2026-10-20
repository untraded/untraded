# `base.adr`: ADR

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Reads | Code |
|---|---|---|---|---|
| 1.0.0 | value | damage_per_round | `round_player` | [`adr` in `metrics/base.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/base.py) |

## Definition

Sum of capped damage to enemies ÷ rounds played.

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| 39.8 | 84.8 | 119.8 | 75.8 | 96.2 | 140.2 | 43.2 | 148.4 | 40.6 | 88.4 |

## Against CS Demo Manager

Compared player by player on 30 matches (must be within 1 %). Every remaining gap is a documented definition difference: see [validation-csdm.md](../validation-csdm.md).

## Limits


See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#32).
