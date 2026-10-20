# `clutch.win_pct`: Clutch success

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Reads | Code |
|---|---|---|---|---|
| 1.0.0 | value | pct | `clutch` | [`clutch_win_pct` in `metrics/duels.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/duels.py) |

## Definition

Clutch wins ÷ clutch attempts * 100, over all N.

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| — | 0 | 0 | — | 0 | 100 | — | — | 0 | — |

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- Undefined (empty) for a player without clutch attempts.
- Kills after the round end (exit frags) are ignored, so no clutch starts after it.
- The enemies are those present in the round: a missing player is not counted.
- When the last two players of a team die on the same tick, nobody clutched.
- A win is a round the clutcher's team wins, whether or not the clutcher survives.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#33).
