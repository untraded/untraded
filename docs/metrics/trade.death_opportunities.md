# `trade.death_opportunities`: Tradable deaths

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Reads | Code |
|---|---|---|---|---|
| 1.0.0 | value | count | `trade_opportunity` | [`death_opportunities` in `metrics/duels.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/duels.py) |

## Definition

The player's deaths where at least one teammate had a trade opportunity.

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `trade.opportunity_distance` | 1000.0 units | A living teammate of the victim within this straight-line distance of the killer had a trade opportunity. 🎯 v0, to calibrate. |

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 3 | 1 | 3 | 2 | 1 | 3 | 2 | 2 | 2 |

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- An opportunity is a distance, not a sight line. The distance is a v0 threshold (🎯).
- A death is traded only when the killer is then killed **by the victim's team**, within `trade.window_s` and the same tick included. A killer killed by their own teammate does not trade it, unlike CS Demo Manager.
- Distances are straight lines between positions, through walls.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#33).
