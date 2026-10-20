-- SPDX-FileCopyrightText: 2026 The Untraded Authors
-- SPDX-License-Identifier: AGPL-3.0-only
--
-- Reference schema of the phase 2 database (ADR 0011). PostgreSQL 16+.
--
-- This file is a design document, not a migration: the schema will be created by Alembic
-- migrations (ADR 0006), which start from it. It must stay valid SQL (checked in CI).
--
-- Conventions:
-- - Steam ids are `bigint` (a SteamID64 is below 2^63).
-- - Times are `timestamptz`, in UTC.
-- - Canonical event tables mirror docs/canonical-tables.md (schema 1.1), keyed by
--   (match_id, ...) instead of a per-file match. Parquet stays the long-term record (ADR 0009).
-- - Tenant data is isolated by row-level security on `app.user_id` (see the end of the file).

CREATE EXTENSION IF NOT EXISTS citext;

-- ===========================================================================================
-- Identity and tenancy
-- ===========================================================================================

-- A person who signed in (Steam OpenID). Not every player is a user.
CREATE TABLE app_user (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    steam_id      bigint NOT NULL UNIQUE,
    display_name  text NOT NULL,
    locale        text NOT NULL DEFAULT 'en',
    created_at    timestamptz NOT NULL DEFAULT now(),
    deleted_at    timestamptz            -- soft delete; personal data is purged by a job
);

-- Every player seen in a match, registered or not. Never exposed outside the matches a viewer
-- may see (vision § 15: "other players: all stored, never exposed outside the match").
CREATE TABLE player (
    steam_id      bigint PRIMARY KEY,
    last_name     text NOT NULL,
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    benchmark_opt_out boolean NOT NULL DEFAULT false   -- anonymous aggregates (vision § 15)
);

CREATE TYPE workspace_kind AS ENUM ('personal', 'team');

-- A personal space (one per user, created at sign-up) or a team.
CREATE TABLE workspace (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    kind       workspace_kind NOT NULL,
    name       text NOT NULL,
    slug       citext NOT NULL UNIQUE,
    plan       text NOT NULL DEFAULT 'free',
    created_by uuid NOT NULL REFERENCES app_user (id),
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Roles are rows, not an enum: each team configures its own roles and permissions.
-- Permissions are dotted names checked by the API, e.g. 'matches.read', 'review.comment',
-- 'roster.edit', 'members.manage', 'settings.edit'. New workspaces get default roles
-- (owner, coach, player, viewer).
CREATE TABLE workspace_role (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    name         text NOT NULL,
    permissions  text[] NOT NULL DEFAULT '{}',
    UNIQUE (workspace_id, name)
);

CREATE TABLE membership (
    workspace_id uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    user_id      uuid NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    role_id      uuid NOT NULL REFERENCES workspace_role (id),
    joined_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, user_id)
);

-- Players a workspace follows. `share_solo` is the player's own choice (vision § 11): when
-- false, a team workspace only sees the matches played together (see workspace_match).
CREATE TABLE workspace_player (
    workspace_id uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    steam_id     bigint NOT NULL REFERENCES player (steam_id),
    share_solo   boolean NOT NULL DEFAULT false,
    added_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, steam_id)
);

CREATE TABLE roster (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    name         text NOT NULL,
    active       boolean NOT NULL DEFAULT true
);

CREATE TYPE roster_role AS ENUM ('starter', 'standin');

-- A match counts for the team when at least 3 roster members played it (vision § 11).
CREATE TABLE roster_member (
    roster_id  uuid NOT NULL REFERENCES roster (id) ON DELETE CASCADE,
    steam_id   bigint NOT NULL REFERENCES player (steam_id),
    role       roster_role NOT NULL DEFAULT 'starter',
    valid_from date NOT NULL DEFAULT current_date,
    valid_to   date,
    PRIMARY KEY (roster_id, steam_id, valid_from)
);

-- ===========================================================================================
-- Ingestion
-- ===========================================================================================

CREATE TYPE ingest_kind AS ENUM (
    'valve_bot', 'renown', 'upload', 'url', 'scrim_webhook', 'faceit_extension', 'faceit_api'
);

-- Where a user's matches come from. Secrets (Steam authentication code, webhook tokens) are
-- encrypted by the application before they reach the database; never stored in clear.
CREATE TABLE ingest_source (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    kind            ingest_kind NOT NULL,
    config          jsonb NOT NULL DEFAULT '{}',   -- non-secret settings (last share code...)
    secret          bytea,                          -- encrypted by the application
    enabled         boolean NOT NULL DEFAULT true,
    last_success_at timestamptz,
    last_error      text,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TYPE match_mode AS ENUM ('premier', 'faceit', 'esea', 'scrim', 'pro');
CREATE TYPE match_status AS ENUM ('pending', 'downloading', 'parsing', 'ready', 'failed', 'unavailable');

-- One row per match, whoever brought it (stored once, ADR 0009). `sha256` is the hash of the
-- decompressed demo, the deduplication key; it is null until the demo has been downloaded.
CREATE TABLE match (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sha256          char(64) UNIQUE,
    mode            match_mode NOT NULL,
    status          match_status NOT NULL DEFAULT 'pending',
    played_at       timestamptz,
    map             text,
    game_build      text,
    tickrate        real,
    rounds_played   smallint,
    first_round     smallint,
    score_a         smallint,
    score_b         smallint,
    team_a_name     text,
    team_b_name     text,
    schema_version  text,                 -- canonical schema that produced the Parquet
    parser_version  text,
    unavailable     text[] NOT NULL DEFAULT '{}',
    demo_key        text,                 -- object store key of the raw demo
    demo_deleted_at timestamptz,          -- retention (ADR 0009)
    parquet_prefix  text,                 -- matches/{id}/ in the object store
    error           text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    parsed_at       timestamptz
);

-- How the match reached us: a match can come from several sources and users.
-- (kind, external_id) is the source's own id (Valve match id, FACEIT match id, upload hash).
CREATE TABLE match_source (
    match_id    uuid NOT NULL REFERENCES match (id) ON DELETE CASCADE,
    kind        ingest_kind NOT NULL,
    external_id text NOT NULL,
    source_id   uuid REFERENCES ingest_source (id) ON DELETE SET NULL,
    received_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (kind, external_id)
);
CREATE INDEX match_source_match ON match_source (match_id);

-- Players of a match (canonical `player` table).
CREATE TABLE match_player (
    match_id       uuid NOT NULL REFERENCES match (id) ON DELETE CASCADE,
    steam_id       bigint NOT NULL REFERENCES player (steam_id),
    team           char(1) NOT NULL CHECK (team IN ('A', 'B')),
    name           text NOT NULL,          -- the name in that match
    rounds_on_team smallint NOT NULL,
    rank           integer,
    PRIMARY KEY (match_id, steam_id)
);
CREATE INDEX match_player_steam ON match_player (steam_id, match_id);

CREATE TYPE access_reason AS ENUM ('own', 'shared', 'roster');

-- Which workspace sees which match, and why. Maintained by the worker when a match is parsed
-- and when follows, sharing choices or rosters change, so access checks are one indexed
-- lookup:
-- - 'own': a personal workspace sees every match of its user's player;
-- - 'shared': a team sees a followed player's matches when that player shares them;
-- - 'roster': a team sees a match where at least 3 members of one of its active rosters played.
CREATE TABLE workspace_match (
    workspace_id uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    match_id     uuid NOT NULL REFERENCES match (id) ON DELETE CASCADE,
    reason       access_reason NOT NULL,
    PRIMARY KEY (workspace_id, match_id)
);
CREATE INDEX workspace_match_match ON workspace_match (match_id);

-- ===========================================================================================
-- Canonical events useful in SQL (copies of the Parquet tables, schema 1.1)
-- Shots, grenade paths, inventory changes and player ticks stay in Parquet only (DuckDB).
-- ===========================================================================================

CREATE TABLE round (
    match_id           uuid NOT NULL REFERENCES match (id) ON DELETE CASCADE,
    round              smallint NOT NULL,
    start_tick         integer NOT NULL,
    freeze_end_tick    integer NOT NULL,
    end_tick           integer NOT NULL,
    official_end_tick  integer,
    winner_side        text CHECK (winner_side IN ('CT', 'T')),
    winner_team        char(1) CHECK (winner_team IN ('A', 'B')),
    reason             text NOT NULL,
    ct_team            char(1) NOT NULL,
    score_a            smallint NOT NULL,
    score_b            smallint NOT NULL,
    is_overtime        boolean NOT NULL,
    bomb_planted_tick  integer,
    bomb_site          char(1),
    bomb_planter       bigint,
    bomb_defused_tick  integer,
    bomb_exploded_tick integer,
    PRIMARY KEY (match_id, round)
);

CREATE TABLE kill (
    match_id       uuid NOT NULL REFERENCES match (id) ON DELETE CASCADE,
    tick           integer NOT NULL,
    round          smallint NOT NULL,
    seq            smallint NOT NULL,       -- order of the kills on the same tick
    attacker       bigint,
    victim         bigint,                  -- null for a bot nobody controls
    victim_bot     boolean NOT NULL,
    assister       bigint,
    flash_assist   boolean NOT NULL,
    weapon         text NOT NULL,
    headshot       boolean NOT NULL,
    wallbang       boolean NOT NULL,
    through_smoke  boolean NOT NULL,
    attacker_blind boolean NOT NULL,
    attacker_side  text,
    victim_side    text,
    is_team_kill   boolean NOT NULL,
    is_suicide     boolean NOT NULL,
    attacker_x real, attacker_y real, attacker_z real,
    victim_x   real, victim_y   real, victim_z   real,
    attacker_place text,
    victim_place   text,
    PRIMARY KEY (match_id, tick, seq)
);
CREATE INDEX kill_attacker ON kill (attacker, match_id);
CREATE INDEX kill_victim ON kill (victim, match_id);

CREATE TABLE damage (
    match_id       uuid NOT NULL REFERENCES match (id) ON DELETE CASCADE,
    tick           integer NOT NULL,
    seq            smallint NOT NULL,
    round          smallint NOT NULL,
    attacker       bigint,
    victim         bigint,
    weapon         text NOT NULL,
    hitgroup       smallint,
    damage         smallint NOT NULL,       -- health lost (capped)
    dmg_armor      smallint NOT NULL,
    is_team_damage boolean NOT NULL,
    grenade_id     integer,
    PRIMARY KEY (match_id, tick, seq)
);

CREATE TABLE blind (
    match_id    uuid NOT NULL REFERENCES match (id) ON DELETE CASCADE,
    tick        integer NOT NULL,
    seq         smallint NOT NULL,
    round       smallint NOT NULL,
    victim      bigint NOT NULL,
    flasher     bigint,
    grenade_id  integer,
    duration    real NOT NULL,
    is_teammate boolean NOT NULL,
    is_self     boolean NOT NULL,
    PRIMARY KEY (match_id, tick, seq)
);

CREATE TABLE grenade (
    match_id      uuid NOT NULL REFERENCES match (id) ON DELETE CASCADE,
    grenade_id    integer NOT NULL,
    round         smallint NOT NULL,
    thrower       bigint,
    side          text,
    type          text NOT NULL,
    throw_tick    integer NOT NULL,
    throw_x real, throw_y real, throw_z real,
    detonate_tick integer,
    detonate_x real, detonate_y real, detonate_z real,
    end_tick      integer,
    PRIMARY KEY (match_id, grenade_id)
);

CREATE TABLE economy (
    match_id                uuid NOT NULL REFERENCES match (id) ON DELETE CASCADE,
    round                   smallint NOT NULL,
    steam_id                bigint NOT NULL,
    side                    text NOT NULL,
    money_start             integer NOT NULL,
    spent                   integer NOT NULL,
    equip_value             integer NOT NULL,
    round_start_equip_value integer NOT NULL,
    armor                   smallint NOT NULL,
    has_helmet              boolean NOT NULL,
    has_defuser             boolean NOT NULL,
    PRIMARY KEY (match_id, round, steam_id)
);

-- The round model's per-player rows (docs/round-model.md): what most screens and aggregates
-- read. Other derived tables (death, clutch, team_round...) stay in Parquet.
CREATE TABLE round_player (
    match_id            uuid NOT NULL REFERENCES match (id) ON DELETE CASCADE,
    round               smallint NOT NULL,
    steam_id            bigint NOT NULL,
    team                char(1) NOT NULL,
    side                text NOT NULL,
    kills               smallint NOT NULL,
    deaths              smallint NOT NULL,
    assists             smallint NOT NULL,
    flash_assists       smallint NOT NULL,
    damage              integer NOT NULL,
    survived            boolean NOT NULL,
    death_tick          integer,
    death_trade_delay_s real,
    opening_kill        boolean NOT NULL,
    opening_death       boolean NOT NULL,
    setup_place         text,
    team_won            boolean NOT NULL,
    buy_type            text,               -- the team's, from team_round
    PRIMARY KEY (match_id, round, steam_id)
);
CREATE INDEX round_player_steam ON round_player (steam_id, match_id);

-- ===========================================================================================
-- Metrics (ADR 0003, 0007)
-- ===========================================================================================

-- The registry as deployed: every (metric, version) the worker has computed.
CREATE TABLE metric_definition (
    metric_id  text NOT NULL,
    version    text NOT NULL,
    name       text NOT NULL,
    unit       text NOT NULL,
    kind       text NOT NULL CHECK (kind IN ('value', 'table')),
    params     jsonb NOT NULL,     -- defaults
    doc        text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (metric_id, version)
);

CREATE TYPE metric_scope AS ENUM ('match', 'ct', 't');

-- Value metrics of one player in one match. Several versions can coexist while a new one is
-- being recomputed; screens read the current version (metric_current).
CREATE TABLE metric_value (
    match_id    uuid NOT NULL REFERENCES match (id) ON DELETE CASCADE,
    steam_id    bigint NOT NULL,
    scope       metric_scope NOT NULL,
    metric_id   text NOT NULL,
    version     text NOT NULL,
    params_hash text NOT NULL,          -- hash of the parameters used (defaults: 'default')
    value       double precision,       -- null when undefined (e.g. HS % without kills)
    computed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (match_id, steam_id, scope, metric_id, version, params_hash),
    FOREIGN KEY (metric_id, version) REFERENCES metric_definition (metric_id, version)
);
CREATE INDEX metric_value_player ON metric_value (steam_id, metric_id, version);

-- Table metrics (zones, heatmap points...): the rows of one player in one match, as JSON.
CREATE TABLE metric_table_value (
    match_id    uuid NOT NULL REFERENCES match (id) ON DELETE CASCADE,
    steam_id    bigint NOT NULL,
    metric_id   text NOT NULL,
    version     text NOT NULL,
    params_hash text NOT NULL,
    rows        jsonb NOT NULL,
    computed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (match_id, steam_id, metric_id, version, params_hash),
    FOREIGN KEY (metric_id, version) REFERENCES metric_definition (metric_id, version)
);

-- Metrics over several matches (a session, 30 days, a map, a side, a buy type...). They are
-- recomputed over all the rounds of the selection, never averaged from per-match values
-- (metrics-v1 § 0), so the worker computes and caches them. `selection` describes the rounds
-- (period, maps, sides, modes, buy types) and `selection_hash` keys the cache.
CREATE TABLE metric_aggregate (
    steam_id       bigint NOT NULL,
    selection_hash text NOT NULL,
    selection      jsonb NOT NULL,
    metric_id      text NOT NULL,
    version        text NOT NULL,
    params_hash    text NOT NULL,
    value          double precision,
    matches        integer NOT NULL,
    rounds         integer NOT NULL,
    computed_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (steam_id, selection_hash, metric_id, version, params_hash),
    FOREIGN KEY (metric_id, version) REFERENCES metric_definition (metric_id, version)
);

-- The version screens use for each metric (the latest fully recomputed one).
CREATE TABLE metric_current (
    metric_id text PRIMARY KEY,
    version   text NOT NULL,
    FOREIGN KEY (metric_id, version) REFERENCES metric_definition (metric_id, version)
);

-- Wide view of the current values, one row per player and match (the "wide views per version"
-- of the plan). Migrations regenerate it when the registry gains metrics.
CREATE VIEW metric_wide_current AS
SELECT v.match_id,
       v.steam_id,
       v.scope,
       max(v.value) FILTER (WHERE v.metric_id = 'base.kills')  AS kills,
       max(v.value) FILTER (WHERE v.metric_id = 'base.deaths') AS deaths,
       max(v.value) FILTER (WHERE v.metric_id = 'base.adr')    AS adr,
       max(v.value) FILTER (WHERE v.metric_id = 'base.kast')   AS kast,
       max(v.value) FILTER (WHERE v.metric_id = 'rating.hltv1') AS hltv1,
       max(v.value) FILTER (WHERE v.metric_id = 'trade.untraded_deaths') AS untraded_deaths
FROM metric_value v
JOIN metric_current c USING (metric_id, version)
WHERE v.params_hash = 'default'
GROUP BY v.match_id, v.steam_id, v.scope;

-- ===========================================================================================
-- Advice (vision § 6.3)
-- ===========================================================================================

CREATE TABLE advice (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    steam_id     bigint NOT NULL,
    workspace_id uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    session_from timestamptz NOT NULL,
    session_to   timestamptz NOT NULL,
    rule_id      text NOT NULL,
    rule_version text NOT NULL,
    priority     smallint NOT NULL CHECK (priority BETWEEN 1 AND 3),
    message_key  text NOT NULL,          -- i18n key; the text is rendered by the client
    message_args jsonb NOT NULL DEFAULT '{}',
    evidence     jsonb NOT NULL,         -- rounds and values that prove it
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX advice_player ON advice (steam_id, created_at DESC);

CREATE TABLE advice_feedback (
    advice_id  uuid NOT NULL REFERENCES advice (id) ON DELETE CASCADE,
    user_id    uuid NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    vote       smallint NOT NULL CHECK (vote IN (-1, 1)),
    comment    text,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (advice_id, user_id)
);

-- ===========================================================================================
-- Job queue (ADR 0004)
-- ===========================================================================================

CREATE TYPE job_status AS ENUM ('queued', 'running', 'done', 'failed', 'dead');

CREATE TABLE job (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kind         text NOT NULL,           -- 'fetch_valve', 'download', 'parse', 'metrics'...
    payload      jsonb NOT NULL DEFAULT '{}',
    status       job_status NOT NULL DEFAULT 'queued',
    priority     smallint NOT NULL DEFAULT 0,
    attempts     smallint NOT NULL DEFAULT 0,
    max_attempts smallint NOT NULL DEFAULT 5,
    run_at       timestamptz NOT NULL DEFAULT now(),
    locked_by    text,
    locked_at    timestamptz,
    last_error   text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    finished_at  timestamptz
);
-- Workers claim with:
--   SELECT id FROM job WHERE status = 'queued' AND run_at <= now()
--   ORDER BY priority DESC, run_at LIMIT 1 FOR UPDATE SKIP LOCKED;
CREATE INDEX job_ready ON job (priority DESC, run_at) WHERE status = 'queued';

CREATE FUNCTION job_notify() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM pg_notify('job_' || NEW.kind, NEW.id::text);
    RETURN NEW;
END;
$$;
CREATE TRIGGER job_queued AFTER INSERT ON job
    FOR EACH ROW WHEN (NEW.status = 'queued') EXECUTE FUNCTION job_notify();

-- ===========================================================================================
-- Tenant isolation (row-level security)
-- ===========================================================================================
-- The API connects as a role without BYPASSRLS and sets the signed-in user per transaction:
--   SET LOCAL app.user_id = '<uuid>';
-- The worker and migrations use a role that bypasses RLS. The application still checks the
-- workspace permissions (e.g. 'matches.read') on top: RLS only guarantees that nothing leaks
-- across workspaces, even through a bug in a query.
-- The helper functions are SECURITY DEFINER so that the policies do not recurse through the
-- RLS of membership and workspace_match.

CREATE FUNCTION current_app_user() RETURNS uuid LANGUAGE sql STABLE AS $$
    SELECT nullif(current_setting('app.user_id', true), '')::uuid
$$;

CREATE FUNCTION is_member(w uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    SELECT EXISTS (
        SELECT 1 FROM membership WHERE workspace_id = w AND user_id = current_app_user()
    )
$$;

CREATE FUNCTION visible_match(m uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    SELECT EXISTS (
        SELECT 1
        FROM workspace_match wm
        JOIN membership ms ON ms.workspace_id = wm.workspace_id
        WHERE wm.match_id = m AND ms.user_id = current_app_user()
    )
$$;

-- A player (name, steam id) is visible only through a match the user may see, or when the
-- player is followed by one of the user's workspaces: never on their own.
CREATE FUNCTION visible_player(p bigint) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    SELECT EXISTS (
        SELECT 1 FROM match_player mp WHERE mp.steam_id = p AND visible_match(mp.match_id)
    ) OR EXISTS (
        SELECT 1 FROM workspace_player wp WHERE wp.steam_id = p AND is_member(wp.workspace_id)
    )
$$;

CREATE FUNCTION followed_player(p bigint) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    SELECT EXISTS (
        SELECT 1 FROM workspace_player wp WHERE wp.steam_id = p AND is_member(wp.workspace_id)
    )
$$;

CREATE FUNCTION shares_workspace(u uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    SELECT EXISTS (SELECT 1 FROM membership m WHERE m.user_id = u AND is_member(m.workspace_id))
$$;

-- Match data: visible when one of the user's workspaces sees the match.
DO $$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'match_player', 'round', 'kill', 'damage', 'blind', 'grenade', 'economy',
        'round_player', 'metric_value', 'metric_table_value', 'workspace_match'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('CREATE POLICY visible ON %I USING (visible_match(match_id))', t);
    END LOOP;
END;
$$;

ALTER TABLE match ENABLE ROW LEVEL SECURITY;
CREATE POLICY visible ON match USING (visible_match(id));

ALTER TABLE player ENABLE ROW LEVEL SECURITY;
CREATE POLICY visible ON player USING (visible_player(steam_id));

-- Workspace data: visible to the workspace's members.
DO $$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'membership', 'workspace_role', 'workspace_player', 'roster', 'advice'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('CREATE POLICY member ON %I USING (is_member(workspace_id))', t);
    END LOOP;
END;
$$;

ALTER TABLE workspace ENABLE ROW LEVEL SECURITY;
CREATE POLICY member ON workspace USING (is_member(id));

ALTER TABLE roster_member ENABLE ROW LEVEL SECURITY;
CREATE POLICY member ON roster_member USING (
    EXISTS (SELECT 1 FROM roster r WHERE r.id = roster_id AND is_member(r.workspace_id))
);

-- Aggregates are computed for followed players only.
ALTER TABLE metric_aggregate ENABLE ROW LEVEL SECURITY;
CREATE POLICY followed ON metric_aggregate USING (followed_player(steam_id));

-- A user's own rows, and the users they share a workspace with.
ALTER TABLE app_user ENABLE ROW LEVEL SECURITY;
CREATE POLICY self ON app_user USING (id = current_app_user() OR shares_workspace(id));
ALTER TABLE ingest_source ENABLE ROW LEVEL SECURITY;
CREATE POLICY self ON ingest_source USING (user_id = current_app_user());
ALTER TABLE advice_feedback ENABLE ROW LEVEL SECURITY;
CREATE POLICY self ON advice_feedback USING (user_id = current_app_user());
