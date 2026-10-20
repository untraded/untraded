# `eco.equipment_lost_at_death`: Equipment lost

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Reads | Code |
|---|---|---|---|---|
| 1.0.0 | value | dollars | `death`, `kill` | [`equipment_lost_at_death` in `metrics/economy.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/economy.py) |

## Definition

The player's equipment value at the tick of death, averaged over their deaths.

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| 2350 | 2937.5 | 2170 | 2787.5 | 2500 | 3150 | 2287.5 | 2862.5 | 2950 | 3900 |

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- The equipment value at the tick of death includes weapons picked up during the round.
- Buy types use v0 thresholds aligned with CS Demo Manager (`buy.eco_max`, `buy.full_min_ct`, `buy.full_min_t`), still to calibrate on our target level.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#36).
