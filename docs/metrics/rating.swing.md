# `rating.swing`: Win-probability swing

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Better | Reads | Code |
|---|---|---|---|---|---|
| 1.1.0 | value | pct | higher | `swing`, `round_player` | [`swing` in `metrics/ratings.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/ratings.py) |

## Definition

The player's swings (`swing` table: how much each of their kills, deaths, plants and defuses moved their team's chance of winning the round, by the open win-probability model 1.0, docs/winprob.md), summed and divided by the rounds played, in percentage points. 0 is a player whose actions moved nothing on balance.

Stands on the rounds played: a value over few cases says little.

Can be negative: compare it in units, never in % of a reference.

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| -5.64 | 6.87 | 4.93 | 2.09 | -8.57 | 23.24 | -10.6 | 7.73 | -12.05 | 2.93 |

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- The model is trained on a small corpus of high-level matches (docs/winprob.md): its numbers move with each new model version, which bumps this metric's version.
- The death of a bot is not credited.
- Ratings summarize; they hide what the other metrics explain. Read them with KAST, ADR and the duels.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version, with the win-probability model 1.0 (#125).
- **1.1.0**: Nothing is credited once the round is decided: a death to the bomb's explosion debited its victim (#126).
