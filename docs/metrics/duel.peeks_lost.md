# `duel.peeks_lost`: Peeks lost

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Better | Reads | Code |
|---|---|---|---|---|---|
| 1.0.0 | value | count | neutral | `death`, `kill`, `damage`, `blind` | [`peeks_lost` in `metrics/duels.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/duels.py) |

## Definition

Duels lost (`duel.duels_lost`) where, in the second before the death, the player had been at least `duel.peek_distance` from where they died: they peeked.

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `duel.sight_s` | 2.0 s | A death is a duel when the victim saw the killer (the engine's spotting) at most this long before. |
| `duel.peek_distance` | 64.0 units | A duel lost is a peek when, in the second before the death, the victim had been at least this far from where they died: a player holding an angle barely moves. |

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 2 | 1 | 1 | 3 | 0 | 0 | 0 | 2 | 1 |

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- Movement is the farthest sample from the death spot (a straight 3D line), read from positions sampled at 16 Hz: a quick jiggle can fall between two samples. A holder who has just repositioned, backed off, dropped from a box or been pushed by a molotov counts as moving. About half of the duels lost on the corpus.
- Distances are straight lines between positions, through walls: neither line of sight nor the navmesh path is taken into account (both come later).

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#168).
