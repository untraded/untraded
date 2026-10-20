# `eco.buy_type`: Buy type

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Better | Reads | Code |
|---|---|---|---|---|---|
| 1.0.0 | table | table | neutral | `team_round`, `round_player` | [`buy_type` in `metrics/economy.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/economy.py) |

## Definition

Rounds played per team buy type (`pistol`, `eco`, `semi`, `force`, `full`), with the % won. The buy type is also a split: `Dataset.split(buy=...)`. Columns: `steamid`, `buy_type`, `rounds`, `win_pct`.

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| player | buy_type | rounds | win_pct |
|---|---|---|---|
| A1 | force | 1 | 100 |
| A1 | full | 2 | 0 |
| A1 | pistol | 1 | 0 |
| A1 | semi | 1 | 0 |
| A2 | force | 1 | 100 |
| A2 | full | 2 | 0 |
| A2 | pistol | 1 | 0 |
| A2 | semi | 1 | 0 |

*First 8 of 40 rows.*

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- Buy types use v0 thresholds aligned with CS Demo Manager (`buy.eco_max`, `buy.full_min_ct`, `buy.full_min_t`), still to calibrate on our target level.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#36).
