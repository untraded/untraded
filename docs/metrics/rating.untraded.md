# `rating.untraded`: Untraded Rating

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Better | Reads | Code |
|---|---|---|---|---|---|
| 2.0.0 | value | ratio | higher | `ledger`, `round_player` | [`untraded` in `metrics/ratings.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/ratings.py) |

## Definition

The match rating: 1 + credit / s, the credit being the player's ledger credit per round played (docs/winprob.md: every change of the round's win probability credited, the hold left out and each round recentred so that its players average zero), in percentage points. s is the credit worth 1.00, chosen so that the rating spreads over the corpus's player-matches as HLTV 1.0 does (`rating-v2.json`): 1.00 is the average player of the match, a 1.20 reads as at HLTV. What the player's actions were worth; `rating.untraded_level` says what the player is worth. Beta: measured on 54 high-level matches.

Stands on the rounds played: a value over few cases says little.

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| 0.37 | 1.05 | 1.33 | 0.9 | 0.52 | 3.1 | 0.37 | 1.14 | -0.07 | 1.27 |

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- Beta: the scale is measured on a small corpus of high-level matches (docs/winprob.md). A new model or a larger corpus gives a new scale, which bumps this metric's version.
- Read it with its margin (`rating.untraded_margin`): over one match, it is wide.
- What the player's actions were worth in the match, noisy over one match: for what the player is worth, read `rating.untraded_level`.
- Ratings summarize; they hide what the other metrics explain. Read them with KAST, ADR and the duels.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version, the beta of the open rating (#137).
- **2.0.0**: The Untraded Rating 2.0: the ledger's credit per round (every change of the round's win probability credited, the hold left out), on a scale fitted on 54 matches (s = 15.31); the average player of a match is 1.00 by construction (#153 to #157).
