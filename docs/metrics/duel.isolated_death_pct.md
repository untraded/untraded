# `duel.isolated_death_pct`: Isolated death %

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Reads | Code |
|---|---|---|---|---|
| 1.0.0 | value | pct | `death`, `round_player` | [`isolated_death_pct` in `metrics/duels.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/duels.py) |

## Definition

Isolated deaths ÷ deaths * 100.

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `trade.window_s` | 5.0 s | Trade window W: a death is traded when a teammate kills the killer within W seconds, the same tick included (HLTV and CS Demo Manager convention). |
| `isolation.radius` | 1000.0 units | An untraded death is isolated when the nearest living teammate is farther than this. 🎯 v0, to calibrate. |

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| 20 | 0 | 40 | 50 | 0 | 0 | 25 | 50 | 25 | 0 |

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- Distances are straight lines between positions, through walls: neither line of sight nor the navmesh path is taken into account (both come later).

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#33).
