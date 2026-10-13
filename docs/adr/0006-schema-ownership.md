# 0006. Database schema ownership

- Status: Accepted
- Date: 2026-10-13

## Context

Python (API, worker) and Node (collector) both access PostgreSQL. Two migration systems would drift.

## Decision

- The schema is owned by Python: migrations in `db/` with **Alembic**.
- Node accesses the database through **kysely**, with types generated from the live schema (kysely-codegen) and checked in CI.

## Consequences

- One source of truth for the schema; Node type errors surface when a migration changes a table it uses.
- Node services cannot change the schema on their own.
