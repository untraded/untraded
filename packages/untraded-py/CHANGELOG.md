# Changelog

## Unreleased

- **Advice** (`untraded.advice`): an open rule engine. A rule fires when the session is worse than the reference by `advice.min_gap_pct` and has enough events, with its evidence (the very events its metric counts), its cost in rounds, and its priority. Batch 1: 10 rules (trades, spacing, opening duels, clutches, aim, utility, recurring death spot). See `docs/advice.md`.
- Every metric says which way is an improvement: `Metric.better` (`higher`, `lower` or `neutral`), a required argument of `@metric`, shown in the generated docs. No formula changes, so no version bumps.
- `parse_demo(mode="premier")` refuses a Valve matchmaking demo whose players' `rank_type` is not Premier (11), with `UnsupportedModeError`: Valve's share-code chain also returns Competitive and Wingman matches. Demos without a rank type are trusted.

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
