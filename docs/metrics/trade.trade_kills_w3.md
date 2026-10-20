# `trade.trade_kills_w3`: Trade kills (3 s)

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Reads | Code |
|---|---|---|---|---|
| 1.0.0 | value | count | `death` | [`trade_kills` in `metrics/duels.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/duels.py) |

## Definition

Kills of an enemy who killed a teammate of the player within `trade.window_w3_s` before.

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `trade.window_w3_s` | 3.0 s | Shorter trade window of the `_w3` variants, for tighter trades. |

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 0 | 1 | 3 | 0 | 1 | 0 | 1 | 0 | 0 |

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- A death is traded only when the killer is then killed **by the victim's team**, within `trade.window_s` and the same tick included. A killer killed by their own teammate does not trade it, unlike CS Demo Manager.
- Distances are straight lines between positions, through walls.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#33).
