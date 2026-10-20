# `duel.nearest_teammate_at_death`: Spacing at death

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Better | Reads | Code |
|---|---|---|---|---|---|
| 1.0.0 | value | units | lower | `death` | [`nearest_teammate_at_death` in `metrics/duels.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/duels.py) |

## Definition

Median, over deaths with a living teammate, of the distance to the nearest one.

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| 329.45 | 210.76 | 1072.46 | 981.53 | 447.2 | 928.68 | 844.48 | 966.8 | 451.28 | 522.9 |

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- A median over the player's deaths with a living teammate: undefined without any.
- Distances are straight lines between positions, through walls: neither line of sight nor the navmesh path is taken into account (both come later).

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#33).
