# `team.trades`: Trade network

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

| Version | Kind | Unit | Better | Reads | Code |
|---|---|---|---|---|---|
| 1.0.0 | team | table | higher | `death`, `round_player`, `round` | [`trades` in `metrics/team.py`](https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded/metrics/team.py) |

## Definition

Who trades whose death. For each player of the team (`key`, a SteamID): their deaths (`cases`, every death as in `trade.traded_death_pct`, in the rounds with a known winner) and the deaths traded within `trade.window_s` (`hits`), in total (`sub_key` empty) and by the teammate who traded them (`sub_key`, a SteamID). A death is traded when a teammate kills the killer within the window (the `death` table, built from `kill`).

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `trade.window_s` | 5.0 s | Trade window W: a death is traded when a teammate kills the killer within W seconds, both ends included (the same tick, and exactly W). 5 s is the usual convention (HLTV, CS Demo Manager); CS Demo Manager excludes exactly W. |

## Example

On the `premier-half` fixture: a Premier match on de_cache, rounds 11 to 15, anonymized players.

| team | key | sub_key | cases | hits |
|---|---|---|---|---|
| A | A1 |  | 5 | 1 |
| A | A1 | A3 | 5 | 1 |
| A | A2 |  | 4 | 1 |
| A | A2 | A4 | 4 | 1 |
| A | A3 |  | 5 | 1 |
| A | A3 | A4 | 5 | 1 |
| A | A4 |  | 4 | 0 |
| A | A5 |  | 5 | 2 |

*First 8 of 18 rows.*

## Against CS Demo Manager

No equivalent in CS Demo Manager.

## Limits

- A player can trade their own death: their grenade or fire kills the killer within the window. That link is kept.
- A bot of the team that trades a death adds to the total but links no player.
- One side of a match (`A` started on CT, `B` on T), not a team: which side is a team's is decided when the numbers are read (3 players of its roster on the match's date, on the same side), so a team's numbers only cover the matches where that rule finds it.
- Counts, not rates: a rate over several matches adds their counts up (hits ÷ cases over all their rounds), never averages the matches' rates.
- Only rounds whose winner is known count (a last round cut by the end of the demo is left out); overtime rounds count like the others.
- Team samples are small: read every rate with its number of cases.

See also the [shared conventions](README.md#shared-conventions) of every metric.

## History

- **1.0.0**: First version (#210).
