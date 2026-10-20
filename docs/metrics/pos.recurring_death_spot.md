# `pos.recurring_death_spot`: Recurring death spot

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Reads | Code |
|---|---|---|---|---|
| 1.1.0 | table | table | `death`, `kill`, `round_player` | [`recurring_death_spot` in `metrics/positioning.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/positioning.py) |

## Definition

Per map and side: zones holding at least `pos.recurring_death_share` of the player's **untraded** deaths, when the player played at least `pos.recurring_min_rounds` rounds there. Columns: `steamid`, `map`, `side`, `zone`, `untraded_deaths`, `share_pct`, `rounds`.

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `trade.window_s` | 5.0 s | Trade window W: a death is traded when a teammate kills the killer within W seconds, both ends included (the same tick, and exactly W). 5 s is the usual convention (HLTV, CS Demo Manager); CS Demo Manager excludes exactly W. |
| `pos.recurring_death_share` | 0.25 ratio | Share of the player's untraded deaths on a map and side that makes a zone recurring. 🎯 v0, to calibrate. |
| `pos.recurring_min_rounds` | 8 rounds | Rounds the player must have played on a map and side before a zone can be recurring. 🎯 v0, to calibrate. |

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

*No rows on this window: the thresholds need more rounds.*

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- The share and the minimum rounds are v0 thresholds (🎯); the table is empty until the player has played enough rounds on a map and side.
- Zones are the engine's navmesh place names (`last_place_name`, e.g. `BombsiteA`), not community callouts, and some places are large.
- These are distributions per map and side: they become meaningful over many rounds on the same map, not on a single match.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#34).
- **1.1.0**: Trades now count a kill on the same tick (delay 0) (#41) and the victim's own grenade or fire killing the killer later (#42); two players killing each other on the same tick trade nothing.
