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

### Trade opportunities: the sighting (02/11/2026)

- **Problem**: distance alone counts a teammate behind a wall. In production, the advice listed up to 63 "missed trades" in an 80-round session, nearly one a round.
- **Method**: the 42 matches parsed on hand (corpus and inbox). For every opportunity within 1,300 units, whether the teammate spotted the killer (`player_tick.spotted_by`, the engine's radar visibility, sampled at 16 Hz) within 5 s of the kill, both alive.
- **Result**:
  - 7,010 opportunities within 1,300 units, 954 of them converted: **13.6 %**;
  - the teammate saw the killer in 1,786 of them; 80 % of the real trades are among them, and the rest (188) are trades the spotting missed, since it can lag behind a quick trade;
  - with a sighting or a trade, 1,974 opportunities, converted at **48 %**.
- **Decision**: an opportunity needs the sighting, or the trade itself (#167). The new versions are `trade.kill_opportunities` 1.2.0, `trade.death_opportunities` 1.2.0 and `trade.kill_conversion_pct` 1.3.0.

### Wasted utility: the dry peek (02/11/2026)

- **Problem**: the rule listed every death with a grenade in the inventory. Half of all deaths qualify, so the rule was the first priority in 14 of the 34 sessions on hand, with up to 51 deaths to review, most of them nothing a player could act on (a CT keeping a molotov for the retake, a death in the back).
- **Method**: the 47 matches parsed on hand. For every enemy death with a grenade (3,632), whether it was a duel lost (`duel.duels_lost`), whether a flash was held, and how far the victim had been from the death spot in the second before (`player_tick` positions, 16 Hz).
- **Result**:
  - movement in the second before a duel lost: median 60 units, 75th percentile 104; a player holding an angle barely moves, one peeking covers ground;
  - at 64 units, 48 % of the duels lost are peeks; with a flash still held, 557 deaths, 15 % of the deaths with grenades, about 1.2 per player and match.
- **Decision**: the rule watches the share of peeks lost with a flash held (`duel.dry_peek_pct`, ⚙ `duel.peek_distance` = 64 units), not the value at death (#168). `util.unused_value_at_death` is unchanged. On the 34 sessions, the rule now fires in 7 (17 before), with 3 to 6 peeks, and leads 3.

### When a rule fires: chance (06/11/2026)

- **Problem**: a gap of 15 % and 3 events decide a finding, whatever the number of cases. How much of it is noise?
- **Method**: a one-off script, not in `untraded.calibration`. 5 players with at least 8 matches, 46 matches. 400 times per player, 2 to 4 of their own matches drawn at random are a session and the others its reference: their play did not change on purpose, so what fires is ordinary variation between matches. The same counts on their 34 real sessions, each against its earlier matches (at least 5). Pattern rules are left out, and neither column keeps the 30-day window. The draws overlap and the players are few: the rates are orders of magnitude, and thresholds close to each other are not told apart.
- **Result**, findings per session (9 comparing rules, before the team flash thresholds below):

  | Trigger | Random sessions | Real sessions |
  |---|---:|---:|
  | Gap and events only | 2.56 | 2.53 |
  | and chance < 0.2 | 1.36 | 1.38 |
  | and chance < 0.1 | 0.70 | 0.65 |
  | and chance < 0.05 | 0.37 | 0.41 |

  Below 0.05, each rule fires 1 to 5 % of the time on noise, as expected: the test holds, except for team flashes (14 %). Counting a flash once brings them to 9 %; thresholds of 0.1 and 0.02 bring them to 13 % and 6 %, like the other rules at 0.2 and 0.05.
- **Reading**: real sessions do not stand out from random ones at any threshold. Against the player's own days, a session rarely differs from their habits. Taken at face value, most findings, clear signals included, are no more frequent than this ordinary variation.
- **Decision**: two levels, `advice.max_chance` = 0.2 and `advice.strong_chance` = 0.05, with 0.1 and 0.02 for team flashes. The gap and the minimum of events stay. **Limits**: the self comparison cannot see a lasting habit, since it is in the reference; level references are not tested; and the correction for a flash uses the session's own ratio of blinds per flash.

### Rules of batch 2: which ones stay (07/11/2026)

- **Problem**: seven candidates, each a count of bad cases so the chance test can read it. Which ones hold, and at which thresholds?
- **Method**: a one-off script, the same as above: 5 players, 47 matches parsed, 300 random sessions per player, 34 real sessions. Few players again: orders of magnitude.
- **Result**, share of random sessions that fire, then number of real sessions that fire, at each threshold:

  | Candidate | Rate over the corpus | < 0.2 | < 0.1 | < 0.05 | < 0.01 | < 0.005 |
  |---|---:|---:|---:|---:|---:|---:|
  | Rounds without impact | 29 % | 17.9 %, 6 | 10.3 %, 4 | 5.8 %, 1 | 2.5 %, 0 | 1.3 %, 0 |
  | Slow trades | 28 % | 14.0 %, 2 | 7.4 %, 2 | 4.4 %, 2 | 0.8 %, 0 | 0.4 %, 0 |
  | Self-flashes | 0.05 per round | 16.3 %, 8 | 12.0 %, 6 | 8.3 %, 5 | 5.1 %, 5 | 3.9 %, 3 |
  | Flashes on nobody | 56 % | 16.9 %, 4 | 10.8 %, 3 | 6.5 %, 2 | 1.5 %, 0 | 0.5 %, 0 |
  | Flashes never followed up | 87 % | 3.1 %, 0 | 0.7 %, 0 | 0.3 %, 0 | 0 %, 0 | 0 %, 0 |
  | HE on teammates | 0.008 per round | 0.5 %, 0 | 0.5 %, 0 | 0.5 %, 0 | 0.5 %, 0 | 0.2 %, 0 |
  | Grenades never thrown | 16 % | 23.5 %, 10 | 16.7 %, 7 | 11.9 %, 6 | 6.1 %, 3 | 4.6 %, 2 |

- **Reading**: a flash that blinds an enemy and leads to no kill is the normal case (87 %), so it says little about a mistake: this candidate is dropped. Self-flashes and grenades never thrown vary more than the model expects. Self-flashes are the first rule to stand out from noise on real sessions (5 of 34, or 15 %, against 5 % below 0.01), on few sessions.
- **Decision**: the default thresholds, except self-flashes (0.1 and 0.01) and grenades never thrown (0.05 and 0.005). HE on teammates never fired on a real session here, and stays: it costs no noise, and it says something when it happens. These counts use the rate of the earlier matches; the engine compares percentages by the median of per-match values, so it fires somewhat less.
- **Effect** on the 34 real sessions, compared with batch 1: findings per session 1.85 → 2.47, priorities 1.71 → 2.00, sessions with no priority 3 → 1, priorities changed in 14. At that point a clear signal still came first; see the next section.

### Order of the priorities: cost alone

- **Problem**: a clear signal came first whatever it cost. One report put 11 rounds of self-flashes, 3 of them lost, ahead of 19 duels lost without damage, 17 of them lost. How rare a gap is says how sure a finding is, not how much it matters.
- **Method**: the three orders compared on the same 34 real sessions, 5 players and 47 matches.

  | Order | Rounds lost, first priority (mean) | Rounds lost, all priorities | Sessions where a priority loses fewer rounds than a later one | Clear signals among the priorities (of 22 found) |
  |---|---:|---:|---:|---:|
  | Clear signals, then cost | 5.97 | 350 | 5 | 21 |
  | **Cost** | **8.15** | **376** | **0** | **19** |
  | Rounds lost, then cost | 8.15 | 378 | 0 | not counted |

- **Reading**: cost and rounds lost give the same order in 33 sessions of 34. Cost also keeps the weight of won rounds that the rest of the engine uses.
- **Decision**: cost alone, and the clear signal stays a mark on the finding. The order changes in 7 sessions, always at the first priority; the set of priorities changes in 1.
- **Limits**: in that session, 2 clear signals leave the priorities and stay among the other points, with their mark. A round is not yet weighed by what it cost in the ledger. 34 sessions from 5 players are few.

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
