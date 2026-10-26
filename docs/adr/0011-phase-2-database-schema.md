# 0011. Phase 2 database schema

- Status: Accepted
- Date: 2026-10-21
- Builds on: [0004](0004-postgres-as-job-queue.md), [0006](0006-schema-ownership.md), [0009](0009-storage-and-retention.md)
- Note (2026-10-26): implemented by migrations 0001 (this reference schema, unchanged) to 0010, which add sessions, references by level, consent, invitations, erasure and uploads: the current schema is in [docs/db/erd.md](../db/erd.md). The API connects as the services' user and switches to the `untraded_api` role in each transaction (migration 0002); the collector, like the worker, bypasses RLS. CI applies the migrations (`untraded-db upgrade`) before the isolation check.

## Context

Phase 2 adds the web app, the API, the worker and the collector. They share one PostgreSQL database. Earlier decisions already frame it:

- PostgreSQL holds the entities, the event tables useful in SQL, the metric values, and the job queue (ADR 0004, 0009).
- The Parquet tables of each match are the long-term record (ADR 0009).
- A match is stored once and shared through workspaces.
- The schema is owned by Python, with Alembic migrations (ADR 0006).

The product adds its own rules:

- workspaces are multi-tenant from the start, personal or team, with roles and **configurable permissions**;
- each player decides whether their solo matches are shared with a team;
- a match counts for a team when **at least 3 roster members** played it;
- players who are not users are stored but **never exposed outside the matches a viewer may see**;
- per-period metrics are **recomputed over all the rounds** of the selection, never averaged from per-match values (metrics-v1 § 0);
- metrics are versioned, and formula changes are recomputed.

This ADR fixes the shape of the schema before any implementation. The reference DDL is [docs/db/schema.sql](../db/schema.sql) and the diagram is [docs/db/erd.md](../db/erd.md).

## Decision

1. **Identity.**
   - `app_user` is a person who signed in through Steam. `player` is every SteamID seen in a match, whether registered or not.
   - Steam ids are `bigint`, and the other keys are UUIDs.
   - Users are soft-deleted; their personal data is then purged by a job.
2. **Tenancy.**
   - A `workspace` is personal or a team, with members (`membership`).
   - Roles are **rows of `workspace_role`**, each holding a list of permission names (`matches.read`, `review.comment`, `roster.edit`…). This makes them configurable per team; a new workspace gets default roles.
   - A workspace follows players (`workspace_player`). `share_solo` records the player's own choice to share their solo matches.
   - Rosters list starters and stand-ins, with validity dates.
3. **Access to matches is materialized** in `workspace_match` (workspace, match, reason: `own`, `shared` or `roster`).
   - The worker maintains it when a match is parsed and when follows, sharing choices or rosters change.
   - Every access check is then one indexed lookup, instead of evaluating the 3-player rule and the sharing choices in each query.
4. **Ingestion.**
   - `match` is unique on the sha256 of the decompressed demo, the deduplication key of ADR 0009.
   - `match_source` records every way a match arrived, keyed by the source and its own id (Valve match id, FACEIT match id…). Two users uploading the same match create one match and two sources.
   - `ingest_source` holds each user's sources. Secrets (Steam authentication code, webhook tokens) are **encrypted by the application** before storage.
   - A match moves through `pending → downloading → parsing → ready`, or ends as `failed` or `unavailable`.
5. **Events in SQL.**
   - Copied to PostgreSQL: rounds, kills, damage, blinds, grenades and economy, plus the round model's `round_player` rows. Screens and aggregates read these.
   - Left in Parquet only, read with DuckDB when needed: shots, grenade paths, inventory changes and player ticks, which make up most of the volume.
   - The SQL copies keep the columns that queries need; Parquet keeps them all.
6. **Metrics.**
   - `metric_definition` stores the deployed registry: id, version, unit, kind and default parameters.
   - `metric_value` holds one value per match, player, scope (`match`, `ct`, `t`), metric, version and parameter hash. Several versions coexist while a new one is recomputed, and `metric_current` says which one screens read.
   - Table metrics are stored as JSON rows in `metric_table_value`.
   - **Multi-match metrics** (a session, 30 days, a map, a buy type) are computed by the worker over all the rounds of the selection and cached in `metric_aggregate`, keyed by a hash of the selection. They are never derived in SQL from per-match values.
   - Wide views (`metric_wide_current`) give one row per player and match for the screens. Migrations regenerate them when metrics are added.
7. **Advice** stores what the rules produced:
   - the rule and its version, the priority (1 to 3), an i18n message key with its arguments, and the **evidence** (rounds and values);
   - per-user feedback, a vote of +1 or −1 with an optional comment.
8. **Jobs** follow ADR 0004:
   - workers claim them with `FOR UPDATE SKIP LOCKED` over a partial index on queued jobs;
   - an insert trigger wakes them with `NOTIFY job_<kind>`.
9. **Tenant isolation with row-level security** (RLS), on top of the API's permission checks.
   - The API connects with a role that cannot bypass RLS and sets `app.user_id` per transaction.
   - Match data is visible when one of the user's workspaces sees the match. A player is visible only through such a match, or when one of the user's workspaces follows them. Workspace data is visible to its members, and personal rows to their owner.
   - The policies call `SECURITY DEFINER` helpers, so they do not recurse.
   - The worker and the migrations use a role that bypasses RLS.
   - CI applies the schema to PostgreSQL 16 and runs an isolation check: [docs/db/rls-check.sql](../db/rls-check.sql).

## Consequences

- A bug in a query cannot leak one workspace's matches, or a non-user's name, to another workspace. That rule ("never exposed outside the match") is enforced by the database, not only by the API. The price is a function call per row on protected tables. `workspace_match` keeps it to an index lookup, and it will be measured in phase 2.
- `workspace_match` is derived data: a missed update hides or shows a match wrongly. The worker owns it, and it can be rebuilt from scratch from follows, sharing choices, rosters and `match_player`.
- Aggregates are a cache, so changing a metric version or the round model invalidates them. They are recomputed lazily, on the next read, or eagerly by a job.
- A 24-round match adds about 1,700 event rows and 2,200 metric values (72 metrics × 10 players × 3 scopes). That is fine up to millions of matches. Partitioning by `match_id` stays possible without changing the keys.
- Phase 3 features (2D viewer, playlists, comments, tags, public profiles, scrim webhooks) add tables later. This ADR does not fix them.
- `schema.sql` is a design reference. The phase 2 Alembic migrations start from it, and from then on the migrations are the source of truth (ADR 0006).
