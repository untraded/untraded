# 0005. Storage layout

- Status: Accepted
- Date: 2026-10-13

## Context

A match produces a raw demo (tens to a hundred-plus MB), canonical tables (events and sampled ticks), and aggregates. The same match can be uploaded by several players or workspaces. Valve demos expire after about 30 days, so we are the only remaining copy.

## Decision

- **Object storage** (local filesystem when self-hosted, S3-compatible when hosted):
  - raw demos are **content-addressed and recompressed with zstd**: `demos/{sha256}.dem.zst`;
  - canonical tables are stored as **Parquet per match**: `matches/{match_id}/{table}.parquet`, queryable with DuckDB.
- **PostgreSQL** stores entities (users, workspaces, players, matches, rounds), the event tables useful in SQL, and metric values.
- A match is **stored once**; access is granted through the presence of a followed player in a workspace.
- Retention: everything kept when self-hosted; when hosted, raw demos for 90 days, then full-rate tick Parquet only.

## Consequences

- Deduplication comes for free (same sha256 means same demo).
- Formula changes can be recomputed from raw demos or full tick Parquet.
- Storage cost per match must be measured in phase 0 (spike S0.6).
