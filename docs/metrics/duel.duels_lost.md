# `duel.duels_lost`: Duels lost

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Better | Reads | Code |
|---|---|---|---|---|---|
| 1.0.0 | value | count | neutral | `death`, `kill`, `damage`, `blind` | [`duels_lost` in `metrics/duels.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/duels.py) |

## Definition

Deaths in a duel: killed by an enemy's gun (no grenade, fire, knife, zeus or bomb), not blind, having seen the killer (the engine's spotting) within `duel.sight_s` before.

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `duel.sight_s` | 2.0 s | A death is a duel when the victim saw the killer (the engine's spotting) at most this long before. |

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| 5 | 3 | 1 | 3 | 4 | 1 | 1 | 1 | 4 | 2 |

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- The sighting is the engine's spotting, sampled at 16 Hz: a duel the spotting missed is not counted, a death in the back never is. A death to a bot is never a duel: a bot has no steamid to spot.
- Distances are straight lines between positions, through walls: neither line of sight nor the navmesh path is taken into account (both come later).

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#167).
