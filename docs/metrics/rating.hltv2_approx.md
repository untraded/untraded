# `rating.hltv2_approx`: HLTV 2.0 (approx.)

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Better | Reads | Code |
|---|---|---|---|---|---|
| 1.1.0 | value | ratio | higher | `round_player` | [`hltv2_approx` in `metrics/ratings.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/ratings.py) |

## Definition

Community approximation, **always labeled approx.**: 0.0073 * KAST + 0.3591 * KPR - 0.5329 * DPR + 0.2372 * Impact + 0.0032 * ADR + 0.1587, with Impact = 2.13 * KPR + 0.42 * APR - 0.41 and KAST in % (`base.kast`, same parameters). Its error against HLTV's published values is not known.

Stands on the rounds played: a value over few cases says little.

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `trade.window_s` | 5.0 s | Trade window W: a death is traded when a teammate kills the killer within W seconds, both ends included (the same tick, and exactly W). 5 s is the usual convention (HLTV, CS Demo Manager); CS Demo Manager excludes exactly W. |
| `kast.count_flash_assist` | false | Whether a flash assist alone makes a round count for KAST. |

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| 0.12 | 1.03 | 1.25 | 1.05 | 1.28 | 2.45 | 0.9 | 1.62 | 0.25 | 1.4 |

## Against CS Demo Manager

Compared player by player on 30 matches, against a 1 % tolerance. The values that differ are counted and explained, each by a documented definition difference, in [validation-csdm.md](../validation-csdm.md).

## Limits

- A community approximation of a formula HLTV does not publish: no error margin against HLTV's own values is known. Always label it approx.
- Can be negative; CS Demo Manager floors it at 0.
- Ratings summarize; they hide what the other metrics explain. Read them with KAST, ADR and the duels.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#37).
- **1.1.0**: Follows `base.kast` 1.1.0 (#41, #42, #43).
