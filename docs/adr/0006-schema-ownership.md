# 0006. Database schema ownership

- Status: Accepted; the Node part is not implemented as written
- Date: 2026-10-13
- Note (2026-10-26): the migrations are in `db/` with Alembic, as decided. The collector, the only Node service using the database, uses node-postgres (`pg`) with hand-written queries: there is no kysely, no generated types and no CI check of them.

## Context

Python (API, worker) and Node (collector) both access PostgreSQL. Two migration systems would drift.

## Decision

- The schema is owned by Python: migrations in `db/` with **Alembic**.
- Node accesses the database through **kysely**, with types generated from the live schema (kysely-codegen) and checked in CI.

## Consequences

- One source of truth for the schema; Node type errors surface when a migration changes a table it uses.
- Node services cannot change the schema on their own.
