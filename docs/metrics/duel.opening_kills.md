# `duel.opening_kills`: Opening kills

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Reads | Code |
|---|---|---|---|---|
| 1.0.0 | value | count | `round_player` | [`opening_kills` in `metrics/duels.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/duels.py) |

## Definition

Rounds where the player makes the opening kill (first enemy kill after freeze end).

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 1 | 1 | 0 | 0 | 0 | 1 | 1 | 0 | 1 |

## Against CS Demo Manager

Compared player by player on 30 matches (must be equal). Every remaining gap is a documented definition difference: see [validation-csdm.md](../validation-csdm.md).

## Limits

- A death by a fall or the world (no killer) is not an opening; the opening is the first kill by a player.
- Distances are straight lines between positions, through walls: neither line of sight nor the navmesh path is taken into account (both come later).

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#33).
