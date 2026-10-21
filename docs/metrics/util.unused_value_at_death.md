# `util.unused_value_at_death`: Wasted utility

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Better | Reads | Code |
|---|---|---|---|---|---|
| 1.0.0 | value | dollars | lower | `death`, `kill` | [`unused_value_at_death` in `metrics/utility.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/utility.py) |

## Definition

Buy value of the grenades in the player's inventory at death, averaged over their deaths (flash 200, HE 300, smoke 300, molotov 400, incendiary 500, decoy 50).

Stands on [`base.deaths`](base.deaths.md): a value over few cases says little.

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 550 | 0 | 175 | 100 | 0 | 0 | 375 | 375 | 525 |

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- Fixed buy prices; grenades picked up from the ground count at the same price.
- Blinds of players already dead are ignored. Blind durations are the engine's, which already depend on the distance and the angle to the flash.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#35).
