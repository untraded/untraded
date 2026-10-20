# `pos.kill_zones`: Kill zones

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Reads | Code |
|---|---|---|---|---|
| 1.0.0 | table | table | `death`, `kill` | [`kill_zones` in `metrics/positioning.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/positioning.py) |

## Definition

Enemy kills by the killer's zone, per map and side. Columns: `steamid`, `map`, `side`, `zone`, `kills`.

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| player | map | side | zone | kills |
|---|---|---|---|---|
| A1 | de_cache | CT | TreeRoom | 1 |
| A2 | de_cache | CT | Quad | 1 |
| A2 | de_cache | T | MidRoof | 1 |
| A2 | de_cache | T | SunRoom | 1 |
| A3 | de_cache | CT | BombsiteB | 1 |
| A3 | de_cache | T | Mid | 2 |
| A3 | de_cache | T | MidRoof | 2 |
| A4 | de_cache | CT | BMain | 1 |

*First 8 of 28 rows.*

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- Zones are the engine's navmesh place names (`last_place_name`, e.g. `BombsiteA`), not community callouts, and some places are large.
- These are distributions per map and side: they become meaningful over many rounds on the same map, not on a single match.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#34).
