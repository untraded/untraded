# `duel.lost_without_damage_pct`: Duels lost without damage

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Better | Reads | Code |
|---|---|---|---|---|---|
| 1.0.0 | value | pct | lower | `death`, `kill`, `damage`, `blind` | [`lost_without_damage_pct` in `metrics/duels.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/duels.py) |

## Definition

Duels lost where the player had not hurt the killer in the round ÷ duels lost * 100.

Stands on [`duel.duels_lost`](duel.duels_lost.md): a value over few cases says little.

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `duel.sight_s` | 2.0 s | A death is a duel when the victim saw the killer (the engine's spotting) at most this long before. |

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| 40 | 33.33 | 0 | 66.67 | 25 | 100 | 100 | 0 | 50 | 0 |

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- Damage to the killer earlier in the round counts, even in an earlier duel. About half of the duels lost on the corpus: compare it with the player's own reference.
- Distances are straight lines between positions, through walls: neither line of sight nor the navmesh path is taken into account (both come later).

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#167).
