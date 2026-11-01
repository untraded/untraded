# `rating.untraded_level`: Untraded Rating level

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Better | Reads | Code |
|---|---|---|---|---|---|
| 1.0.0 | value | ratio | higher | `ledger`, `round_player` | [`untraded_level` in `metrics/ratings.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/ratings.py) |

## Definition

The level: what the player is worth, on the scale of `rating.untraded` (1.00 = the average player). A ridge regression of the ledger's credit on kills, deaths and damage per round, trained to predict the credit of rounds it has not seen (`rating-v2.json`), centred on each match's players; the ledger's credit then corrects it by n / (n + k) as rounds add up (on 54 matches the box alone predicted best, so k is not set yet and the level is the box). Closer to 1.00 than the match rating, as an estimate should be. Over several matches, the round-weighted average of each match's level.

Stands on the rounds played: a value over few cases says little.

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| 0.77 | 0.98 | 1.03 | 0.98 | 0.98 | 1.35 | 0.91 | 1.16 | 0.84 | 1.01 |

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- Beta: fitted on 54 high-level matches (docs/winprob.md). Over one match it is the box score's prediction; how fast the ledger should take over across matches is not measured yet.
- Closer to 1.00 than the match rating by design: it is the match rating to expect.
- Ratings summarize; they hide what the other metrics explain. Read them with KAST, ADR and the duels.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version, with the Untraded Rating 2.0 (#157).
