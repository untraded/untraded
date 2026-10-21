# `base.survival_pct`: Survival

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Better | Reads | Code |
|---|---|---|---|---|---|
| 1.1.0 | value | pct | higher | `round_player` | [`survival_pct` in `metrics/base.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/base.py) |

## Definition

% of rounds where the player is alive at round end and does not die after it (a death after the round end drops the weapons).

Stands on the rounds played: a value over few cases says little.

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 20 | 0 | 20 | 0 | 60 | 20 | 20 | 20 | 20 |

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- A player alive at the round end who dies after it (an exit frag) did not survive: the weapons are lost.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#32).
- **1.1.0**: A death after the round end is not a survival: the weapons are lost (#43).
