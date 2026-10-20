# `rating.hltv1`: HLTV Rating 1.0

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Reads | Code |
|---|---|---|---|---|
| 1.0.0 | value | ratio | `round_player` | [`hltv1` in `metrics/ratings.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/ratings.py) |

## Definition

(KillRating + 0.7 * SurvivalRating + MultiKillRating) / 2.7, each component being the player's per-round value over HLTV's reference average (KPR 0.679, survival 0.317, multi-kill points 1.277, with N² points for a round of N kills). Public formula.

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| 0.17 | 0.66 | 1.07 | 0.95 | 1.18 | 2.64 | 0.95 | 1.23 | 0.33 | 1.18 |

## Against CS Demo Manager

Compared player by player on 30 matches, against a 1 % tolerance. The values that differ are counted and explained, each by a documented definition difference, in [validation-csdm.md](../validation-csdm.md).

## Limits

- HLTV's reference averages date from the CS:GO 1.0 era and were not recomputed for CS2. The formula is public and exact; it is checked against independent calculations.
- Ratings summarize; they hide what the other metrics explain. Read them with KAST, ADR and the duels.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#37).
