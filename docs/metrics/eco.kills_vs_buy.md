# `eco.kills_vs_buy`: Kills by economy

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Better | Reads | Code |
|---|---|---|---|---|---|
| 1.0.0 | table | table | neutral | `death`, `kill`, `inventory_change` | [`kills_vs_buy` in `metrics/economy.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/economy.py) |

## Definition

The player's enemy kills per (killer weapon class, victim weapon class). The class is the best weapon held: `awp`, `rifle` (other snipers included), `heavy` (shotguns and machine guns), `smg`, else `pistol`. The killer's inventory is the last change before the kill, the victim's is read at the kill. Columns: `steamid`, `killer_class`, `victim_class`, `kills`.

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| player | killer_class | victim_class | kills |
|---|---|---|---|
| A1 | rifle | rifle | 1 |
| A2 | pistol | pistol | 1 |
| A2 | pistol | smg | 1 |
| A2 | rifle | awp | 1 |
| A3 | pistol | pistol | 3 |
| A3 | pistol | rifle | 1 |
| A3 | rifle | rifle | 1 |
| A4 | rifle | pistol | 1 |

*First 8 of 26 rows.*

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- The class is the best weapon held, not the weapon used: a rifle holder killing with a pistol is a `rifle` kill.
- Buy types use thresholds aligned with CS Demo Manager (`buy.eco_max`, `buy.full_min_ct`, `buy.full_min_t`): a spending convention, checked on the corpus and kept (docs/calibration.md).

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#36).
