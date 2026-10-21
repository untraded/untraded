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

-- The player records their own consent (row-level security: their rows only).
GRANT INSERT ON consent TO untraded_api;

-- Their own source, through these functions only: ingest_source holds the encrypted codes and
-- stays out of the API role's reach (migration 0002), so the API never reads a secret.
CREATE FUNCTION my_source()
RETURNS TABLE (id uuid, enabled boolean, last_success_at timestamptz, last_error text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    SELECT id, enabled, last_success_at, last_error FROM ingest_source
    WHERE user_id = current_app_user() AND kind = 'valve_bot'
    ORDER BY created_at LIMIT 1
$$;

-- Keeps the player's codes: `sealed` is encrypted by the API with `source` as associated data
-- (my_source().id, or a new id for a first source). Re-enables the source, clears its error.
CREATE FUNCTION set_my_source(source uuid, sealed bytea, share_code text) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
BEGIN
    IF current_app_user() IS NULL THEN
        RAISE EXCEPTION 'no signed-in user';
    END IF;
    UPDATE ingest_source
    SET secret = sealed, enabled = true, last_error = NULL,
        config = jsonb_set(config, '{known_share_code}', to_jsonb(share_code))
    WHERE id = source AND user_id = current_app_user() AND kind = 'valve_bot';
    IF NOT FOUND THEN
        INSERT INTO ingest_source (id, user_id, kind, config, secret)
        VALUES (source, current_app_user(), 'valve_bot',
                jsonb_build_object('known_share_code', share_code), sealed);
    END IF;
END;
$$;

-- A withdrawn consent stops following the player.
CREATE FUNCTION pause_my_sources() RETURNS void
LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    UPDATE ingest_source SET enabled = false WHERE user_id = current_app_user()
$$;

REVOKE ALL ON FUNCTION my_source(), set_my_source(uuid, bytea, text), pause_my_sources()
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION my_source(), set_my_source(uuid, bytea, text), pause_my_sources()
    TO untraded_api;
