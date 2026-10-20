# Phase 2 database: entity-relationship diagram

The reference schema is [schema.sql](schema.sql), and the decisions behind it are in [ADR 0011](../adr/0011-phase-2-database-schema.md). Only keys and the columns that carry a relationship are shown here.

## Tenancy, players and access

```mermaid
erDiagram
    app_user ||--o{ membership : "belongs to"
    workspace ||--o{ membership : has
    workspace ||--o{ workspace_role : defines
    workspace_role ||--o{ membership : "grants"
    workspace ||--o{ workspace_player : follows
    player ||--o{ workspace_player : "followed in"
    workspace ||--o{ roster : has
    roster ||--o{ roster_member : lists
    player ||--o{ roster_member : "is in"
    workspace ||--o{ workspace_match : sees
    match ||--o{ workspace_match : "seen by"
    app_user ||--o{ ingest_source : owns

    app_user {
        uuid id PK
        bigint steam_id UK
    }
    player {
        bigint steam_id PK
        text last_name
        bool benchmark_opt_out
    }
    workspace {
        uuid id PK
        enum kind "personal | team"
        citext slug UK
    }
    workspace_role {
        uuid id PK
        uuid workspace_id FK
        text_array permissions
    }
    membership {
        uuid workspace_id PK
        uuid user_id PK
        uuid role_id FK
    }
    workspace_player {
        uuid workspace_id PK
        bigint steam_id PK
        bool share_solo
    }
    roster {
        uuid id PK
        uuid workspace_id FK
    }
    roster_member {
        uuid roster_id PK
        bigint steam_id PK
        date valid_from PK
        enum role "starter | standin"
    }
    workspace_match {
        uuid workspace_id PK
        uuid match_id PK
        enum reason "own | shared | roster"
    }
    ingest_source {
        uuid id PK
        uuid user_id FK
        enum kind
        bytea secret "encrypted"
    }
```

## Matches, events and metrics

```mermaid
erDiagram
    match ||--o{ match_source : "arrived through"
    ingest_source |o--o{ match_source : brought
    match ||--o{ match_player : has
    player ||--o{ match_player : "played in"
    match ||--o{ round : has
    match ||--o{ kill : has
    match ||--o{ damage : has
    match ||--o{ blind : has
    match ||--o{ grenade : has
    match ||--o{ economy : has
    match ||--o{ round_player : has
    match ||--o{ metric_value : has
    match ||--o{ metric_table_value : has
    metric_definition ||--o{ metric_value : versions
    metric_definition ||--o{ metric_table_value : versions
    metric_definition ||--o{ metric_aggregate : versions
    metric_definition ||--o| metric_current : "current version"
    player ||--o{ metric_aggregate : "aggregated for"
    player ||--o{ advice : receives
    advice ||--o{ advice_feedback : gets

    match {
        uuid id PK
        char64 sha256 UK "decompressed demo"
        enum mode
        enum status
        text schema_version
        text demo_key "object store"
        text parquet_prefix "object store"
    }
    match_source {
        enum kind PK
        text external_id PK
        uuid match_id FK
    }
    match_player {
        uuid match_id PK
        bigint steam_id PK
        char team "A | B"
    }
    round {
        uuid match_id PK
        smallint round PK
    }
    kill {
        uuid match_id PK
        int tick PK
        smallint seq PK
        bigint attacker
        bigint victim
    }
    round_player {
        uuid match_id PK
        smallint round PK
        bigint steam_id PK
    }
    metric_definition {
        text metric_id PK
        text version PK
        jsonb params
    }
    metric_value {
        uuid match_id PK
        bigint steam_id PK
        enum scope PK "match | ct | t"
        text metric_id PK
        text version PK
        text params_hash PK
        float value
    }
    metric_aggregate {
        bigint steam_id PK
        text selection_hash PK
        text metric_id PK
        text version PK
        text params_hash PK
        jsonb selection
    }
    advice {
        uuid id PK
        bigint steam_id
        uuid workspace_id FK
        text rule_id
        jsonb evidence
    }
    advice_feedback {
        uuid advice_id PK
        uuid user_id PK
        smallint vote
    }
```

`damage`, `blind`, `grenade` and `economy` are keyed like `kill` (by `match_id` with a tick and a sequence, a grenade id, or a round and a player). The job queue (`job`) has no relationships.
