<!--
SPDX-FileCopyrightText: 2026 The Untraded Authors
SPDX-License-Identifier: AGPL-3.0-only
-->

# Round win probability

Untraded's open rating rests on one question: **at this moment of the round, how likely are the counter-terrorists to win it?** The model that answers it is public: its inputs, its coefficients and its scores are all in this repository (`untraded.winprob`, MIT). HLTV 3.0 and Leetify also rate players from win-probability swings, but they do not publish their tables. Ours can be checked and refitted by anyone.

## What the model sees

One sample per second of play, from the end of freeze time, seen by the counter-terrorists (`untraded.winprob.features`):

| Input | Unit |
|---|---|
| `alive_ct`, `alive_t` | players alive on each side |
| `hp_ct`, `hp_t` | health of the living, in hundreds of points |
| `armor_ct`, `armor_t` | armor of the living, in hundreds of points |
| `equip_ct`, `equip_t` | equipment value of the living, in thousands of $ |
| `kits` | living counter-terrorists with a defuse kit |
| `planted` | 1 once the bomb is down |
| `time_left` | before the plant: round time left (1:55 from freeze-time end), in tens of seconds; 0 once the bomb is down |
| `time_left_planted` | once the bomb is down: bomb time left (40 s from the plant), in tens of seconds; 0 before |
| `alive_ct_planted`, `alive_t_planted` | players alive on each side once the bomb is down, 0 before |
| `map=<name>` | one per map, against a baseline map: the first in alphabetical order (`de_ancient` in version 1.0). A map the model has not seen counts as the baseline |

**Which samples are kept:**
- only rounds with a winner that end by elimination, the bomb's explosion, a defuse or the time running out;
- a sample is kept while the round is still open: both sides have someone alive, or only the counter-terrorists do while the bomb is down (they can still defuse);
- nothing is kept after a defuse, an explosion or the round's end;
- the target is whether the counter-terrorists win the round.

**What is left out, on purpose:**
- **Positions**: too many parameters for the data we have yet.
- **Player skill**: a 2026 study found that it does not help on newer matches ([CS2_Win_Probability_Model](https://github.com/Henry1145141919810/CS2_Win_Probability_Model)).

## The model

A **logistic regression**, small enough to be published as coefficients (`untraded.winprob.model`):

- **Fitting**: Newton's method, with an L2 penalty on standardized inputs.
- **Weights**: every round weighs the same, whatever its length (its samples share a weight of 1).
- **Common-sense signs**:
  - one more player, more health, armor, equipment or kits never lowers a side's chances;
  - a coefficient that comes out on the wrong side is dropped, and the model refitted without it.
- **Maps** shift the odds; the rest of the game's rules is shared by every map.
- **Training data**: demos of **consenting players** only, at Untraded's target level (Premier and FACEIT). **Nothing from professional demos** goes in, because their terms forbid it (ADR 0010): `untraded winprob train` leaves out every match parsed with `--mode pro`.

The published model is `packages/untraded-py/src/untraded/winprob/winprob-v1.json`. It holds:
- the coefficients;
- the means and scales of the inputs;
- what it was trained on (matches, rounds, dates, maps), with no match ids;
- the scores below.

A gradient-boosted model will be tried once the corpus reaches about 300 matches, and kept only if it beats the logistic regression on held-out matches by more than 0.01 of log loss, with an interval that excludes zero.

## How good it is

**How it is scored** (`untraded.winprob.validation`):
- the **newest matches are held out** (30 %), as the model always predicts matches played after its training;
- every score weighs each round the same;
- two baselines frame the numbers: the counter-terrorists' win rate alone, and a model that only knows how many players each side has alive;
- the scores are reported overall, before and after the plant, with a calibration table (predicted against observed, by tenths).

**Version 1.0** (trained 2026-10-26): 30 matches, 645 rounds and 44,841 samples from Premier and FACEIT demos played between 2026-10-10 and 2026-10-19, on 7 maps. The 9 newest matches (193 rounds) were held out:

| On held-out matches | AUC (higher is better) | Brier (lower is better) | Log loss (lower is better) |
|---|---|---|---|
| **The model** | **0.867** | **0.149** | **0.453** |
| Players alive only | 0.838 | 0.159 | 0.477 |
| Counter-terrorist win rate only | 0.500 | 0.250 | 0.694 |
| The model, before the plant | 0.832 | 0.166 | 0.501 |
| The model, after the plant | 0.956 | 0.075 | 0.243 |

**Calibration**: when the model says 15 %, the counter-terrorists won 15 % of those rounds; the widest gap is at 70–80 % (75 % predicted, 84 % observed, on 16 rounds). The full table is in the model file (`validation.calibration`).

With 30 matches the numbers move from one corpus to the next: a first fit on 10 matches scored an AUC of 0.80. Each new version is trained on a larger corpus and its scores are published here.

The published model is then refitted on every match, held-out ones included.

## Model 2 (in progress)

Model 2 adds candidate inputs to model 1's. **Each family joins only if it earns its place on the corpus**, so the model grows with the data instead of overfitting it.

| Family | Inputs (per side unless noted) |
|---|---|
| `defuse_race` | `defuse_margin`: once the bomb is down, bomb time left minus the time the quickest living counter-terrorist needs to reach it (straight-line distance at 250 units/s) and defuse it (5 s with a kit, 10 s without), clipped to ±20 s, in tens of seconds; 0 before the plant |
| `clock_bends` | `time_left_over_30s`, `time_left_over_60s`: `max(0, time_left − bend)`, so the clock's weight can change through the round |
| `weapons` | AWPs, rifles and other primaries carried by the living (`awp_*`, `rifles_*`, `smgs_*`) |
| `grenades` | smokes, flashes, molotovs and HE grenades carried by the living (`smokes_*`, `flashes_*`, `fires_*`, `hes_*`) |

The counts come from each player's last inventory change (`inventory_change`). Weapons, grenades and the defuse race have common-sense signs, like model 1's inputs.

**How a family earns its place** (`untraded.winprob.validation.select_features`):
- **Cross-fitting**: every match is predicted by a model fitted without it (5 groups of matches, assigned by a hash of the match id).
- **Forward selection**: at each step, the family that lowers the cross-fitted log loss most joins, if the 95 % interval of its gain is above zero. The interval comes from resampling **matches** (1,000 draws), because the states of one match are not independent. The selection stops when no family qualifies.
- **No leak into the scores**: for the held-out scores, the families are chosen on the training matches alone. The published model's choice is then made on every match, and each step is recorded in the model file (`validation.selection`).

**Every model is now scored** on top of the table above:
- on **contested states**: as many players alive on each side, equipment within $1,500. That is where the alive count alone says nothing;
- with **Murphy's decomposition** of the Brier score: reliability (calibration), resolution, uncertainty;
- against **model 1's inputs fitted on the same matches**, with the log loss gain and its 95 % interval (bootstrap by match);
- with a **learning curve**: the held-out scores of the model fitted on the oldest 25, 50, 75 and 100 % of the training matches. Where it flattens, more matches stop paying.

`untraded.winprob.cross_fit` also serves the swing: the swings of the corpus's own matches must come from a model that did not see them, or its overfitting inflates them.

**First run, on the 30 matches of version 1.0** (2026-11-01):

| Family | Log loss gain, cross-fitted (95 % interval) | Kept |
|---|---|---|
| `defuse_race` | +0.0016 (+0.0004 to +0.0029) | yes |
| `clock_bends` | −0.0001 (−0.0005 to +0.0002) | no |
| `weapons` | −0.0048 (−0.0105 to +0.0004) | no |
| `grenades` | −0.0005 (−0.0015 to +0.0006) | no |

- On the 21 training matches alone, no family qualifies, so the held-out scores are model 1's (log loss 0.453).
- On contested states the model barely beats a coin: AUC 0.62, log loss 0.677. The CS2 literature reports the same, about 0.58 ([CS2_Win_Probability_Model](https://github.com/Henry1145141919810/CS2_Win_Probability_Model)).
- The learning curve still falls up to 16 training matches (log loss 0.473, 0.462, 0.453, 0.453 for 5, 10, 16, 21).
- Weapons and grenades are not wrong inputs: 30 matches are too few to tell them apart from the equipment value. The selection is rerun at each step of the corpus.

Model 1 stays the published model until model 2 is trained on a larger corpus and its swings are ready.

## Swing: crediting actions

Each event changes the state, and the model gives the probability just before and just after it. The difference is the event's **swing**, seen by the side of the player it is credited to (`untraded.winprob.swing`):

- **A kill**: the victim's side loses a player, with their health, armor, equipment and kit.
  - The swing is shared among the enemies who damaged the victim this round, **by damage dealt** (the killer has at least the last hit).
  - A **flash assist** takes 10 % of it first.
  - The **victim** is debited the same swing. A team kill debits the killer instead, and credits no one; a death to the world or a suicide debits the victim only.
  - The death of a bot is not credited: the demo gives it no state of its own.
- **The plant**: the bomb goes down with 40 seconds to go; the planter gets the swing.
- **The defuse**: the counter-terrorists win; the defuser gets the swing.
- When an event decides the round (the last enemy dies, the defuse), the probability after it is the result, 1 or 0.
- The time passing between events is credited to no one. Kills during freeze time are not credited.
- The plant is credited only while a counter-terrorist is alive.
- Nothing is credited once the round is decided: the victims of the bomb's explosion and the kills after the round's end.

Every parsed match keeps its swings in the derived table `swing` ([round model](round-model.md)), and the metric **`rating.swing`** adds up each player's swings per round played, in percentage points ([metrics-v1](metrics-v1.md) § 6). `untraded winprob swings <match directory>` prints them.

The 2D viewer's round replays carry the curve and the swings ([replay format](replay-format.md), version 2).

## The Untraded Rating

`rating.swing` is the win probability a player's actions moved per round, in percentage points. Its average is about 0, so a rating cannot be a ratio to it. The **Untraded Rating** (`rating.untraded`, beta) maps it onto a scale where **1.00 is the average player of the corpus** (`untraded.winprob.rating`):

```
rating = 1 + (swing per round − m) / k
```

- **m** is the corpus's swing per round, all rounds pooled: the average player rates 1.00.
- **k** is the swing worth 1.00 of rating, chosen so that the rating spreads over the corpus's player-matches as HLTV 1.0 does on the same matches: the gaps read about as at HLTV, though one player's two ratings can differ (they correlate at 0.76).

| Scale 1.0 (`rating-v1.json`) | |
|---|---|
| Measured on | the 30 matches of the model 1.0, 300 player-matches |
| m | 0.4446 percentage points per round |
| k | 12.8914 percentage points per round for 1.00 |
| Correlation with HLTV 1.0, 2.0 (approx.) | 0.76, 0.77 |

The rating moves with HLTV without copying it: it credits what a kill was worth in its round (a kill in a 5v5 is worth less than the last kill of a clutch), the plant and the defuse, and debits each death by what it cost.

- **Its margin** (`rating.untraded_margin`): half-width of the 95 % interval, 1.96 × the standard deviation of the player's swing per round ÷ √rounds ÷ k. Over one match it is wide; over a session it narrows.
- **Its parts** (`rating.untraded_parts`): the points from kills (the shares the player earned, by damage and flash), deaths, plants and defuses, plus the baseline 1 − m / k. They add up to the rating, so every point can be traced to the actions behind it.

`untraded winprob rating-scale <match directories> --version 1.0 --out rating-v1.json` measures the scale (pro matches are left out). A new model or a larger corpus gives a new scale, and a new version of the metric.

## Reproducing it

```bash
untraded parse <Premier demos…> --mode premier --dates-from corpus/manifest.toml --out parsed
untraded parse <FACEIT demos…> --mode faceit --dates-from corpus/manifest.toml --out parsed
untraded winprob train parsed/matches/* --version 1.0 --source valve-premier --source faceit --out winprob-v1.json
```

`--l2` (default 1.0) and `--held-out` (default 0.3) set the penalty and the share of the newest matches held out. `--features` picks the inputs: `auto` (default) selects model 2's families as above, `v1` or `v2` take model 1's or all of model 2's. The corpus demos are private (ADR 0010), but the commands, the code and the model's outputs are not. Anyone can refit the model on their own matches and compare.
