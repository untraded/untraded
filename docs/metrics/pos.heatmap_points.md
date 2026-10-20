# `pos.heatmap_points`: Heatmap points

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Reads | Code |
|---|---|---|---|---|
| 1.0.0 | table | table | `death`, `kill` | [`heatmap_points` in `metrics/positioning.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/positioning.py) |

## Definition

Raw kill and death positions per map and side (rendering comes in phase 2). Columns: `steamid`, `match_id`, `round`, `map`, `side`, `role` (`kill`, `death`), `zone`, `x`, `y`, `z`.

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| player | round | map | side | role | zone | x | y | z |
|---|---|---|---|---|---|---|---|---|
| A1 | 11 | de_cache | CT | death | Truck | -1037.44 | 1282.45 | 1688.03 |
| A1 | 12 | de_cache | CT | death | BombsiteB | -159.1 | -989.2 | 1612.03 |
| A1 | 12 | de_cache | CT | kill | TreeRoom | -743.43 | -942.74 | 1612.03 |
| A1 | 13 | de_cache | T | death | Mid | -123.09 | 180.89 | 1610.85 |
| A1 | 14 | de_cache | T | death | Mid | 602.19 | 280.94 | 1608.35 |
| A1 | 15 | de_cache | T | death | BombsiteA | -385.69 | 1430.87 | 1688.03 |
| A2 | 11 | de_cache | CT | death | AMain | 561.4 | 1723.26 | 1700.03 |
| A2 | 12 | de_cache | CT | death | BombsiteB | 14.66 | -749.65 | 1609.03 |

*First 8 of 81 rows.*

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- Raw points only: rendering comes in phase 2.
- Zones are the engine's navmesh place names (`last_place_name`, e.g. `BombsiteA`), not community callouts, and some places are large.
- These are distributions per map and side: they become meaningful over many rounds on the same map, not on a single match.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#34).
