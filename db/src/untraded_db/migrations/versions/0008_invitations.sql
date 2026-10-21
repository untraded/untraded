-- SPDX-FileCopyrightText: 2026 The Untraded Authors
-- SPDX-License-Identifier: AGPL-3.0-only
--
-- Invitations: an admin invites a Steam account, and its first sign-in creates the user with
-- their personal workspace. The player then gives their consent and their match history codes
-- on the site, so following them needs no command line.

CREATE TABLE invitation (
    steam_id     bigint PRIMARY KEY,
    display_name text NOT NULL,           -- shown to the admin, and the user's first name
    invited_by   uuid REFERENCES app_user (id) ON DELETE SET NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    accepted_at  timestamptz              -- the first sign-in
);

-- A session for a user, or for an invited Steam account signing in for the first time: it
-- becomes a user with a personal workspace (as the collector's add-source does).
CREATE OR REPLACE FUNCTION open_auth_session(steam bigint, token bytea, ttl interval)
RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
    found uuid;
    invited text;
    space uuid;
    owner uuid;
BEGIN
    SELECT id INTO found FROM app_user WHERE steam_id = steam AND deleted_at IS NULL;
    IF found IS NULL THEN
        SELECT display_name INTO invited FROM invitation
        WHERE steam_id = steam AND accepted_at IS NULL
        FOR UPDATE;
        IF invited IS NULL OR EXISTS (SELECT 1 FROM app_user WHERE steam_id = steam) THEN
            RETURN NULL;  -- not invited, or a deleted user
        END IF;
        INSERT INTO app_user (steam_id, display_name) VALUES (steam, invited)
        RETURNING id INTO found;
        INSERT INTO workspace (kind, name, slug, created_by)
        VALUES ('personal', invited, 'u-' || steam, found)
        RETURNING id INTO space;
        INSERT INTO workspace_role (workspace_id, name, permissions)
        VALUES (space, 'owner', ARRAY['*'])
        RETURNING id INTO owner;
        INSERT INTO membership (workspace_id, user_id, role_id) VALUES (space, found, owner);
        UPDATE invitation SET accepted_at = now() WHERE steam_id = steam;
    END IF;
    INSERT INTO auth_session (token_hash, user_id, expires_at)
    VALUES (token, found, now() + ttl);
    RETURN found;
END;
$$;

-- The player records their own consent and their own source (row-level security: theirs only).
GRANT INSERT ON consent TO untraded_api;
GRANT INSERT, UPDATE (config, secret, enabled, last_error) ON ingest_source TO untraded_api;
