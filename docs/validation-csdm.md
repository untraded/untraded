# Validation against CS Demo Manager (E8)

Workstream E8 compares our stats, player by player, with [CS Demo Manager](https://cs-demo-manager.com)'s analyzer, [`cs-demo-analyzer`](https://github.com/akiver/cs-demo-analyzer) (MIT). Every gap is either fixed or explained by a documented definition difference.

**Rules**: counts must be equal; ADR, KAST and ratings must be within 1 %.

## How to run it

The analyzer ships as an npm package with one executable per platform (`csda`):

```bash
npm install @akiver/cs-demo-analyzer@1.12.0
untraded compare-csdm --csda node_modules/@akiver/cs-demo-analyzer/dist/bin/linux-x64/csda --mode premier --out e8/ demos/*.dem.zst
```

`untraded compare-csdm` parses each demo, runs the analyzer on it, prints one line per field (players, gaps, largest difference) and, with `--out`, writes every comparison row to `comparison.parquet`. The code is `untraded.validation.csdm`.
Demos are compared in parallel, in low-priority processes: a demo starts whenever the free RAM covers it (about 2 GB, learned from the finished demos) on top of a reserve left to the user, so the number of demos running follows the machine's load. `--jobs N` runs exactly N at once instead.

## Results (20/10/2026)

- **Sample**: the 30 matches of the corpus outside pro demos (29 Premier, 1 FACEIT): 300 player rows, 28 fields, **8,400 values**.
- **Versions**: `cs-demo-analyzer` 1.12.0; `untraded` with the fixes below.
- **159 gaps (1.9 %), each traced to its round and its cause** (§ Definition differences). 72 of them come from two matches: the FACEIT demo (bots, § 2) and `valve-premier-2026-10-16-ancient-01` (a round abandoned by vote, § 1).

| Field | Rule | Gaps | Causes |
|---|---|---|---|
| deaths, 2K, 4K, 5K | exact | **0** | |
| assists | exact | 1 | an assist on a bot's death, FACEIT (§ 2) |
| kills, 1K, 3K, headshots, grenade damage | exact | 2, 1, 1, 3, 1 | the FACEIT demo only: a dead player controlling a bot (§ 2) |
| opening kills, opening deaths | exact | 1, 2 | one round whose first death is a fall (§ 7) |
| traded deaths | exact | 12 | 10 killers then killed by their own teammate, 1 trade by a player controlling a bot, 1 trade at exactly 5 s (§ 5) |
| trade kills | exact | 3 | a trade by a player controlling a bot, the kill of an enemy who had just killed his own teammate, a trade at exactly 5 s (§ 5) |
| ADR | 1 % | 17 | 10 in the match with the abandoned round and 4 late joiners or early leavers (§ 1), 3 bots in the FACEIT demo (§ 2). Total damage is identical in the 14 cases without a bot |
| HLTV 1.0 | 1 % | 14 | the rounds counted (§ 1) and bots (§ 2) |
| KAST | 1 % | 34 | 47 rounds counted by CSDM only: 19 not played, 12 with a flash assist only, 10 where the player was killed by a teammate, 6 traded by the killer's teammate (§ 1, § 4, § 5) |
| HLTV 2.0 (approx.) | 1 % | 50 | 40 through the KAST and ADR gaps, 5 through flash assists, 3 through CSDM's assist counter, 2 through its floor at 0 (§ 8) |
| clutch attempts and wins | exact | 16 attempts and 1 win, out of 3,000 values | 6 situations after the round end, 4 missing players, 1 pair of same-tick deaths, 6 bots in the FACEIT demo (§ 6) |

**How each gap was traced.** CSDM's KAST and HLTV 2.0 were recomputed from its JSON export with its own code (`Player.KAST()`, `HltvRating2()`, v1.12.0), round by round, and compared with our `round_player` rows. Trades, clutches and openings were matched event by event.

**Fixed** in the parser and the derived tables, found by this comparison:
- **Damage** is the health lost. `dmg_health` is rounded down, so it was often one point short: ADR differed for 132 players before the fix.
- **Kills of bots** count for the killer, and the death is nobody's.
- **Disconnections** are not deaths: the game records a `world` suicide when a player leaves.
- **Same-tick trades** count: a killer killed on the tick of their kill trades it (#41).
- **Posthumous trades** count: the victim's grenade or fire that kills their killer after the victim's death trades it (#42).
- **A player who leaves mid-round** leaves their team's lineup for clutches (#44).
- **Abandon votes** during freeze time are noted in `match.unavailable` and add no round (#41).

**Settled** with the maintainer (#43): a flash assist weighs 0.5 in `base.assist_score`, and a death after the round end is not a survival, as in CSDM (KAST, survival rate and HLTV 2.0 (approx.) at version 1.1.0).

## Definition differences

1. **Rounds counted.**
   - Our per-round stats divide by the rounds the player **played** (metrics-v1 § 0). CSDM divides by all the rounds of the match, and its KAST counts a round the player missed as survived. This changes the ADR, KAST and ratings of late joiners and early leavers; their total damage is the same.
   - CSDM also counts a round abandoned by vote during freeze time (no kill, ended on the freeze-time end tick). We only note it in `match.unavailable`. In `valve-premier-2026-10-16-ancient-01`, every player has 11 rounds for CSDM and 10 for us.
2. **Bots.** A dead player can take over a bot of their team.
   - We credit the bot's kills and damage to that player, as the in-game scoreboard does. CSDM does not.
   - Neither tool counts the bot's death as the player's death. CSDM counts an assist on a bot's death; we do not.
3. **Assists.**
   - CSDM's assister field includes flash-only assists. We split assists from flash assists (`base.assists`, `base.flash_assists`); the comparison adds them up.
   - The comparison counts CSDM's assists from its kill list, enemy kills only: its per-player counter does not match that list for 24 of 250 players.
4. **KAST.**
   - **Flash assists**: CSDM's KAST counts a round with a flash assist only. Ours does not by default (`kast.count_flash_assist = false`).
   - **Team kills**: CSDM skips them, so a player killed by a teammate "survives" the round. For us, that player is dead.
   - A death after the round end is a death on both sides since #43.
5. **Trades.** For us, a death is traded when the killer is then killed **by the victim's team**, within 5 s **inclusive**. CSDM's trade flags differ in four ways:
   - a killer then killed by one of their own teammates trades the death (10 of the 12 traded-death gaps);
   - a player controlling a bot can trade;
   - the kill of an enemy who had just killed his own teammate is a trade kill;
   - a trade at exactly 5.00 s does not count.
6. **Clutches.**
   - CSDM's per-player clutch counters do not add up: a player can have more 1vN attempts than rounds played. The comparison uses its `clutches` list instead.
   - The remaining gaps come from four rules:
     - we ignore kills after the round end, while CSDM finds 1v1 situations among the exit frags;
     - we count the enemies present in the round, while CSDM counts the full roster, missing players included;
     - when the last two players of a team die on the same tick, nobody clutched for us, while CSDM makes the second one a 1vN clutcher;
     - in the FACEIT demo, bots change both counts.
7. **Openings.** The first death of a round by a fall (`World`, no killer) is an opening death for CSDM. For us, the opening is the first kill by a player.
8. **HLTV 2.0 (approx.).** Same formula on both sides, and CSDM floors negative values at 0. CSDM's rating takes its assists from its per-player counter, flash assists included.
   - The values differ through KAST and ADR (§ 1, § 4) and through assists.
   - For the 10 players with no KAST or ADR gap, the cause is checked one by one:
     - for 5 of them, the formula applied to our inputs plus flash assists gives CSDM's value exactly;
     - for 3, the formula applied to CSDM's own exported inputs gives our value, and CSDM's rating is off by its assist counter (one assist = 0.005 to 0.006);
     - the last 2 are the floor at 0.
   - The largest gap is 0.19 (an early leaver). No published error margin exists for this approximation against HLTV's own ratings.
9. **Utility damage.** CSDM's utility damage includes the 1 to 2 points of a smoke, flash or decoy hitting a player. The comparison does too. Our metrics `util.he_damage` and `util.fire_damage` do not.

## Phase 1 criterion

The plan asks for **0 gaps** on counts and **≤ 1 %** on ADR and KAST over 20 matches; every gap must be fixed or explained.
- **Met on 30 matches.** No gap is left unexplained. Each comes from a definition difference above, a bot in the FACEIT demo, or a CSDM counter that disagrees with its own event list.
- On exact counts, outside the FACEIT demo, 25 of 6,960 values differ (0.4 %): trades, clutches and one fall.
- We keep our definitions where they differ, because they follow the match more closely (rounds played, trades by the victim's team, same-tick deaths). They are documented in metrics-v1, not aligned with CSDM.
