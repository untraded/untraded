# Metric catalog v1 (phase 1)

*Version 1, 2026-10-13, updated 2026-10-26. This catalog is **closed** for phase 1: new metrics go to v2. Two entries were added since, `base.assist_score` (settled with the CS Demo Manager comparison) and `rating.swing` (the first step of the open rating). Each entry is a registered metric (`packages/untraded-py/src/untraded/metrics/`, 82 in all: 73 values and 9 tables) with a generated documentation page ([metrics/](metrics/README.md)), which also gives its version and history.*

**Legend**
- **ID**: stable registry identifier. It never changes, even when the formula's version does.
- **CSDM**: ✅ cross-checked against CS Demo Manager in phase 1; ≈ comparable with a known definition difference; — no equivalent.
- **⚙** adjustable parameter with its default. **🎯** v0 threshold, to calibrate on demos from consenting high-level players ([ADR 0010](adr/0010-reference-data-and-corpus.md)).

---

## 0. Common conventions

| Topic | Rule |
|---|---|
| Tickrate | Computed from each demo (64 in every demo seen so far), **never assumed**: the header does not carry it ([ADR 0008](adr/0008-rounds-from-game-state.md)). All durations are converted from ticks to seconds. |
| Rounds played | Rounds where the player was connected and on a team at freeze-time end. Warmup, knife rounds and cancelled or replayed rounds are excluded. |
| Side | The player's team side at round start. Every metric exists overall, **CT** and **T**. |
| Kills | Enemy kills only. Team kills and suicides are counted separately (`base.team_kills`, `base.suicides`). |
| Deaths | All deaths: by an enemy, a teammate, suicide, fall damage or the bomb. |
| Damage | **Capped** damage, i.e. health actually removed: `min(dmg_health, victim health before the hit)`. Only damage to enemies counts unless stated otherwise. |
| Distances | 3D Euclidean distance between positions, in Hammer units (a player is about 72 u tall). Navmesh path distance comes in v2. |
| Zones | The player's `last_place_name`, i.e. the engine navmesh place name (e.g. `BombsiteA`, `Connector`). Mapping to community callouts comes in v2. |
| Multi-match averages | Per-round metrics are recomputed over all rounds, never as an average of per-match averages. |
| Bots | A dead player who takes over a bot of their team gets the bot's kills and damage, as on the in-game scoreboard. The death of a bot, controlled or not, is nobody's death, and an assist on the death of an uncontrolled bot is not counted. |

---

## 1. Base

| ID | Name | Definition | CSDM |
|---|---|---|---|
| `base.kills` | Kills | Number of kills | ✅ |
| `base.deaths` | Deaths | Number of deaths | ✅ |
| `base.assists` | Assists | Enemy kills where the player is the `assister`, **flash assists excluded** | ✅ |
| `base.flash_assists` | Flash assists | Enemy kills with `assistedflash` credited to the player | ✅ |
| `base.assist_score` | Weighted assists | Assists + ⚙ `assist.flash_weight = 0.5` × flash assists: a flash assist counts, but less than an assist | — |
| `base.team_kills`, `base.suicides` | Team kills, suicides | Teammates killed by the player; deaths where the player is both attacker and victim | ✅ |
| `base.kd_diff` | K−D | kills − deaths | ✅ |
| `base.kpr`, `base.dpr`, `base.apr` | Per round | kills, deaths or assists ÷ rounds played | ✅ |
| `base.adr` | ADR | Sum of capped damage to enemies ÷ rounds played | ✅ (≤ 1 %) |
| `base.hs_pct` | HS % | Headshot kills ÷ kills × 100 | ✅ |
| `base.kast` | KAST | % of rounds played where the player got a **K**ill, an **A**ssist (flash assists excluded by default, ⚙ `kast.count_flash_assist = false`), **S**urvived (alive at round end and no death after it), or was **T**raded (§ 2) | ✅ (≤ 1 %) |
| `base.multikills_{1..5}` | 1K to 5K | Number of rounds with **exactly** N kills | ✅ |
| `base.rounds_with_kill_pct` | Rounds with a kill | % of rounds with at least one kill | — |
| `base.survival_pct` | Survival | % of rounds where the player is alive at round end **and does not die after it**: a death after the round end (an exit frag) drops the weapons, so it is not a survival | ✅ |

## 2. Duels and trades (priority)

**Core definitions**
- **Opening**: the first enemy kill of the round after freeze-time end. A death by a fall or the world (no killer) is not an opening.
- **Trade**: A is killed by enemy B at tick *t*. If a teammate C of A kills B within [*t*, *t* + W], the same tick included, then:
  - **A's death is traded**;
  - **C gets a trade kill**.
  - When A and B kill each other on the same tick, nobody is traded. A's own grenade or fire killing B after A's death does trade it.
- **W**, the trade window: ⚙ `trade.window_s = 5.0` (HLTV and CSDM convention). A 3-second variant is computed alongside with the `_w3` suffix (⚙ `trade.window_w3_s = 3.0`).
- **Trade opportunity**: A is killed by B. Every teammate C of A who is **alive** at that tick and **within D units of B's position** has a trade opportunity.
  - ⚙🎯 `trade.opportunity_distance = 1300` u (calibrated, [calibration.md](calibration.md)).

| ID | Name | Definition | CSDM |
|---|---|---|---|
| `duel.opening_kills` | Opening kills | Rounds where the player makes the opening kill | ✅ |
| `duel.opening_deaths` | Opening deaths | Rounds where the player is the opening victim | ✅ |
| `duel.opening_attempts` | Opening duels | Opening kills + opening deaths | ✅ |
| `duel.opening_success_pct` | Opening success | Opening kills ÷ opening duels × 100 | ✅ |
| `duel.opening_attempt_pct` | Opening frequency | Opening duels ÷ rounds played × 100 | — |
| `duel.opening_win_conversion_pct` | Opening conversion | % of rounds with an opening kill by the player that the team wins | — |
| `trade.trade_kills` | Trade kills | Trade kills made: kills of an enemy who killed a teammate of the player within W before | ✅ |
| `trade.traded_deaths` | Traded deaths | The player's deaths that were traded | ✅ |
| `trade.traded_death_pct` | Traded death % | Traded deaths ÷ deaths × 100 | — |
| `trade.untraded_deaths` | **Untraded deaths** | Deaths − traded deaths (the product's signature metric). Includes deaths with no teammate left to trade them | — |
| `trade.trade_kills_w3`, `trade.traded_deaths_w3`, `trade.traded_death_pct_w3`, `trade.untraded_deaths_w3` | 3-second variants | The same four metrics with W = 3 s (⚙ `trade.window_w3_s = 3.0`) | — |
| `trade.kill_opportunities` | Trade opportunities | The player's trade opportunities (as defined above) | — |
| `trade.kill_conversion_pct` | Opportunity conversion | Trade kills ÷ trade opportunities × 100 | — |
| `trade.death_opportunities` | Tradable deaths | The player's deaths where at least one teammate had a trade opportunity | — |
| `duel.isolated_deaths` | Isolated deaths | **Untraded** deaths where the nearest living teammate was more than R units away. ⚙🎯 `isolation.radius = 1000` u (checked on the corpus and kept, [calibration.md](calibration.md)). A death with no living teammate (last player alive) is not isolated | — |
| `duel.isolated_death_pct` | Isolated death % | Isolated deaths ÷ deaths × 100 | — |
| `duel.nearest_teammate_at_death` | Spacing at death | Median, over deaths with a living teammate, of the distance to the nearest one (u) | — |
| `clutch.attempts_1v{1..5}` | Clutch attempts | Rounds where the player becomes the last one alive on the team, facing N living enemies. Kills after the round end are ignored, only the enemies present in the round count, and when the last two players of a team die on the same tick nobody clutched | ✅ |
| `clutch.wins_1v{1..5}` | Clutch wins | …and the team wins the round, whether or not the clutcher survives | ✅ |
| `clutch.win_pct` | Clutch success | Clutch wins ÷ clutch attempts × 100, over all N | ✅ |

## 3. Positioning (priority)

These metrics are distributions per map and side, not one number per player: the registry exposes them as `table` metrics (`untraded.metrics.compute_table`), with the columns listed on each metric's page in [metrics/](metrics/README.md).

| ID | Name | Definition | CSDM |
|---|---|---|---|
| `pos.death_zones` | Death zones | Distribution of deaths by zone, per map and side, with the traded % for each zone | — |
| `pos.kill_zones` | Kill zones | Distribution of enemy kills by zone (killer position), per map and side | — |
| `pos.setup_zone_t20` | Position at T+20 s | The player's zone 20 s after freeze-time end (⚙ `setup.offset_s = 20`, applied when the round model is derived), over the rounds where the player is alive then, distribution per map and side: CT setups, T defaults | — |
| `pos.setup_diversity` | Predictability | Normalized entropy of that distribution, per map and side: entropy ÷ ln of the number of distinct zones used (0 = always the same spot, 1 = spread evenly; 0 with a single zone) | — |
| `pos.recurring_death_spot` | Recurring death spot | For each map and side: a zone holding ≥ X % of the player's **untraded** deaths, when the player played ≥ N rounds there. ⚙🎯 `pos.recurring_death_share = 0.25`, `pos.recurring_min_rounds = 32` (calibrated, [calibration.md](calibration.md)). **First building block of pattern-based advice.** | — |
| `pos.heatmap_points` | Heatmap points | Raw export of kill and death positions (killer and victim), per map and side. Rendering comes in phase 2. | ≈ |

## 4. Utility

| ID | Name | Definition | CSDM |
|---|---|---|---|
| `util.thrown_{flash,he,molotov,smoke,decoy}` | Grenades thrown | Counts by type (molotov and incendiary merged) | ✅ |
| `util.thrown_per_round` | Utility per round | Total thrown ÷ rounds played | — |
| `util.enemies_flashed` | Enemies flashed | Enemies blinded by the player's flashes for at least ⚙ `flash.min_blind_s = 1.0` | ≈ |
| `util.enemy_blind_time` | Blind time dealt | Sum of enemy blind durations (s), every blind (the minimum only applies to counts) | ✅ |
| `util.blind_per_flash` | Flash efficiency | Enemy blind time dealt ÷ flashes thrown | — |
| `util.teammates_flashed`, `util.team_blind_time` | Team flashes | Count (same minimum) and total duration on teammates, the player excluded | ✅ |
| `util.self_flashed` | Self-flashes | Times the player blinded themselves, same minimum | — |
| `util.flash_to_kill` | Decisive flashes | Enemies blinded by the player and killed by the player's team, the player included, **while still blind** (blind tick ≤ kill tick ≤ blind tick + duration; no minimum). One count per kill for each player whose flash was still active | — |
| `util.he_damage`, `util.he_team_damage` | HE damage | Capped damage to enemies and to teammates; self-damage counts as neither | ✅ |
| `util.fire_damage` | Fire damage | Capped molotov and incendiary damage to enemies (fire ownership is verified, see demoparser2 issue #317) | ✅ |
| `util.unused_value_at_death` | Wasted utility | Value ($) of grenades in the inventory at death, averaged per death (buy prices: flash 200, HE 300, smoke 300, molotov 400, incendiary 500, decoy 50) | — |

`player_blind` also fires on players who are already dead: flash metrics only count blinds of living players. Fire damage counts only damage linked to one of the player's own grenades (fire and impact).

## 5. Economy

**Buy type per team and round** (v0, aligned with CSDM so it can be validated). The measured value is the team's average equipment value per player, at freeze-time end + 7 s.

| Type | Rule |
|---|---|
| **pistol** | First round of each regulation half |
| **eco** | ≤ $1,000 |
| **full** | ≥ $4,500 on CT, ≥ $4,000 on T |
| **force** | Previous round lost, and neither eco nor full |
| **semi** | Everything else |

⚙🎯 All thresholds are parameters (`buy.eco_max`, `buy.full_min_ct`, `buy.full_min_t`), applied when the round model is derived; they were checked on the corpus and kept ([calibration.md](calibration.md)).

| ID | Name | Definition | CSDM |
|---|---|---|---|
| `eco.buy_type` | Buy type | The player's team buy type per round (derived, exposed as a split: `Dataset.split(buy=...)`); the metric counts rounds per buy type with the % won | ✅ |
| `eco.win_pct_by_matchup` | Win % by economy | % of rounds won per (team buy type, opponent buy type) pair | — |
| `eco.equipment_lost_at_death` | Equipment lost | The player's equipment value at the tick of death, averaged per death | — |
| `eco.kills_vs_buy` | Kills by economy | Enemy kills split by (killer, victim) weapon class: the best weapon held, among `awp`, `rifle` (other snipers included), `heavy` (shotguns and machine guns), `smg`, else `pistol`. The killer's inventory is its last change before the kill, the victim's is read at the kill | — |

`eco.buy_type`, `eco.win_pct_by_matchup` and `eco.kills_vs_buy` are table metrics (§ 3).

## 6. Ratings

| ID | Name | Definition | CSDM |
|---|---|---|---|
| `rating.hltv1` | HLTV Rating 1.0 | (KillRating + 0.7 × SurvivalRating + MultiKillRating) / 2.7, with reference averages 0.679, 0.317 and 1.277 (public formula); a round of N kills is worth N² multi-kill points. Kills are enemy kills, deaths any death. Same formula as `rating_hltv_1`, published in `untraded` 0.0.1. | ✅ |
| `rating.hltv2_approx` | HLTV 2.0 (approx.) | 0.0073 × KAST + 0.3591 × KPR − 0.5329 × DPR + 0.2372 × Impact + 0.0032 × ADR + 0.1587, with Impact = 2.13 × KPR + 0.42 × APR − 0.41 and KAST in % (`base.kast`, same parameters). Can be negative (CS Demo Manager floors it at 0). **Always labeled "approx."** | ≈ |
| `rating.swing` | Win-probability swing | The player's swings (derived table `swing`: how much each of their kills, deaths, plants and defuses moved their team's chance of winning the round, by the open win-probability model 1.0, [winprob](winprob.md)), summed and divided by the rounds played, in percentage points. 0 is a player whose actions moved nothing on balance. Can be negative. Matches derived before the `swing` table existed are left out | — |

**Validation.**
- HLTV 1.0: the demos of the 1.0 era are CS:GO demos, which the CS2 parser does not read, so it is checked against independent calculations. The reference average player rates exactly 1.00. Over 18 Premier matches, the mean of each lobby is 0.99, ranging from 0.91 to 1.04. Against CS Demo Manager on 30 matches (E8), every gap comes from the rounds counted or from bots ([validation-csdm.md](validation-csdm.md)).
- HLTV 2.0 (approx.): HLTV does not publish the formula, and no published error margin was found for this community approximation. Over the same matches, its lobby mean is 1.10 and it correlates at 0.95 with the 1.0. Against CS Demo Manager, the formula is the same and every gap comes from its inputs (KAST, ADR, assists) or its floor at 0.

The **open Untraded rating** will be built on `rating.swing`, on a scale where 1.00 is the average player. Its model is trained on demos from consenting high-level players only ([ADR 0010](adr/0010-reference-data-and-corpus.md), [winprob](winprob.md)).

## 7. Splits available in v1

Every metric can be computed on any subset of rounds. `Dataset.split` keeps the rounds a player played:
- on a **map** (`map=...`);
- on a **side** (`side="CT"` or `"T"`);
- with a **team buy type** (`buy=...`, § 5).

The matches a dataset is built from (`Dataset.from_matches`) choose the rest: a **source** (Premier, FACEIT, scrim) or a **period**, such as the self reference below. A split by **half** is not built in yet.

By design, there are no splits by fatigue, tilt, time of day or ping.

### Self reference

A session is compared with the player's own reference ([ADR 0010](adr/0010-reference-data-and-corpus.md), `untraded.reference`, `untraded reference`):
- the reference covers the ⚙ `reference.window_days = 30` days **before** the session's first day. The session itself is excluded, so that a very good or very bad evening does not pull its own reference towards it;
- it is computed over **all the rounds** of those matches (§ 0), never averaged from per-match values;
- it is shown only from ⚙ `reference.min_matches = 5` matches and ⚙ `reference.min_rounds = 100` rounds. Below that, the comparison says there are not enough matches yet;
- **totals** (counts, damage in HP, blind time dealt) are compared **per round**, since the session and the reference do not have the same number of rounds. Rates, ratios and medians are compared as they are. A test checks this classification on every metric: on the same match counted twice, a total doubles and a rate does not;
- dates are match days (`match.played_at`): a match played earlier on the session's first day is in neither. Undated matches are left out of the reference.

---

## 8. Out of v1 (for reference)

| Topic | Phase |
|---|---|
| Aim level 1: accuracy by weapon, distance and movement; counter-strafing; time to damage | 2 |
| Open rating on the 1.00 scale, built on `rating.swing` (§ 6) | 2 |
| Typical positions by clustering, arrival timings, team spacing at first contact | 2-3 |
| Team stats: executes, setups, trade network, retakes and post-plants | 3 |
| True line of sight, crossfire exposure, aim level 2 | 5 |
