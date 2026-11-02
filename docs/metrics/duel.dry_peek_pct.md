# `duel.dry_peek_pct`: Peeks without the flash

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Better | Reads | Code |
|---|---|---|---|---|---|
| 1.0.0 | value | pct | lower | `death`, `kill`, `damage`, `blind` | [`dry_peek_pct` in `metrics/duels.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/duels.py) |

## Definition

Peeks lost with a flash still in the inventory ÷ peeks lost * 100: the flash that could have gone first.

Stands on [`duel.peeks_lost`](duel.peeks_lost.md): a value over few cases says little.

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `duel.sight_s` | 2.0 s | A death is a duel when the victim saw the killer (the engine's spotting) at most this long before. |
| `duel.peek_distance` | 64.0 units | A duel lost is a peek when, in the second before the death, the victim had been at least this far from where they died: a player holding an angle barely moves. |

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| A1 | A2 | A3 | A4 | A5 | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 100 | 0 | 100 | 0 | — | — | — | 50 | 0 |

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- Only the player's own flash counts: a peek behind a teammate's flash still counts as dry when the player kept theirs. A second flash kept after throwing the first, or a flash in hand when the player was killed mid-throw, also counts as held. Peeks won are not seen.
- Distances are straight lines between positions, through walls: neither line of sight nor the navmesh path is taken into account (both come later).

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#168).
