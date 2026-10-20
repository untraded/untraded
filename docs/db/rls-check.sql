-- SPDX-FileCopyrightText: 2026 The Untraded Authors
-- SPDX-License-Identifier: AGPL-3.0-only
--
-- Checks the tenant isolation of docs/db/schema.sql (ADR 0011), run in CI after the schema:
--   psql -v ON_ERROR_STOP=1 -f docs/db/schema.sql -f docs/db/rls-check.sql
--
-- Two users, each with a personal workspace; one match played by both, one by Alice only.
-- Bob must see the shared match and its other player (Alice, as a player of that match), but
-- not Alice's own match, nor its opponent.

CREATE ROLE untraded_api NOLOGIN;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO untraded_api;

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

CREATE FUNCTION expect(label text, actual bigint, expected bigint) RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    IF actual IS DISTINCT FROM expected THEN
        RAISE EXCEPTION 'RLS check failed: % = %, expected %', label, actual, expected;
    END IF;
END;
$$;
GRANT EXECUTE ON FUNCTION expect(text, bigint, bigint) TO untraded_api;

BEGIN;
SET LOCAL ROLE untraded_api;

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

SET LOCAL app.user_id = '00000000-0000-0000-0000-00000000000a';  -- Alice
SELECT expect('matches seen by Alice', (SELECT count(*) FROM match), 2);
SELECT expect('players seen by Alice', (SELECT count(*) FROM player), 3);
COMMIT;

\echo 'RLS check passed'
