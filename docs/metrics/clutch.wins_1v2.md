# `clutch.wins_1v2`: 1v2 wins

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Reads | Code |
|---|---|---|---|---|
| 1.0.0 | value | count | `clutch` | [`wins` in `metrics/duels.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/duels.py) |

## Definition

1v2 clutches the team wins.

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Against CS Demo Manager

Compared player by player on 30 matches (must be equal). Every remaining gap is a documented definition difference: see [validation-csdm.md](../validation-csdm.md).

## Limits

- Kills after the round end (exit frags) are ignored, so no clutch starts after it.
- The enemies are those present in the round: a missing player is not counted.
- When the last two players of a team die on the same tick, nobody clutched.
- A win is a round the clutcher's team wins, whether or not the clutcher survives.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#33).
