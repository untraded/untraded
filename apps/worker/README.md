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
| `UNTRADED_DEMO_RETENTION_DAYS` | unset (kept) | raw demo retention after the parse (ADR 0009) |

- `queue.py`: claim with `FOR UPDATE SKIP LOCKED`, exponential backoff, `dead` after
  `max_attempts`, abandoned jobs put back after 30 minutes (3 hours for `download`).
- `runner.py`: the loop. The claim commits first; the handler's writes and the completion then
  commit together, and a failure (Rust panics included) is rolled back and recorded.
- `store.py`: the local object store; an S3-compatible one implements the same methods later.
- `jobs.py`: the handlers by kind. `parse` (`{"match_id": ...}`): demo from the store, canonical
  tables, round model and metrics (scopes `match`, `ct`, `t`), Parquet under `matches/{id}/`,
  SQL tables, `workspace_match`, status `ready` (`failed` once the job is dead). A demo already
  known by its sha256 is merged into its match. `download` (`{"match_id": ..., "url": ...}`):
  resumable HTTP download (Valve drops connections), stored as received under
  `demos/{sha256}{suffix}`, then a `parse` job; a demo gone from the server (404, 410) makes the
  match `unavailable`.
- `sessions.py`: the `session` job, queued after each parse for every invited player of the
  match. Matches with at most one hour between the end of one and the start of the next form a
  session; its report (`play_session_metric`) compares it with the player's 30 days before
  (`untraded.reference`), recomputed from the Parquet tables.
- `advice.py`: the session's priorities, right after its report: the rules of `untraded.advice`
  against the same reference, the three costliest kept, each event with its `demo_gototick`.
- `levels.py`: references by level (Premier rating bands of 2,500 points), pooled from every
  player of the collected matches as anonymous aggregates (opt-out respected, at least 20
  players), recomputed hourly; sessions without enough history of their own use them.
- `retention.py`: deletes raw demos `UNTRADED_DEMO_RETENTION_DAYS` after the parse (unset: kept;
  0: at the next sweep), swept when the worker is idle.
- `analysis.py` and `load.py`: the analysis without a database, and its loading (idempotent:
  a reparse replaces the match's rows).

The tests marked `db` need `UNTRADED_TEST_DATABASE_URL` (they empty the `job` table); CI runs
them on PostgreSQL 16.
