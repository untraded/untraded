# Architecture decision records

One decision per file, numbered, never rewritten: a decision that changes gets a new ADR that supersedes the old one.

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-monorepo-and-licensing.md) | Monorepo (uv + pnpm), AGPL-3.0-only for the product, MIT for libraries, REUSE | Accepted |
| [0002](0002-parser-agnostic-canonical-tables.md) | Parser-agnostic canonical tables | Accepted |
| [0003](0003-versioned-metric-registry.md) | Versioned metric registry | Accepted |
| [0004](0004-postgres-as-job-queue.md) | PostgreSQL as the job queue | Accepted |
| [0005](0005-storage-layout.md) | Content-addressed demos, Parquet per match, PostgreSQL for entities and aggregates | Superseded by 0009 |
| [0006](0006-schema-ownership.md) | Database schema owned by Python (Alembic), typed access from Node | Accepted |
| [0007](0007-explicit-metric-parameters.md) | Explicit, documented metric parameters | Accepted |
| [0008](0008-rounds-from-game-state.md) | Rounds from game state; events are optional input with documented fallbacks | Accepted |
| [0009](0009-storage-and-retention.md) | Raw demos stored as received; 16 Hz Parquet is the long-term record; retention per deployment | Accepted |
| [0010](0010-reference-data-and-corpus.md) | No published pro-derived data; calibration on consenting players' demos; private shared corpus | Accepted |
| [0011](0011-phase-2-database-schema.md) | Phase 2 database: configurable roles, materialized match access, events and metrics in SQL, row-level security | Accepted |

## Template

```markdown
# NNNN. Title

- Status: Proposed | Accepted | Superseded by NNNN
- Date: YYYY-MM-DD

## Context
## Decision
## Consequences
```
