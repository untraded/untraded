# `pos.setup_diversity`: Predictability

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Reads | Code |
|---|---|---|---|---|
| 1.0.0 | table | table | `round_player` | [`setup_diversity` in `metrics/positioning.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/positioning.py) |

## Definition

Normalized entropy of the T+20 s zone distribution, per map and side: 0 = always the same zone, 1 = spread evenly over the zones used (entropy ÷ ln of the number of distinct zones; 0 with a single zone). Columns: `steamid`, `map`, `side`, `rounds`, `zones`, `diversity`.

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| player | map | side | rounds | zones | diversity |
|---|---|---|---|---|---|
| A1 | de_cache | CT | 2 | 2 | 1 |
| A1 | de_cache | T | 1 | 1 | 0 |
| A2 | de_cache | CT | 2 | 2 | 1 |
| A2 | de_cache | T | 2 | 2 | 1 |
| A3 | de_cache | CT | 2 | 1 | 0 |
| A3 | de_cache | T | 3 | 3 | 1 |
| A4 | de_cache | CT | 2 | 2 | 1 |
| A4 | de_cache | T | 3 | 2 | 0.92 |

*First 8 of 20 rows.*

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- Zones are the engine's navmesh place names (`last_place_name`, e.g. `BombsiteA`), not community callouts, and some places are large.
- These are distributions per map and side: they become meaningful over many rounds on the same map, not on a single match.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#34).
