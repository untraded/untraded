# 0010. Reference data and demo corpus

- Status: Accepted
- Date: 2026-10-14
- Refines: [0007](0007-explicit-metric-parameters.md)

## Context

The plan was to build a pro corpus in phase 1. It had three uses: calibrate v0 thresholds (ADR 0007), publish pro reference baselines, and train the win-probability model behind the open rating. Spike S0.4 found that:

- CS2 pro demos are in practice only available from HLTV. Its terms forbid automated collection, commercial use and building a competing service without a license.
- There is no openly licensed CS2 pro dataset, and one built from HLTV demos was taken down after a notice from Valve.
- In the EU, a collection of demos can be protected as a database even when individual facts are not.

Separately, demos contain the SteamIDs and names of every player in the match.

## Decision

- **Nothing derived from pro demos is published or shipped** (no pro baselines, no pro-trained tables) until a source with suitable terms exists. Pro demos obtained manually may be used **internally** for engineering (parser robustness, metric validation), and are never redistributed.
- **Calibration and the win-probability model** use demos from **consenting players** at our target level (Premier and FACEIT). Published thresholds and model tables are derived from those.
- **The default reference is the player's own rolling 30-day baseline.** Rank-based references come later, as anonymous opt-out aggregates.
- **Corpus:**
  - demos are never committed;
  - the reference corpus is listed in `corpus/manifest.toml` (sha256 of the decompressed demo, source, map, date, game build);
  - the files live in a **private shared store** (S3-compatible or SFTP), configured outside the repository and synced to `$UNTRADED_CORPUS_DIR` by a `corpus` command;
  - no corpus demo is public.
- **Test fixtures** are anonymized canonical extracts: SteamIDs and names are replaced, and only the rounds a test needs are kept.
  - *Update 2026-10-20*: fixtures come from Premier and FACEIT demos only, never from pro demos, as they are published in the repository. Each is a window of consecutive rounds (`untraded.fixtures`, `untraded fixture extract`). Players become 1 to N and `A1`… `B5`; the server name, team names, date, rank and match id are removed; positions and events are unchanged. The tests fail if a steamid of an event is not a renumbered player.
  - *Update 2026-10-20 (review)*: knives become `knife` in inventories and weapon names (a knife skin is close to a signature of its owner). `fixture.toml` no longer names the source demo: the public corpus manifest would date the match and lead back to its players. The fixture-to-demo mapping is kept in the private repository, and the parser check reads it from `UNTRADED_FIXTURE_SOURCES`. The demo ids of the first version remain in the git history.

## Consequences

- Phase 1 ships no pro baselines.
- The open rating's training waits until consenting testers' demos exist (phase 2).
- 🎯 thresholds stay marked as v0 until calibrated on that corpus.
- Every machine and the CI can rebuild the same corpus from the manifest. The shared store is an operating cost and holds personal data, so access is restricted.
- If a licensed pro source becomes available, a new ADR can lift the first rule.
