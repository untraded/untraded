<!--
SPDX-FileCopyrightText: 2026 The Untraded Authors
SPDX-License-Identifier: AGPL-3.0-only
-->

# untraded-worker

Consumes the PostgreSQL job queue (`job` table, ADR 0004) and runs the `untraded` library on the
demos it brings. AGPL-3.0-only.

```bash
just db-up && just db-migrate      # PostgreSQL 16 from compose.dev.yaml, with the migrations
uv run untraded-worker run         # until SIGINT or SIGTERM; --once stops when the queue is empty
```

| Variable | Default | Role |
|---|---|---|
| `UNTRADED_DATABASE_URL` | the `compose.dev.yaml` database | PostgreSQL |
| `UNTRADED_STORE_DIR` | `store` | object store: raw demos and Parquet tables (ADR 0009) |

- `queue.py`: claim with `FOR UPDATE SKIP LOCKED`, exponential backoff, `dead` after
  `max_attempts`, abandoned jobs put back after 30 minutes.
- `runner.py`: the loop. The claim commits first; the handler's writes and the completion then
  commit together, and a failure (Rust panics included) is rolled back and recorded.
- `store.py`: the local object store; an S3-compatible one implements the same methods later.
- `jobs.py`: the handlers by kind (`parse` and `download` come next).

The tests marked `db` need `UNTRADED_TEST_DATABASE_URL` (they empty the `job` table); CI runs
them on PostgreSQL 16.
