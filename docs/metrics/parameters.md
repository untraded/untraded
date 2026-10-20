# Parameters

*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by hand. The specification is [metrics-v1.md](../metrics-v1.md).*

Metric parameters are applied when a metric is computed: `compute(dataset, params={"trade.window_s": 3.0})`. Derivation parameters are applied when the round model is built, so changing one means deriving again. Reference parameters choose the matches of the player's own reference (`untraded.reference`). 🎯 marks a v0 threshold still to calibrate on demos from consenting high-level players (ADR 0010).

| Parameter | Default | Unit | Stage | 🎯 | Meaning | Used by |
|---|---|---|---|---|---|---|
| `assist.flash_weight` | 0.5 | ratio | metric |  | Weight of a flash assist in `base.assist_score`, an assist weighing 1. | [`base.assist_score`](base.assist_score.md) |
| `buy.eco_max` | 1000 | $ | derive | 🎯 | A team buy is an eco at or below this average equipment value per player, at freeze-time end + 7 s. | the round model |
| `buy.full_min_ct` | 4500 | $ | derive | 🎯 | A CT buy is a full buy at or above this average equipment value per player. | the round model |
| `buy.full_min_t` | 4000 | $ | derive | 🎯 | A T buy is a full buy at or above this average equipment value per player. | the round model |
| `flash.min_blind_s` | 1.0 | s | metric |  | Minimum blind duration for a blind to count as a flash (counts only; blind times keep every blind). | [`util.enemies_flashed`](util.enemies_flashed.md), [`util.self_flashed`](util.self_flashed.md), [`util.teammates_flashed`](util.teammates_flashed.md) |
| `isolation.radius` | 1000.0 | units | metric | 🎯 | An untraded death is isolated when the nearest living teammate is farther than this. | [`duel.isolated_death_pct`](duel.isolated_death_pct.md), [`duel.isolated_deaths`](duel.isolated_deaths.md) |
| `kast.count_flash_assist` | false | boolean | metric |  | Whether a flash assist alone makes a round count for KAST. | [`base.kast`](base.kast.md), [`rating.hltv2_approx`](rating.hltv2_approx.md) |
| `pos.recurring_death_share` | 0.25 | ratio | metric | 🎯 | Share of the player's untraded deaths on a map and side that makes a zone recurring. | [`pos.recurring_death_spot`](pos.recurring_death_spot.md) |
| `pos.recurring_min_rounds` | 32 | rounds | metric | 🎯 | Rounds the player must have played on a map and side before a zone can be recurring. | [`pos.recurring_death_spot`](pos.recurring_death_spot.md) |
| `reference.min_matches` | 5 | matches | reference |  | Below this many matches in the window, the reference is not shown. | the self reference |
| `reference.min_rounds` | 100 | rounds | reference |  | Below this many rounds played in the window, the reference is not shown. | the self reference |
| `reference.window_days` | 30 | days | reference |  | The player's own reference covers this many days before the session, the session excluded. | the self reference |
| `setup.offset_s` | 20.0 | s | derive |  | The setup zone is read this long after freeze-time end (`pos.setup_zone_t20`). | the round model |
| `trade.opportunity_distance` | 1300.0 | units | metric | 🎯 | A living teammate of the victim within this straight-line distance of the killer had a trade opportunity. | [`trade.death_opportunities`](trade.death_opportunities.md), [`trade.kill_conversion_pct`](trade.kill_conversion_pct.md), [`trade.kill_opportunities`](trade.kill_opportunities.md) |
| `trade.window_s` | 5.0 | s | metric |  | Trade window W: a death is traded when a teammate kills the killer within W seconds, both ends included (the same tick, and exactly W). 5 s is the usual convention (HLTV, CS Demo Manager); CS Demo Manager excludes exactly W. | [`base.kast`](base.kast.md), [`duel.isolated_death_pct`](duel.isolated_death_pct.md), [`duel.isolated_deaths`](duel.isolated_deaths.md), [`pos.death_zones`](pos.death_zones.md), [`pos.recurring_death_spot`](pos.recurring_death_spot.md), [`rating.hltv2_approx`](rating.hltv2_approx.md), [`trade.kill_conversion_pct`](trade.kill_conversion_pct.md), [`trade.trade_kills`](trade.trade_kills.md), [`trade.traded_death_pct`](trade.traded_death_pct.md), [`trade.traded_deaths`](trade.traded_deaths.md), [`trade.untraded_deaths`](trade.untraded_deaths.md) |
| `trade.window_w3_s` | 3.0 | s | metric |  | Shorter trade window of the `_w3` variants, for tighter trades. | [`trade.trade_kills_w3`](trade.trade_kills_w3.md), [`trade.traded_death_pct_w3`](trade.traded_death_pct_w3.md), [`trade.traded_deaths_w3`](trade.traded_deaths_w3.md), [`trade.untraded_deaths_w3`](trade.untraded_deaths_w3.md) |
