# Phase 2 database: entity-relationship diagram

The decisions behind the schema are in [ADR 0011](../adr/0011-phase-2-database-schema.md). The migrations in [`db/`](../../db/src/untraded_db/migrations/versions/) are the source of truth (ADR 0006); this page shows the schema **after the last one, 0013**. [schema.sql](schema.sql) is the reference schema of ADR 0011, kept identical to migration 0001, which a test checks (`db/tests/test_migrations.py`): it does not hold the later migrations.

Every table and column is shown. Solid lines are foreign keys; dotted lines are links by Steam id that have no foreign key constraint (event and metric rows keep the Steam ids of every player of a match). Types: `char1` is `char(1)`, `char64` is `char(64)`, `text_array` is `text[]`, `double` is `double precision`.

| Migration | Adds |
|---|---|
| 0001 initial | the reference schema of ADR 0011 (tenancy, ingestion, matches, canonical events, metrics, advice, job queue, row-level security) |
| 0002 sessions | `match.ended_at`, `auth_session`, play sessions and their report, the `untraded_api` role |
| 0003 metric direction | `metric_definition.better` |
| 0004 level reference | `level_reference`; `play_session.reference_kind`, `reference_level_low`, `reference_level_high` |
| 0005 session advice | `advice.session_id`, `cost`, `events`, `rounds_touched`, `rounds_lost`; the API may write `advice_feedback` |
| 0006 metric cases | `metric_definition.cases`, `signed` |
| 0007 consent | `consent`, the `consent_current` view |
| 0008 invitations | `invitation`; first sign-in of an invited account; the player's own source functions |
| 0009 erasure | `request_erasure`, `request_my_erasure` |
| 0010 uploads | `match_source.rejected`; the upload functions |
| 0011 invitation requests | `invitation_request`; `request_invitation(steam, persona)` for the API role |
| 0012 Untraded Rating | `metric_wide_current.untraded` |
| 0013 blinded bots | `blind.victim` nullable |

## Tenancy and players

```mermaid
erDiagram
    app_user ||--o{ workspace : created
    app_user ||--o{ membership : "belongs to"
    workspace ||--o{ membership : has
    workspace ||--o{ workspace_role : defines
    workspace_role ||--o{ membership : grants
    workspace ||--o{ workspace_player : follows
    player ||--o{ workspace_player : "followed in"
    workspace ||--o{ roster : has
    roster ||--o{ roster_member : lists
    player ||--o{ roster_member : "is in"
    app_user |o..o| player : "same steam_id"
    app_user |o--o{ invitation : invited
    app_user ||--o{ consent : gives
    app_user ||--o{ auth_session : "signs in with"

    app_user {
        uuid id PK
        bigint steam_id UK
        text display_name
        text locale "default en"
        timestamptz created_at
        timestamptz deleted_at "soft delete"
    }
    player {
        bigint steam_id PK
        text last_name
        timestamptz first_seen_at
        boolean benchmark_opt_out
    }
    workspace {
        uuid id PK
        enum kind "personal | team"
        text name
        citext slug UK
        text plan "default free"
        uuid created_by FK
        timestamptz created_at
    }
    workspace_role {
        uuid id PK
        uuid workspace_id FK "unique with name"
        text name
        text_array permissions
    }
    membership {
        uuid workspace_id PK, FK
        uuid user_id PK, FK
        uuid role_id FK
        timestamptz joined_at
    }
    workspace_player {
        uuid workspace_id PK, FK
        bigint steam_id PK, FK
        boolean share_solo
        timestamptz added_at
    }
    roster {
        uuid id PK
        uuid workspace_id FK
        text name
        boolean active
    }
    roster_member {
        uuid roster_id PK, FK
        bigint steam_id PK, FK
        date valid_from PK
        date valid_to
        enum role "starter | standin"
    }
    invitation {
        bigint steam_id PK
        text display_name
        uuid invited_by FK "set null"
        timestamptz created_at
        timestamptz accepted_at "first sign-in"
    }
    invitation_request {
        bigint steam_id PK
        text persona_name "public Steam name, if read"
        timestamptz requested_at
    }
    consent {
        bigint id PK "identity"
        uuid user_id FK
        text text_version
        boolean analysis
        boolean research_corpus "only with analysis"
        timestamptz recorded_at
        text recorded_by
    }
    auth_session {
        bytea token_hash PK "sha256 of the cookie token"
        uuid user_id FK
        timestamptz created_at
        timestamptz last_seen_at
        timestamptz expires_at
    }
```

- `consent` is never updated: a player's consent is their latest row, which the view `consent_current` (`user_id`, `text_version`, `analysis`, `research_corpus`, `recorded_at`) returns.
- An invited Steam account becomes a user, with a personal workspace (slug `u-{steam_id}`) and an `owner` role (`*`), at its first sign-in (`open_auth_session`).

## Ingestion and matches

```mermaid
erDiagram
    app_user ||--o{ ingest_source : owns
    match ||--o{ match_source : "arrived through"
    ingest_source |o--o{ match_source : brought
    match ||--o{ match_player : has
    player ||--o{ match_player : "played in"
    workspace ||--o{ workspace_match : sees
    match ||--o{ workspace_match : "seen by"

    ingest_source {
        uuid id PK
        uuid user_id FK
        enum kind "valve_bot | renown | upload | url | scrim_webhook | faceit_extension | faceit_api"
        jsonb config "non-secret settings"
        bytea secret "encrypted by the application"
        boolean enabled
        timestamptz last_success_at
        text last_error
        timestamptz created_at
    }
    match {
        uuid id PK
        char64 sha256 UK "decompressed demo, null until downloaded"
        enum mode "premier | faceit | esea | scrim | pro"
        enum status "pending | downloading | parsing | ready | failed | unavailable"
        timestamptz played_at
        timestamptz ended_at
        text map
        text game_build
        real tickrate
        smallint rounds_played
        smallint first_round
        smallint score_a
        smallint score_b
        text team_a_name
        text team_b_name
        text schema_version "canonical schema"
        text parser_version
        text_array unavailable
        text demo_key "store key of the raw demo"
        timestamptz demo_deleted_at "retention"
        text parquet_prefix "matches/{id}"
        text error
        timestamptz created_at
        timestamptz parsed_at
    }
    match_source {
        enum kind PK "ingest_kind"
        text external_id PK
        uuid match_id FK
        uuid source_id FK "set null"
        timestamptz received_at
        text rejected "why an upload was refused"
    }
    match_player {
        uuid match_id PK, FK
        bigint steam_id PK, FK
        char1 team "A | B"
        text name "in that match"
        smallint rounds_on_team
        integer rank
    }
    workspace_match {
        uuid workspace_id PK, FK
        uuid match_id PK, FK
        enum reason "own | shared | roster"
    }
```

`match_source.rejected` is a stable code: `not_a_demo`, `corrupt`, `too_large`, `unsupported_mode`, `not_a_player`.

## Canonical events and the round model

Copies of the Parquet tables useful in SQL ([canonical tables](../canonical-tables.md), schema 1.1, and `round_player` of the [round model](../round-model.md)). Shots, grenade paths, bomb events, inventory changes, player ticks and the other derived tables stay in Parquet only.

```mermaid
erDiagram
    match ||--o{ round : has
    match ||--o{ kill : has
    match ||--o{ damage : has
    match ||--o{ blind : has
    match ||--o{ grenade : has
    match ||--o{ economy : has
    match ||--o{ round_player : has
    player |o..o{ kill : "attacker, victim, assister"
    player ||..o{ round_player : "steam_id"

    round {
        uuid match_id PK, FK
        smallint round PK
        integer start_tick
        integer freeze_end_tick
        integer end_tick
        integer official_end_tick
        text winner_side "CT | T"
        char1 winner_team "A | B"
        text reason
        char1 ct_team
        smallint score_a
        smallint score_b
        boolean is_overtime
        integer bomb_planted_tick
        char1 bomb_site
        bigint bomb_planter
        integer bomb_defused_tick
        integer bomb_exploded_tick
    }
    kill {
        uuid match_id PK, FK
        integer tick PK
        smallint seq PK "order on the same tick"
        smallint round
        bigint attacker
        bigint victim "null for a bot nobody controls"
        boolean victim_bot
        bigint assister
        boolean flash_assist
        text weapon
        boolean headshot
        boolean wallbang
        boolean through_smoke
        boolean attacker_blind
        text attacker_side
        text victim_side
        boolean is_team_kill
        boolean is_suicide
        real attacker_x
        real attacker_y
        real attacker_z
        real victim_x
        real victim_y
        real victim_z
        text attacker_place
        text victim_place
    }
    damage {
        uuid match_id PK, FK
        integer tick PK
        smallint seq PK
        smallint round
        bigint attacker
        bigint victim
        text weapon
        smallint hitgroup
        smallint damage "health lost (capped)"
        smallint dmg_armor
        boolean is_team_damage
        integer grenade_id
    }
    blind {
        uuid match_id PK, FK
        integer tick PK
        smallint seq PK
        smallint round
        bigint victim "null for a bot nobody controls"
        bigint flasher
        integer grenade_id
        real duration
        boolean is_teammate
        boolean is_self
    }
    grenade {
        uuid match_id PK, FK
        integer grenade_id PK
        smallint round
        bigint thrower
        text side
        text type
        integer throw_tick
        real throw_x
        real throw_y
        real throw_z
        integer detonate_tick
        real detonate_x
        real detonate_y
        real detonate_z
        integer end_tick
    }
    economy {
        uuid match_id PK, FK
        smallint round PK
        bigint steam_id PK
        text side
        integer money_start
        integer spent
        integer equip_value
        integer round_start_equip_value
        smallint armor
        boolean has_helmet
        boolean has_defuser
    }
    round_player {
        uuid match_id PK, FK
        smallint round PK
        bigint steam_id PK
        char1 team
        text side
        smallint kills
        smallint deaths
        smallint assists
        smallint flash_assists
        integer damage
        boolean survived
        integer death_tick
        real death_trade_delay_s
        boolean opening_kill
        boolean opening_death
        text setup_place
        boolean team_won
        text buy_type "the team's, from team_round"
    }
```

`damage`, `blind`, `grenade` and `economy` also name their players by Steam id, without a constraint, like `kill`.

## Metrics, sessions and advice

```mermaid
erDiagram
    match ||--o{ metric_value : has
    match ||--o{ metric_table_value : has
    metric_definition ||--o{ metric_value : versions
    metric_definition ||--o{ metric_table_value : versions
    metric_definition ||--o{ metric_aggregate : versions
    metric_definition ||--o| metric_current : "current version"
    metric_definition ||--o{ level_reference : versions
    metric_definition ||--o{ play_session_metric : versions
    player ||..o{ metric_value : "steam_id"
    player ||..o{ metric_aggregate : "aggregated for"
    player ||--o{ play_session : plays
    play_session ||--o{ play_session_match : groups
    match ||--o{ play_session_match : "is in"
    play_session ||--o{ play_session_metric : reports
    play_session |o--o{ advice : "priorities of"
    workspace ||--o{ advice : "shown in"
    player ||..o{ advice : receives
    advice ||--o{ advice_feedback : gets
    app_user ||--o{ advice_feedback : votes

    metric_definition {
        text metric_id PK
        text version PK
        text name
        text unit
        text kind "value | table"
        jsonb params "defaults"
        text doc
        text better "higher | lower | neutral"
        text_array cases "what a rate stands on"
        boolean signed "can be negative"
        timestamptz created_at
    }
    metric_current {
        text metric_id PK, FK
        text version FK
    }
    metric_value {
        uuid match_id PK, FK
        bigint steam_id PK
        enum scope PK "match | ct | t"
        text metric_id PK, FK
        text version PK, FK
        text params_hash PK "default for the defaults"
        double value "null when undefined"
        timestamptz computed_at
    }
    metric_table_value {
        uuid match_id PK, FK
        bigint steam_id PK
        text metric_id PK, FK
        text version PK, FK
        text params_hash PK
        jsonb rows
        timestamptz computed_at
    }
    metric_aggregate {
        bigint steam_id PK
        text selection_hash PK
        jsonb selection
        text metric_id PK, FK
        text version PK, FK
        text params_hash PK
        double value
        integer matches
        integer rounds
        timestamptz computed_at
    }
    level_reference {
        enum mode PK "match_mode"
        integer band_low PK
        integer band_high "exclusive"
        integer used_low "ratings pooled"
        integer used_high
        text metric_id PK, FK
        text version PK, FK
        text basis "value | per_round"
        double value
        integer player_matches
        integer players
        integer rounds
        timestamptz computed_at
    }
    play_session {
        uuid id PK
        bigint steam_id FK "unique with started_at"
        timestamptz started_at
        timestamptz ended_at
        smallint matches
        integer rounds
        date reference_from
        date reference_to
        integer reference_matches
        integer reference_rounds
        boolean enough "reference shown"
        text reference_kind "self | level | none"
        integer reference_level_low
        integer reference_level_high
        jsonb params "window_days, min_matches, min_rounds"
        timestamptz computed_at
    }
    play_session_match {
        uuid session_id PK, FK
        uuid match_id PK, FK
    }
    play_session_metric {
        uuid session_id PK, FK
        text metric_id PK, FK
        text version PK, FK
        text basis "value | per_round"
        double session
        double reference "null when not enough"
        double delta
    }
    advice {
        uuid id PK
        bigint steam_id
        uuid workspace_id FK
        uuid session_id FK "cascade"
        timestamptz session_from
        timestamptz session_to
        text rule_id
        text rule_version
        smallint priority "1 to 3"
        text message_key "i18n key"
        jsonb message_args
        jsonb evidence "rounds and values"
        double cost
        integer events
        integer rounds_touched
        integer rounds_lost
        timestamptz created_at
    }
    advice_feedback {
        uuid advice_id PK, FK
        uuid user_id PK, FK
        smallint vote "-1 | 1"
        text comment
        timestamptz created_at
    }
```

- `metric_wide_current` is a view of the current values (`metric_current`, default parameters), one row per match, player and scope: `kills`, `deaths`, `adr`, `kast`, `hltv1`, `untraded_deaths`, `untraded` (0012). It runs with the caller's rights (`security_invoker`).
- A **play session** groups a player's matches while there is at most one hour between the end of one and the start of the next. Its report compares it with the player's own 30 days before (`reference_kind` `self`), else with a level (`level`, from `level_reference`: anonymous aggregates of a rating band), else nothing (`none`).

## Job queue

```mermaid
erDiagram
    job {
        bigint id PK "identity"
        text kind "download | ingest_upload | parse | session | erase_player"
        jsonb payload
        enum status "queued | running | done | failed | dead"
        smallint priority
        smallint attempts
        smallint max_attempts "default 5"
        timestamptz run_at
        text locked_by
        timestamptz locked_at
        text last_error
        timestamptz created_at
        timestamptz finished_at
    }
```

`job` has no relationships. Inserting a queued job notifies the channel `job_{kind}` (trigger `job_queued`).

## Row-level security and the API role

The API runs each transaction as `untraded_api` (no `BYPASSRLS`) with `app.user_id` set to the signed-in user. The services' own role (worker, collector, migrations) bypasses row-level security.

| Rows visible to `untraded_api` | Tables |
|---|---|
| a match one of the user's workspaces sees (`visible_match`) | `match`, `match_player`, `round`, `kill`, `damage`, `blind`, `grenade`, `economy`, `round_player`, `metric_value`, `metric_table_value`, `workspace_match` |
| through such a match, or a player followed by one of the user's workspaces (`visible_player`) | `player` |
| the user's workspaces (`is_member`) | `workspace`, `membership`, `workspace_role`, `workspace_player`, `roster`, `roster_member`, `advice` |
| followed players (`followed_player`) | `metric_aggregate` |
| the user's own player, or a followed one | `play_session`, `play_session_match`, `play_session_metric` |
| the user's own rows | `ingest_source`, `advice_feedback`, `consent`; `app_user` (and the users they share a workspace with) |
| none (functions only) | `auth_session` |
| no row-level security | `metric_definition`, `metric_current`, `level_reference`, `invitation`, `invitation_request`, `job` |

- `untraded_api` reads every table and view of migrations 0001 and 0002 except `auth_session`, `ingest_source` and `job`, plus `level_reference`, `consent` and `consent_current`; it has no grant on `invitation`. It writes only `advice_feedback` (the user's own votes) and `consent` (insert), and otherwise goes through `SECURITY DEFINER` functions:
  - sign-in: `open_auth_session`, `auth_session_user`, `close_auth_session`;
  - the player's Steam codes: `my_source`, `set_my_source`, `pause_my_sources` (the API never reads a secret);
  - erasure: `request_my_erasure` (`request_erasure`, for any Steam id, is not granted to it); both mark the account deleted, pause its sources, close its sessions, drop a pending invitation and queue an `erase_player` job;
  - uploads: `my_upload_refusal`, `add_my_upload` (a pending `match`, its `match_source` and an `ingest_upload` job), `my_uploads`.
