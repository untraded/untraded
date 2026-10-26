# 0009. Storage and retention

- Status: Accepted
- Date: 2026-10-14
- Supersedes: [0005](0005-storage-layout.md)
- Note (2026-10-26): as implemented, an uncompressed `.dem` is stored as received too, without the zstd pass; the Parquet tables are under the match's database id (`matches/{id}/`, `match.parquet_prefix`), not its sha256; the only store so far is the local filesystem. Raw demo retention is `UNTRADED_DEMO_RETENTION_DAYS` (unset: kept).

## Context

ADR 0005 planned to recompress raw demos with zstd, keep them for 90 days in the hosted version, then keep full-rate tick Parquet. Spike S0.6 measured the actual costs:

- zstd brings a demo down to only 0.84, 0.74 and 0.70 of its size at levels 1, 3 and 9. Level 19 reaches 0.60 for about 170 CPU seconds per demo. Valve already serves `.dem.bz2` (about 0.67) and FACEIT `.dem.zst` (0.725): recompressing saves nothing and costs CPU.
- Canonical tables at 16 Hz take about **6 MB per match** in Parquet, 60 times less than the demo. Full-rate ticks would cost several times more and are not needed by any v1 metric.
- Parsing cost grows with each stored prop.
- In a hosted version, **raw demo storage dominates the cost** and grows linearly with retention.

## Decision

- **Raw demos are stored as received**, without recompression: `demos/{sha256}.dem.bz2`, `.dem.zst`, `.dem.gz`, or `.dem` compressed once with zstd level 3 when uploaded uncompressed. The key is the sha256 of the **decompressed** `.dem`, so the same match from two sources is stored once.
- **Canonical tables are the long-term record**: Parquet per match (`matches/{match_id}/{table}.parquet`, zstd), ticks sampled at 16 Hz by default, full rate only on demand. The canonical schema is versioned, and each match records the schema version that produced it.
- **Metrics are recomputed from Parquet**, not from raw demos. The canonical schema therefore includes everything v1 metrics need, plus what planned metrics are known to need. A prop is added only for a stated reason, since each one costs CPU on every match. Data added to the schema later only exists for matches whose raw demo is still available.
- **Retention:**

  | Deployment | Parquet | Raw demos |
  |---|---|---|
  | Self-hosted | Kept | Kept by default (configurable) |
  | Hosted | Kept for the life of the account | Deleted after a period set per plan (default 30 days) |

  A deployment may also delete raw demos right after a successful parse.
- Unchanged from ADR 0005:
  - the object store is the local filesystem or S3-compatible;
  - PostgreSQL stores entities, the event tables useful in SQL, and metric values;
  - a match is stored once and shared through workspaces.

## Consequences

- No CPU is spent on recompression, and deduplication still works across sources.
- Formula changes (ADR 0003) are recomputed from Parquet. A new metric that needs data the schema lacks only applies to new matches and to those still holding a raw demo. Choosing the canonical schema is therefore a long-lived decision, reviewed with each metric catalog.
- A canonical schema change needs a version bump, and a migration or a re-parse of retained demos.
