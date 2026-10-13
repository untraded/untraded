# 0002. Parser-agnostic canonical tables

- Status: Accepted
- Date: 2026-10-13

## Context

demoparser2 is the best CS2 parser today, but CS2 patches regularly break parsers for hours to weeks, PyPI releases can lag fixes by more than two weeks, and demoinfocs-golang or a future awpy v3 may become better options. Metric code must not be rewritten when the parser changes.

## Decision

- A `DemoParser` protocol in `untraded.parsing` turns a demo into **canonical tables**: `match`, `player`, `round`, `kill`, `damage`, `shot`, `grenade`, `blind`, `economy`, `player_tick`.
- Canonical tables are **Polars DataFrames with strict, versioned schemas**, validated on creation (types, monotonic ticks, every event attached to a round, warmup excluded).
- **Only `untraded.parsing` may import `demoparser2` or pandas** (enforced by ruff's banned-API rule).
- The tickrate is read from the demo, never assumed.

## Consequences

- Swapping or cross-checking parsers means writing one adapter.
- Canonical extracts of a few rounds can be committed as test fixtures, so CI runs without demos.
- One conversion step (pandas → Polars) is paid at the adapter boundary.
