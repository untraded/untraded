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

## Results (19/10/2026)

- **Sample**: 18 demos of the corpus (17 Premier, 1 FACEIT), 180 player rows.
- **Versions**: `cs-demo-analyzer` 1.12.0; `untraded` after the parsing fixes below.

| Field | Rule | Gaps | Explanation |
|---|---|---|---|
| deaths, opening kills, opening deaths | exact | **0** | |
| multi-kills (2K, 4K, 5K) | exact | **0** | |
| kills, 1K, 3K, headshots | exact | 2, 1, 1, 3 | the FACEIT demo only: kills by a dead player controlling a bot (§ 2) |
| grenade damage | exact | 1 | the FACEIT demo: damage dealt while controlling a bot (§ 2) |
| ADR | 1 % | 7 | late joiners (§ 1), and damage while controlling a bot (§ 2) |
| HLTV 1.0 | 1 % | 5 | late joiners (§ 1), and kills while controlling a bot (§ 2) |
| assists | exact | 24 | team-kill assists (§ 3) |
| KAST | 1 % | 23 | deaths after the round end, assists, and trades by a teammate (§ 3, § 4, § 5) |
| traded deaths, trade kills | exact | 6, 2 | trades by a teammate of the killer (§ 5) |
| HLTV 2.0 (approx.) | 1 % | 33 | its inputs: KAST and assists (§ 3 to § 5); CSDM also floors negative ratings at 0 |
| clutch attempts and wins | exact | 15 attempts, 1 win, out of 1,800 values | lineups and the round end (§ 6) |

**Fixed** in the parser, found by this comparison:
- **Damage** is the health lost. `dmg_health` is rounded down, so it was often one point short: ADR differed for 132 players before the fix.
- **Kills of bots** count for the killer, and the death is nobody's.
- **Disconnections** are not deaths: the game records a `world` suicide when a player leaves.

## Definition differences

1. **Rounds counted.** Our per-round stats divide by the rounds the player **played** (metrics-v1 § 0). CSDM divides by the match's rounds, which lowers the ADR and the rating of a player who joined late.
2. **Bots.** A dead player can take over a bot of their team.
   - We credit the bot's kills and damage to that player, as the in-game scoreboard does. CSDM does not.
   - Neither tool counts the bot's death as the player's death.
3. **Assists.** CSDM counts every assist event. We split assists from flash assists (`base.assists`, `base.flash_assists`; the comparison adds them up), and we drop assists on a team kill.
4. **Survival (KAST).** For us, a player survives a round when alive at the round's end. CSDM also counts a death after the round end (an exit frag) as a death.
5. **Trades.** For us, a death is traded when the killer is then killed **by the victim's team**. CSDM also counts the killer's death by one of their own teammates.
6. **Clutches.**
   - CSDM's per-player clutch counters do not add up: a player can have more 1vN attempts than rounds played. The comparison uses its `clutches` list instead, which matches ours on almost every row.
   - The rest comes from two rules. First, we count the enemies alive at freeze-time end, while CSDM counts the full roster, missing players included. Second, we ignore kills after the round end.
7. **Utility damage.** CSDM's utility damage includes the 1 to 2 points of a smoke, flash or decoy hitting a player. The comparison does too. Our metrics `util.he_damage` and `util.fire_damage` do not.
8. **HLTV 2.0 (approx.).** Same formula on both sides. The values differ only through KAST and assists: by 0.009 on average and 0.19 at most (a late joiner), and CSDM floors negative values at 0. No published error margin exists for this approximation against HLTV's own ratings.

## Phase 1 criterion

The plan asks for **0 gaps** on counts and **≤ 1 %** on ADR and KAST over 20 matches; every gap must be fixed or explained.
- On 18 matches, every remaining gap is explained by the differences above, and there is no unexplained gap.
- Two more Premier matches are needed to reach 20.
