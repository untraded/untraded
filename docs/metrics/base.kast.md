# `base.kast`: KAST

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Better | Reads | Code |
|---|---|---|---|---|---|
| 1.1.0 | value | pct | higher | `round_player` | [`kast` in `metrics/base.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/base.py) |

## Definition

% of rounds played where the player got a Kill, an Assist (flash assists excluded by default), Survived (alive at round end, no death after it), or was Traded (death traded within `trade.window_s`).

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `trade.window_s` | 5.0 s | Trade window W: a death is traded when a teammate kills the killer within W seconds, both ends included (the same tick, and exactly W). 5 s is the usual convention (HLTV, CS Demo Manager); CS Demo Manager excludes exactly W. |
| `kast.count_flash_assist` | false | Whether a flash assist alone makes a round count for KAST. |

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| 40 | 80 | 60 | 60 | 80 | 100 | 60 | 80 | 40 | 100 |

## Against CS Demo Manager

Compared player by player on 30 matches, against a 1 % tolerance. The values that differ are counted and explained, each by a documented definition difference, in [validation-csdm.md](../validation-csdm.md).

## Limits

- Differs from CS Demo Manager by design. CS Demo Manager counts a round the player missed as survived, a player killed by a teammate as surviving, a flash-only assist, and a trade by the killer's own teammate; Untraded counts none of them (validation-csdm § 1, § 4 and § 5).
- Flash assists do not count by default (`kast.count_flash_assist`).

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#32).
- **1.1.0**: A death after the round end is not a survival (#43), as in CS Demo Manager. Trades now count a kill on the same tick (delay 0) (#41) and the victim's own grenade or fire killing the killer later (#42); two players killing each other on the same tick trade nothing.
