# Calibration of the v0 thresholds (E9)

Seven thresholds of the v1 catalogue were v0 guesses, marked 🎯 in [metrics-v1](metrics-v1.md) and in the [parameters page](metrics/parameters.md). This page gives the method used for each one, the results on the corpus, and the decisions taken.

**Rule.** A suggestion is evidence for a decision, not a new default. A default only changes when the data **clearly** contradicts it, with a version bump of every metric that reads it ([ADR 0003](adr/0003-versioned-metric-registry.md)). Calibration only uses demos of consenting players at the target level ([ADR 0010](adr/0010-reference-data-and-corpus.md)).

## How to run it

```bash
untraded parse --mode premier --source valve --dates-from corpus/manifest.toml --out parsed/ demos/*.dem.bz2
untraded calibrate parsed/matches/*
```

The code is `untraded.calibration`. Each function measures what a threshold should separate and states its rule. `untraded calibrate` prints, in order: the buy profile with the least populated bucket between 500 and 2,500 $ and between 3,000 and 5,500 $, the traded share by distance to the nearest teammate with the suggested radius, the quantiles of the real trade distances, and the replication table of recurring spots.

## Results (20/10/2026)

- **Sample**: the 29 Premier matches of the corpus. That is 622 rounds and 4,552 deaths (3,926 of them with a living teammate) of 208 players, all from one maintainer's lobbies. The median Premier rating is 16,200, and half of the players are between 14,400 and 17,800.
- **Caveat**: one level of play and one group of maps. The calibration will be rerun on a wider corpus of consenting players before the hosted beta.

### Buy types: `buy.eco_max` = 1000 $, `buy.full_min_ct` = 4500 $, `buy.full_min_t` = 4000 $

- **Method**: team rounds outside pistol rounds, grouped by the team's average equipment value per player at freeze-time end + 7 s, in buckets of 250 $, with the win rate of each bucket. A threshold between two buy clusters belongs in a sparse bucket, and the win rate should change regime across it.
- **Result**:
  - Under 1,000 $, the win rate stays at 0 to 22 %.
  - From 1,000 to 3,000 $, it is 20 to 45 % on thin data (2 to 21 rounds per bucket).
  - From 3,000 $ on, it reaches **55 to 70 % on both sides**, already at the level of full buys.
  - The emptiest bucket between 500 and 2,500 $ is 1,750 to 2,000 $, on both sides.
- **Decision: kept.** A full buy is a **spending convention**: rifles, armour, helmet and utility, aligned with CS Demo Manager so the types can be compared. It is not a prediction of the round. Rounds between 3,000 $ and the full-buy threshold are well-armed partial buys, and the "semi" and "force" types describe them. The plateau from 3,000 $ is worth knowing for the future win-probability model, which uses the equipment value itself and not the type.

### `isolation.radius` = 1000 units

- **Method**: deaths by an enemy with a living teammate, grouped by the distance to the nearest teammate in buckets of 250 units, with the share traded within 5 s. The rule: the radius is where the traded share falls below half of its value at close range (under 500 units), since beyond it a teammate is too far to trade. Buckets of fewer than 20 deaths are ignored.
- **Result**:

  | Nearest teammate | Deaths | Traded |
  |---|---|---|
  | 0 to 250 u | 574 | 39 % |
  | 250 to 500 u | 856 | 27 % |
  | 500 to 750 u | 711 | 21 % |
  | 750 to 1,000 u | 613 | 15 % |
  | 1,000 to 1,250 u | 446 | 10 % |
  | 1,250 u and more | 726 | 0 to 3 % |

  The rule gives 750 units (15 % < 32 % / 2). The sharp break, below which trades still happen and beyond which they almost never do, is at 1,250 units.
- **Decision: kept at 1000.** The two readings frame the current value, so the data does not contradict it.

### `trade.opportunity_distance` = 1000 → **1300** units

- **Method**: for each death actually traded within 5 s, the distance from the trader to the killer at the moment of the death. An "opportunity" should cover most real trades: the rule is the 90th percentile.
- **Result**: 752 real trades. The median distance is 757 units, the 75th percentile 1,008, the **90th 1,302** and the 95th 1,444. With 1,000 units, **26 % of the real trades came from a teammate who had "no opportunity"**.
- **Decision: changed to 1,300 units.** The data clearly contradicts 1,000. The new versions are `trade.death_opportunities` 1.1.0, `trade.kill_opportunities` 1.1.0 and `trade.kill_conversion_pct` 1.2.0.

### `pos.recurring_death_share` = 0.25, `pos.recurring_min_rounds` = 8 → **32** rounds

- **Method**: a recurring death spot must be a habit, not chance. The test is replication.
  - A player's rounds on a map and side are split in two halves by parity, in match and round order.
  - A spot is recurring in a half when it holds at least the share of the half's untraded deaths (and at least 2 of them), on a half of at least N rounds.
  - **Precision** is the share of spots found in the first half that are also recurring in the second.
- **Result** (rounds per half):

  | Share | 6 | 8 | 12 | 16 |
  |---|---|---|---|---|
  | 0.20 | 14 % (222 spots) | 15 % (96) | 35 % (37) | 48 % (25) |
  | 0.25 | 11 % (213) | **8 % (87)** | 21 % (28) | 38 % (16) |
  | 0.33 | 10 % (185) | 7 % (59) | 21 % (19) | 33 % (12) |
  | 0.40 | 9 % (156) | 5 % (44) | 18 % (11) | 29 % (7) |

  With the v0 values (0.25 and 8 rounds), **8 %** of the spots come back: almost all are noise. Precision rises clearly with the number of rounds. The share matters less, and the differences between shares rest on few spots.
- **Decision**:
  - `pos.recurring_min_rounds` becomes **32**, that is 16 rounds per half, the best tested level. The data clearly contradicts 8 rounds. `pos.recurring_death_spot` goes to 1.2.0.
  - `pos.recurring_death_share` **stays at 0.25**: the gap with 0.20 rests on 16 against 25 spots.
  - A recurring spot now needs about two matches on the same map and side. That is the price of advice that holds.

## Next calibration

Rerun `untraded calibrate` once the corpus holds several levels of play and other consenting players. Then revisit the share of recurring spots and the buy types, which are the two results limited by the sample here.
