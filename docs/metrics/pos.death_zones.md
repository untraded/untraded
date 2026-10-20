# `pos.death_zones`: Death zones

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Reads | Code |
|---|---|---|---|---|
| 1.1.0 | table | table | `death`, `kill` | [`death_zones` in `metrics/positioning.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/positioning.py) |

## Definition

Deaths by zone, per map and side, with the traded % in each zone. Columns: `steamid`, `map`, `side`, `zone`, `deaths`, `traded_pct`.

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `trade.window_s` | 5.0 s | Trade window W: a death is traded when a teammate kills the killer within W seconds, both ends included (the same tick, and exactly W). 5 s is the usual convention (HLTV, CS Demo Manager); CS Demo Manager excludes exactly W. |

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| player | map | side | zone | deaths | traded_pct |
|---|---|---|---|---|---|
| A1 | de_cache | CT | BombsiteB | 1 | 0 |
| A1 | de_cache | CT | Truck | 1 | 0 |
| A1 | de_cache | T | BombsiteA | 1 | 0 |
| A1 | de_cache | T | Mid | 2 | 50 |
| A2 | de_cache | CT | AMain | 1 | 0 |
| A2 | de_cache | CT | BombsiteB | 1 | 0 |
| A2 | de_cache | T | MidRoof | 1 | 0 |
| A2 | de_cache | T | SunRoom | 1 | 100 |

*First 8 of 37 rows.*

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- Zones are the engine's navmesh place names (`last_place_name`, e.g. `BombsiteA`), not community callouts, and some places are large.
- These are distributions per map and side: they become meaningful over many rounds on the same map, not on a single match.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#34).
- **1.1.0**: Trades now count a kill on the same tick (delay 0) (#41) and the victim's own grenade or fire killing the killer later (#42); two players killing each other on the same tick trade nothing.
