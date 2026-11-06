# `trade.slow_trade_pct`: Slow trades

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Better | Reads | Code |
|---|---|---|---|---|---|
| 1.0.0 | value | pct | lower | `death` | [`slow_trade_pct` in `metrics/duels.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/duels.py) |

## Definition

Trade kills that took longer than `trade.window_w3_s` ÷ trade kills (within `trade.window_s`) * 100.

Stands on [`trade.trade_kills`](trade.trade_kills.md): a value over few cases says little.

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `trade.window_s` | 5.0 s | Trade window W: a death is traded when a teammate kills the killer within W seconds, both ends included (the same tick, and exactly W). 5 s is the usual convention (HLTV, CS Demo Manager); CS Demo Manager excludes exactly W. |
| `trade.window_w3_s` | 3.0 s | Shorter trade window of the `_w3` variants, for tighter trades. |

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| — | — | 0 | 0 | — | 50 | — | 0 | — | — |

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- A death is traded only when the killer is then killed **by the victim's team**, within `trade.window_s`, both ends included. CS Demo Manager differs in four ways: a killer killed by their own teammate trades the death, a player controlling a bot can trade, the kill of an enemy who had just killed a teammate is a trade kill, and a trade at exactly 5.00 s does not count (validation-csdm § 5).
- Distances are straight lines between positions, through walls.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#33).
