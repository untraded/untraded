# `util.he_damage`: HE damage

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Better | Reads | Code |
|---|---|---|---|---|---|
| 1.0.0 | value | hp | higher | `damage` | [`he_damage` in `metrics/utility.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/utility.py) |

## Definition

Capped damage of the player's HE grenades to enemies.

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| 9 | 5 | 0 | 0 | 1 | 0 | 0 | 33 | 0 | 15 |

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- Only HE grenades. The 1 to 2 points of a smoke, flash or decoy hitting a player are not utility damage here, unlike CS Demo Manager.
- Blinds of players already dead are ignored. Blind durations are the engine's, which already depend on the distance and the angle to the flash.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#35).
