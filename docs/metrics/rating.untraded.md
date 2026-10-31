# `rating.untraded`: Untraded Rating

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Better | Reads | Code |
|---|---|---|---|---|---|
| 1.0.0 | value | ratio | higher | `swing`, `round_player` | [`untraded` in `metrics/ratings.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/ratings.py) |

## Definition

1 + (swing per round - m) / k, the swing per round being `rating.swing`. m is the corpus's swing per round (all rounds pooled): the average player rates 1.00. k is the swing worth 1.00, chosen so that the rating spreads over the corpus's player-matches as HLTV 1.0 does. Both are published with the win-probability model (`rating-v1.json`, docs/winprob.md). Beta: measured on a small corpus of high-level matches.

Stands on the rounds played: a value over few cases says little.

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| 0.53 | 1.5 | 1.35 | 1.13 | 0.3 | 2.77 | 0.14 | 1.56 | 0.03 | 1.19 |

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- Beta: the scale is measured on a small corpus of high-level matches (docs/winprob.md). A new model or a larger corpus gives a new scale, which bumps this metric's version.
- Read it with its margin (`rating.untraded_margin`): over one match, it is wide.
- Ratings summarize; they hide what the other metrics explain. Read them with KAST, ADR and the duels.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version, the beta of the open rating (#137).
