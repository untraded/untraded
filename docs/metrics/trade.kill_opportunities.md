# `trade.kill_opportunities`: Trade opportunities

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Better | Reads | Code |
|---|---|---|---|---|---|
| 1.2.0 | value | count | neutral | `death`, `trade_opportunity` | [`kill_opportunities` in `metrics/duels.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/duels.py) |

## Definition

Times a teammate of the player was killed while the player was alive, within `trade.opportunity_distance` of the killer, and saw the killer (the engine's spotting) within `trade.window_s` of the kill, or traded it.

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `trade.window_s` | 5.0 s | Trade window W: a death is traded when a teammate kills the killer within W seconds, both ends included (the same tick, and exactly W). 5 s is the usual convention (HLTV, CS Demo Manager); CS Demo Manager excludes exactly W. |
| `trade.opportunity_distance` | 1300.0 units | A living teammate of the victim within this straight-line distance of the killer, who saw the killer within the trade window, had a trade opportunity. 🎯 Calibrated on the corpus (docs/calibration.md). |

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 1 | 1 | 4 | 2 | 3 | 0 | 3 | 1 | 2 |

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- The sighting is the engine's spotting (the radar's), sampled at 16 Hz: not a true line of sight, and it can lag behind a quick trade, which is why a trade counts as seen. The distance (🎯) was calibrated on the corpus: 1300 units (docs/calibration.md).
- A death is traded only when the killer is then killed **by the victim's team**, within `trade.window_s`, both ends included. CS Demo Manager differs in four ways: a killer killed by their own teammate trades the death, a player controlling a bot can trade, the kill of an enemy who had just killed a teammate is a trade kill, and a trade at exactly 5.00 s does not count (validation-csdm § 5).
- Distances are straight lines between positions, through walls.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#33).
- **1.1.0**: `trade.opportunity_distance` 1000 -> 1300 units: 26 % of the real trades of the calibration corpus came from beyond 1000 units, 90 % from within 1300 (docs/calibration.md).
- **1.2.0**: An opportunity needs the teammate to have seen the killer within `trade.window_s` (the engine's spotting), or to have traded it: distance alone counted teammates behind walls, and only 14 % of the opportunities were converted (#167).
