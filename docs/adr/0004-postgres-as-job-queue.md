# 0004. PostgreSQL as the job queue

- Status: Accepted
- Date: 2026-10-13

## Context

The Node collector produces work (new demos) that Python workers consume. Self-hosters should run as few services as possible. Volumes are modest: a few hundred to a few thousand demos per day for the hosted version.

## Decision

- No Redis. Jobs live in a PostgreSQL `job` table (type, payload JSONB, status, attempts, run_at, locked_by, locked_at, last_error).
- Workers claim jobs with `SELECT … FOR UPDATE SKIP LOCKED`, and are woken by `LISTEN/NOTIFY`, with polling as a fallback.
- Retries use exponential backoff; jobs that keep failing are marked dead and stay visible.

## Consequences

- One service fewer to install, back up and monitor; the queue is inspectable with plain SQL.
- Both languages use the same table through SQL; there is no shared queue library.
- If throughput ever outgrows PostgreSQL, the queue sits behind a small interface and can be replaced.
