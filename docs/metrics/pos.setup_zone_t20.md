# `pos.setup_zone_t20`: Position at T+20 s

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Better | Reads | Code |
|---|---|---|---|---|---|
| 1.0.0 | table | table | neutral | `round_player` | [`setup_zone_t20` in `metrics/positioning.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/positioning.py) |

## Definition

The player's zone 20 s after freeze-time end (rounds where they are alive then), per map and side: CT setups, T defaults. Columns: `steamid`, `map`, `side`, `zone`, `rounds`, `share_pct`.

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| player | map | side | zone | rounds | share_pct |
|---|---|---|---|---|---|
| A1 | de_cache | CT | BombsiteB | 1 | 50 |
| A1 | de_cache | CT | TreeRoom | 1 | 50 |
| A1 | de_cache | T | Mid | 1 | 100 |
| A2 | de_cache | CT | BombsiteA | 1 | 50 |
| A2 | de_cache | CT | Quad | 1 | 50 |
| A2 | de_cache | T | Garage | 1 | 50 |
| A2 | de_cache | T | SunRoom | 1 | 50 |
| A3 | de_cache | CT | Mid | 2 | 100 |

*First 8 of 37 rows.*

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- Only rounds where the player is alive 20 s after freeze-time end (`setup.offset_s`).
- Zones are the engine's navmesh place names (`last_place_name`, e.g. `BombsiteA`), not community callouts, and some places are large.
- These are distributions per map and side: they become meaningful over many rounds on the same map, not on a single match.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#34).
