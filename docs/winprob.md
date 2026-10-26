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
| `time_left` | before the plant: round time left (1:55 from freeze-time end), in tens of seconds |
| `time_left_planted`, `alive_ct_planted`, `alive_t_planted` | the same values once the bomb is down, 0 before |
| `map=<name>` | one per map, against a baseline map |

**Which samples are kept:**
- a sample is kept while the round is still open: both sides have someone alive, or only the counter-terrorists do while the bomb is down (they can still defuse);
- nothing is kept after a defuse or an explosion;
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
- **Training data**: demos of **consenting players** only, at Untraded's target level (Premier and FACEIT). **Nothing from professional demos** goes in, because their terms forbid it (ADR 0010).

The published model is `packages/untraded-py/src/untraded/winprob/winprob-v1.json`. It holds:
- the coefficients;
- the means and scales of the inputs;
- what it was trained on (matches, rounds, dates, maps), with no match ids;
- the scores below.

A gradient-boosted model (v2) will be tried once the corpus reaches about 300 matches, and kept only if it beats this one on held-out matches.

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

## Swing: crediting actions

Each event changes the state, and the model gives the probability just before and just after it. The difference is the event's **swing**, seen by the side of the player it is credited to (`untraded.winprob.swing`):

- **A kill**: the victim's side loses a player, with their health, armor, equipment and kit.
  - The swing is shared among the enemies who damaged the victim this round, **by damage dealt** (the killer has at least the last hit).
  - A **flash assist** takes 10 % of it first.
  - The **victim** is debited the same swing. A team kill debits the killer; a death to the world debits the victim.
- **The plant**: the bomb goes down with 40 seconds to go; the planter gets the swing.
- **The defuse**: the counter-terrorists win; the defuser gets the swing.
- When an event decides the round (the last enemy dies, the defuse), the probability after it is the result, 1 or 0.
- The time passing between events is credited to no one.

`untraded winprob swings <match directory>` prints each player's swing per round.

The **open rating** built on these swings comes next. On its scale, 1.00 is the average player of the corpus.

## Reproducing it

```bash
untraded parse <demos…> --mode premier --dates-from corpus/manifest.toml --out parsed
untraded winprob train parsed/matches/* --version 1.0 --source valve-premier --out winprob-v1.json
```

The corpus demos are private (ADR 0010), but the commands, the code and the model's outputs are not. Anyone can refit the model on their own matches and compare.
