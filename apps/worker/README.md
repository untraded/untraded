<!--
SPDX-FileCopyrightText: 2026 The Untraded Authors
SPDX-License-Identifier: AGPL-3.0-only
-->

# untraded-worker

Consumes the PostgreSQL job queue (`job` table, ADR 0004) and runs the `untraded` library on the
demos it brings. AGPL-3.0-only.

```bash
just db-up && just db-migrate      # PostgreSQL 16 from compose.dev.yaml, with the migrations
uv run untraded-worker run         # until SIGINT or SIGTERM
uv run untraded-worker replays     # the 2D viewer's round replays of matches parsed before
uv run untraded-worker swings      # the swing table of matches parsed before
```

`run` takes `--once` (stop when no job is ready), `--kinds parse,session` (only those job kinds;
default all) and `--name` (the worker name recorded on its jobs; default the host name).
`replays` and `swings` skip the matches that already have them; `--force` rewrites them all,
after a new replay format or a new win-probability model. Both log and skip a match that fails.

| Variable | Default | Role |
|---|---|---|
| `UNTRADED_DATABASE_URL` | the `compose.dev.yaml` database | PostgreSQL |
| `UNTRADED_STORE_DIR` | `store` | object store: raw demos and Parquet tables (ADR 0009) |
| `UNTRADED_DEMO_RETENTION_DAYS` | unset (kept) | raw demo retention after the parse (ADR 0009) |
| `UNTRADED_UPLOADS_DIR` | `uploads` | where the API writes the demos players send (shared with the API) |
| `UNTRADED_UPLOAD_MAX_DEMO_GB` | `1.5` | the largest decompressed demo a player may send |
| `UNTRADED_ALLOW_PRIVATE_DEMO_URLS` | unset | `1` lets `download` reach private addresses (a server on your own network); otherwise a demo URL never reaches a private, loopback, link-local (cloud metadata) or reserved address, redirects included |

- `queue.py`: claim with `FOR UPDATE SKIP LOCKED`, exponential backoff, `dead` after
  `max_attempts`, abandoned jobs put back after 30 minutes (3 hours for `download`).
- `runner.py`: the loop. The claim commits first; the handler's writes and the completion then
  commit together, and a failure (Rust panics included) is rolled back and recorded. When the
  queue is empty, it runs the periodic tasks (level references, retention).
- `store.py`: the local object store; an S3-compatible one implements the same methods later.
- `jobs.py`: the handlers by kind. `parse` (`{"match_id": ...}`): demo from the store, canonical
  and derived tables (the `swing` table included), round model and metrics (scopes `match`, `ct`,
  `t`), Parquet under `matches/{id}/`, the round replays, SQL tables, `workspace_match`, status
  `ready` (`failed` once the job is dead), then a `session` job per registered player of the
  match. A demo already known by its sha256 is merged into its match. A demo of a mode we do not
  analyse (Competitive or Wingman, from Valve's share-code chain) makes the match `unavailable`
  and its demo is deleted; so does a demo sent by a player who is not in the match, when nothing
  else brought it (`not_a_player`). `download` (`{"match_id": ..., "url": ...}`): resumable HTTP
  download (Valve drops connections), stored as received under `demos/{sha256}{suffix}`, then a
  `parse` job; a demo gone from the server (404, 410) makes the match `unavailable`.
- `download.py`: the resumable download, and the address check of
  `UNTRADED_ALLOW_PRIVATE_DEMO_URLS`.
- `uploads.py`: the `ingest_upload` job (`{"match_id": ..., "file": ...}`), for a demo a player
  sent (`POST /uploads`): checked (a CS2 demo, at most `UNTRADED_UPLOAD_MAX_DEMO_GB`
  decompressed), recognised as Premier when it comes from Valve's servers, copied to the store,
  then a `parse` job. A refused upload keeps its reason in `match_source.rejected` (`not_a_demo`,
  `corrupt`, `too_large`, then at the parse `unsupported_mode` or `not_a_player`); a dead job
  fails the match and deletes the file.
- `replays.py`: the 2D viewer's round replays (`untraded.replay`, `docs/replay-format.md`), one
  per round under `matches/{id}/replay/{round}.json.gz`, with the round's win-probability curve
  and swings. Written by the parse (a failure there leaves the analysis standing), and by
  `untraded-worker replays`.
- `swings.py`: `untraded-worker swings`, the `swing` table of matches parsed before it existed,
  or again after a new win-probability model.
- `sessions.py`: the `session` job (`{"steam_id": ..., "match_id": ...}`). Matches with at most
  one hour between the end of one and the start of the next form a session; a match that joins
  two sessions merges them. Its report (`play_session_metric`) compares it with the player's
  30 days before (`untraded.reference`), recomputed from the Parquet tables. A match is also in
  the reference of the sessions of the 30 days after it: when it arrives late (a demo sent days
  later), those sessions are recomputed too.
- `advice.py`: the session's priorities, right after its report: the rules of `untraded.advice`
  against the same reference, the three costliest kept, each event with its `demo_gototick`.
- `levels.py`: references by level (Premier rating bands of 2,500 points), pooled from every
  player of the collected matches as anonymous aggregates (opt-out respected, at least 20
  players), recomputed hourly; sessions without enough history of their own use them.
- `retention.py`: deletes raw demos `UNTRADED_DEMO_RETENTION_DAYS` after the parse (unset: kept;
  0: at the next sweep), swept every 10 minutes when the worker is idle. A demo another match
  still needs stays.
- `erase.py`: the `erase_player` job (`{"steam_id": ...}`), queued when a player asks for
  erasure or an admin erases them: their account with its sources, consents, sign-in sessions,
  votes, invitation and personal workspace; their play sessions, advice and aggregates; the
  matches no other user played in (rows, Parquet and raw demo). In the other matches they stay
  one of the ten players, left out of the level references.
- `analysis.py` and `load.py`: the analysis without a database, and its loading (idempotent:
  a reparse replaces the match's rows).

The tests marked `db` need `UNTRADED_TEST_DATABASE_URL` (they empty the `job` table); CI runs
them on PostgreSQL 16.
