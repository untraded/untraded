# `trade.traded_death_pct`: Traded death % (5 s)

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Reads | Code |
|---|---|---|---|---|
| 1.0.0 | value | pct | `death`, `round_player` | [`traded_death_pct` in `metrics/duels.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/duels.py) |

## Definition

Traded deaths ÷ deaths * 100.

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `trade.window_s` | 5.0 s | Trade window W: a death is traded when a teammate kills the killer within W seconds, the same tick included (HLTV and CS Demo Manager convention). |

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| 20 | 25 | 20 | 0 | 40 | 50 | 25 | 0 | 0 | 50 |

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- A death is traded only when the killer is then killed **by the victim's team**, within `trade.window_s` and the same tick included. A killer killed by their own teammate does not trade it, unlike CS Demo Manager.
- Distances are straight lines between positions, through walls.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#33).
