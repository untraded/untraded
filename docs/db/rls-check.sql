-- SPDX-FileCopyrightText: 2026 The Untraded Authors
-- SPDX-License-Identifier: AGPL-3.0-only
--
-- Checks the tenant isolation (ADR 0011), run in CI once the migrations are applied:
--   uv run untraded-db upgrade && psql -v ON_ERROR_STOP=1 -f docs/db/rls-check.sql
-- It runs in one transaction, rolled back at the end: it leaves the database as it found it.
--
-- Two users, each with a personal workspace; one match played by both, one by Alice only.
-- Bob must see the shared match and its other player (Alice, as a player of that match), but
-- not Alice's own match, nor its opponent.

-- The API role and its rights come from migration 0002.
BEGIN;

INSERT INTO app_user (id, steam_id, display_name) VALUES
    ('00000000-0000-0000-0000-00000000000a', 101, 'alice'),
    ('00000000-0000-0000-0000-00000000000b', 102, 'bob');
INSERT INTO player (steam_id, last_name) VALUES (101, 'alice'), (102, 'bob'), (999, 'opponent');
INSERT INTO workspace (id, kind, name, slug, created_by) VALUES
    ('00000000-0000-0000-0000-0000000000a1', 'personal', 'alice', 'alice', '00000000-0000-0000-0000-00000000000a'),
    ('00000000-0000-0000-0000-0000000000b1', 'personal', 'bob', 'bob', '00000000-0000-0000-0000-00000000000b');
INSERT INTO workspace_role (id, workspace_id, name, permissions) VALUES
    ('00000000-0000-0000-0000-0000000000a2', '00000000-0000-0000-0000-0000000000a1', 'owner', '{matches.read}'),
    ('00000000-0000-0000-0000-0000000000b2', '00000000-0000-0000-0000-0000000000b1', 'owner', '{matches.read}');
INSERT INTO membership (workspace_id, user_id, role_id) VALUES
    ('00000000-0000-0000-0000-0000000000a1', '00000000-0000-0000-0000-00000000000a', '00000000-0000-0000-0000-0000000000a2'),
    ('00000000-0000-0000-0000-0000000000b1', '00000000-0000-0000-0000-00000000000b', '00000000-0000-0000-0000-0000000000b2');
INSERT INTO workspace_player (workspace_id, steam_id) VALUES
    ('00000000-0000-0000-0000-0000000000a1', 101),
    ('00000000-0000-0000-0000-0000000000b1', 102);
INSERT INTO match (id, mode, status) VALUES
    ('00000000-0000-0000-0000-000000000001', 'premier', 'ready'),   -- Alice and Bob
    ('00000000-0000-0000-0000-000000000002', 'premier', 'ready');   -- Alice and the opponent
INSERT INTO match_player (match_id, steam_id, team, name, rounds_on_team) VALUES
    ('00000000-0000-0000-0000-000000000001', 101, 'A', 'alice', 24),
    ('00000000-0000-0000-0000-000000000001', 102, 'B', 'bob', 24),
    ('00000000-0000-0000-0000-000000000002', 101, 'A', 'alice', 24),
    ('00000000-0000-0000-0000-000000000002', 999, 'B', 'opponent', 24);
INSERT INTO workspace_match (workspace_id, match_id, reason) VALUES
    ('00000000-0000-0000-0000-0000000000a1', '00000000-0000-0000-0000-000000000001', 'own'),
    ('00000000-0000-0000-0000-0000000000a1', '00000000-0000-0000-0000-000000000002', 'own'),
    ('00000000-0000-0000-0000-0000000000b1', '00000000-0000-0000-0000-000000000001', 'own');

-- Metrics, read through the wide view (which must not bypass row-level security).
INSERT INTO metric_definition (metric_id, version, name, unit, kind, params, doc) VALUES
    ('base.kills', '1.0.0', 'Kills', 'count', 'value', '{}', '');
INSERT INTO metric_current (metric_id, version) VALUES ('base.kills', '1.0.0');
INSERT INTO metric_value (match_id, steam_id, scope, metric_id, version, params_hash, value) VALUES
    ('00000000-0000-0000-0000-000000000001', 101, 'match', 'base.kills', '1.0.0', 'default', 20),
    ('00000000-0000-0000-0000-000000000001', 102, 'match', 'base.kills', '1.0.0', 'default', 15),
    ('00000000-0000-0000-0000-000000000002', 101, 'match', 'base.kills', '1.0.0', 'default', 25),
    ('00000000-0000-0000-0000-000000000002', 999, 'match', 'base.kills', '1.0.0', 'default', 10);

-- A play session of Alice's (both matches).
INSERT INTO play_session (id, steam_id, started_at, ended_at, matches, rounds, reference_from,
                          reference_to, reference_matches, reference_rounds, enough, params) VALUES
    ('00000000-0000-0000-0000-0000000000c1', 101, now() - interval '3 hours', now(), 2, 48,
     current_date - 30, current_date - 1, 0, 0, false, '{}');
INSERT INTO play_session_match (session_id, match_id) VALUES
    ('00000000-0000-0000-0000-0000000000c1', '00000000-0000-0000-0000-000000000001'),
    ('00000000-0000-0000-0000-0000000000c1', '00000000-0000-0000-0000-000000000002');
INSERT INTO play_session_metric (session_id, metric_id, version, basis, session) VALUES
    ('00000000-0000-0000-0000-0000000000c1', 'base.kills', '1.0.0', 'per_round', 0.94);

CREATE FUNCTION expect(label text, actual bigint, expected bigint) RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    IF actual IS DISTINCT FROM expected THEN
        RAISE EXCEPTION 'RLS check failed: % = %, expected %', label, actual, expected;
    END IF;
END;
$$;
GRANT EXECUTE ON FUNCTION expect(text, bigint, bigint) TO untraded_api;

-- True when the statement is refused for lack of privilege.
CREATE FUNCTION denied(statement text) RETURNS bigint
LANGUAGE plpgsql AS $$
BEGIN
    EXECUTE statement;
    RETURN 0;
EXCEPTION WHEN insufficient_privilege THEN
    RETURN 1;
END;
$$;
GRANT EXECUTE ON FUNCTION denied(text) TO untraded_api;

SET LOCAL ROLE untraded_api;

-- Sign-in: only invited Steam accounts (with a user) get a session.
SELECT expect('session for an unknown account',
    (SELECT count(*) FROM (SELECT open_auth_session(555, sha256('t0'), '1 day') AS u) s
     WHERE u IS NOT NULL), 0);
SELECT expect('session for Bob',
    (SELECT count(*) FROM (SELECT open_auth_session(102, sha256('t1'), '1 day') AS u) s
     WHERE u = '00000000-0000-0000-0000-00000000000b'), 1);
SELECT expect('Bob from his token',
    (SELECT count(*) FROM (SELECT auth_session_user(sha256('t1')) AS u) s
     WHERE u = '00000000-0000-0000-0000-00000000000b'), 1);
SELECT expect('unknown token',
    (SELECT count(*) FROM (SELECT auth_session_user(sha256('nope')) AS u) s
     WHERE u IS NOT NULL), 0);
SELECT close_auth_session(sha256('t1'));
SELECT expect('closed session',
    (SELECT count(*) FROM (SELECT auth_session_user(sha256('t1')) AS u) s
     WHERE u IS NOT NULL), 0);
SELECT expect('auth_session is not readable', denied('SELECT 1 FROM auth_session'), 1);
SELECT expect('ingest_source is not readable', denied('SELECT 1 FROM ingest_source'), 1);
SELECT expect('no writes', denied('UPDATE match SET status = ''failed'''), 1);

-- Nobody signed in: nothing.
SELECT expect('matches without a user', (SELECT count(*) FROM match), 0);
SELECT expect('players without a user', (SELECT count(*) FROM player), 0);

SET LOCAL app.user_id = '00000000-0000-0000-0000-00000000000b';  -- Bob
SELECT expect('matches seen by Bob', (SELECT count(*) FROM match), 1);
SELECT expect('match players seen by Bob', (SELECT count(*) FROM match_player), 2);
SELECT expect('players seen by Bob', (SELECT count(*) FROM player), 2);           -- not 999
SELECT expect('opponent seen by Bob', (SELECT count(*) FROM player WHERE steam_id = 999), 0);
SELECT expect('workspaces seen by Bob', (SELECT count(*) FROM workspace), 1);
SELECT expect('users seen by Bob', (SELECT count(*) FROM app_user), 1);
SELECT expect('metric rows seen by Bob', (SELECT count(*) FROM metric_wide_current), 2);
SELECT expect('metric rows of 999 seen by Bob',
    (SELECT count(*) FROM metric_wide_current WHERE steam_id = 999), 0);
SELECT expect('sessions seen by Bob', (SELECT count(*) FROM play_session), 0);
SELECT expect('session matches seen by Bob', (SELECT count(*) FROM play_session_match), 0);
SELECT expect('session metrics seen by Bob', (SELECT count(*) FROM play_session_metric), 0);

SET LOCAL app.user_id = '00000000-0000-0000-0000-00000000000a';  -- Alice
SELECT expect('matches seen by Alice', (SELECT count(*) FROM match), 2);
SELECT expect('players seen by Alice', (SELECT count(*) FROM player), 3);
SELECT expect('metric rows seen by Alice', (SELECT count(*) FROM metric_wide_current), 4);
SELECT expect('sessions seen by Alice', (SELECT count(*) FROM play_session), 1);
SELECT expect('session matches seen by Alice', (SELECT count(*) FROM play_session_match), 2);
SELECT expect('session metrics seen by Alice', (SELECT count(*) FROM play_session_metric), 1);
ROLLBACK;

\echo 'RLS check passed'
