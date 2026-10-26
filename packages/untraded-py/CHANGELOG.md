# Changelog

## Unreleased

- **Advice** (`untraded.advice`): an open rule engine. A rule fires when the session is worse than the reference by `advice.min_gap_pct` and has enough events, with its evidence (the very events its metric counts), its cost in rounds, and its priority. Batch 1: 10 rules (trades, spacing, opening duels, clutches, aim, utility, recurring death spot). See `docs/advice.md`.
- Every metric says which way is an improvement: `Metric.better` (`higher`, `lower` or `neutral`), a required argument of `@metric`, shown in the generated docs. No formula changes, so no version bumps.
- `parse_demo(mode="premier")` refuses a Valve matchmaking demo whose players' `rank_type` is not Premier (11), with `UnsupportedModeError`: Valve's share-code chain also returns Competitive and Wingman matches. Demos without a rank type are trusted.
- Every value metric says what it stands on, `Metric.cases` (the rounds played, or the count metrics whose sum is its number of cases), and whether it can be negative, `Metric.signed`; both are shown in the generated docs (#88).
- **Win probability** (`untraded.winprob`): a round win-probability model on the round's state, sampled every second (a logistic regression with enforced signs and per-round weights), validated on the newest matches against two baselines, and the swing of each kill, plant and defuse credited to players. The published model `winprob-v1.json` (version 1.0) ships with the package, `default_model()`. New dependency: `numpy>=2` (#124). See `docs/winprob.md`.
- `derive` adds a `swing` table, computed with the published model or the one passed as `winprob=`; `swing_table` builds it alone for matches derived before it (#125).
- New metric `rating.swing`, the player's swings per round played, in percentage points (#125). Version 1.1.0: nothing is credited once the round is decided, so a death to the bomb's explosion no longer debits its victim (#126).
- **Round replays** (`untraded.replay`) for the 2D viewer: one compact JSON document per round (players' states on one timeline, kills, grenades and their paths, blinds, bomb), with the radar transforms of the map pool in `untraded.maps` (#103), Cache included (#108). Format 2 adds the win-probability curve and the swings (#126).
- **Radars** (`untraded.navmesh`, `untraded.vpk`, `untraded.radars`): reads CS2 navigation meshes (versions 31 to 36), from `.nav` files or a CS2 installation, and draws one SVG radar per map and level (#104).
- **Command line**: `untraded radars` (#104), `untraded winprob train` and `untraded winprob swings` (#124).
- `digest(path, max_size=...)` raises the new `DemoTooLargeError` when a demo decompresses to more than `max_size` bytes (#113).
- Fixtures: the weapon in hand of `player_tick` is made generic too, so a knife's name no longer shows in an extract (#105).

## 0.1.0 (2026-10-20)

The metrics engine (phase 1 of Untraded).

- **Parsing** (`untraded.parsing`): 13 parser-agnostic canonical tables (schema 1.1) from `.dem`, `.dem.bz2`, `.dem.gz` and `.dem.zst` demos, with rounds cut from game state and documented fallbacks for missing events. Kills of bots, disconnections and abandon votes are handled. `CanonicalMatch.read` and `.write` use one Parquet file per table.
- **Round model** (`untraded.derive`): per-player rounds, deaths with trade delays and spacing, trade opportunities, clutches, team buy types.
- **Metrics** (`untraded.metrics`): a versioned registry of 81 metrics, 72 values and 9 tables, with explicit parameters, splits by side, map and buy type, and one generated page per metric.
- **Ratings**: HLTV Rating 1.0, and an approximation of HLTV 2.0 always labeled "approx.".
- **Self reference** (`untraded.reference`): a session against the player's own 30 days before it.
- **Calibration** (`untraded.calibration`): measures of the adjustable thresholds on a corpus.
- **Command line**: `parse` (parallel), `analyze`, `reference`, `calibrate`, `compare-csdm`, `fixture`, `corpus`.
- **Validation**: the shared stats match CS Demo Manager on 30 matches, and each of the 159 differing values out of 8,400 is explained by a documented definition difference.

## 0.0.2 (2026-10-13)

- `rating_hltv_1` (HLTV Rating 1.0 on match totals).
