# `util.self_flashed`: Self-flashes

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Better | Reads | Code |
|---|---|---|---|---|---|
| 1.0.0 | value | count | lower | `blind`, `death` | [`self_flashed` in `metrics/utility.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/utility.py) |

## Definition

Times the player blinded themselves for at least `flash.min_blind_s`.

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `flash.min_blind_s` | 1.0 s | Minimum blind duration for a blind to count as a flash (counts only; blind times keep every blind). |

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- Blinds of players already dead are ignored. Blind durations are the engine's, which already depend on the distance and the angle to the flash.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#35).
