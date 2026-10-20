-- SPDX-FileCopyrightText: 2026 The Untraded Authors
-- SPDX-License-Identifier: AGPL-3.0-only
--
-- Phase 2, step 2 (API and web): match end times, sign-in sessions, play sessions and their
-- report, and the API role that row-level security applies to.

-- When the match ended. Play sessions are cut on the time between the end of a match and the
-- start of the next (more than one hour: a new session). The collector knows it from the Game
-- Coordinator; the worker can also derive it from the demo (start + ticks / tickrate).
ALTER TABLE match ADD COLUMN ended_at timestamptz;

-- ===========================================================================================
-- The API role
-- ===========================================================================================
-- The API connects as the services' user and, in each transaction, runs
--   SET LOCAL ROLE untraded_api; SET LOCAL app.user_id = '<uuid>';
-- untraded_api does not own the tables and has no BYPASSRLS: every policy applies to it.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'untraded_api') THEN
        CREATE ROLE untraded_api NOLOGIN;
    END IF;
END;
$$;
GRANT untraded_api TO CURRENT_USER;
GRANT USAGE ON SCHEMA public TO untraded_api;

-- Views run with their owner's rights by default, which bypasses row-level security: the wide
-- view of the metrics must run with the caller's.
ALTER VIEW metric_wide_current SET (security_invoker = true);

-- ===========================================================================================
-- Sign-in sessions (Steam OpenID)
-- ===========================================================================================
-- The cookie carries a random token; only its sha256 is stored, so a copy of the database does
-- not hold usable sessions. The API reaches this table only through the functions below.

CREATE TABLE auth_session (
    token_hash   bytea PRIMARY KEY CHECK (length(token_hash) = 32),
    user_id      uuid NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    created_at   timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    expires_at   timestamptz NOT NULL
);
CREATE INDEX auth_session_user ON auth_session (user_id);
ALTER TABLE auth_session ENABLE ROW LEVEL SECURITY;  -- no policy: no direct access

-- Opens a session for the Steam account that signed in, if it was invited (it has a user):
-- returns the user, or null. Signing in is by invitation during the beta.
CREATE FUNCTION open_auth_session(steam bigint, token bytea, ttl interval) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
    found uuid;
BEGIN
    SELECT id INTO found FROM app_user WHERE steam_id = steam AND deleted_at IS NULL;
    IF found IS NOT NULL THEN
        INSERT INTO auth_session (token_hash, user_id, expires_at)
        VALUES (token, found, now() + ttl);
    END IF;
    RETURN found;
END;
$$;

-- The user of a live session (null if unknown or expired), and when it was last seen.
CREATE FUNCTION auth_session_user(token bytea) RETURNS uuid
LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    UPDATE auth_session s SET last_seen_at = now()
    FROM app_user u
    WHERE s.token_hash = token AND s.expires_at > now()
      AND u.id = s.user_id AND u.deleted_at IS NULL
    RETURNING s.user_id
$$;

CREATE FUNCTION close_auth_session(token bytea) RETURNS void
LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    DELETE FROM auth_session WHERE token_hash = token OR expires_at <= now()
$$;

REVOKE ALL ON FUNCTION open_auth_session(bigint, bytea, interval) FROM PUBLIC;
REVOKE ALL ON FUNCTION auth_session_user(bytea) FROM PUBLIC;
REVOKE ALL ON FUNCTION close_auth_session(bytea) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION open_auth_session(bigint, bytea, interval) TO untraded_api;
GRANT EXECUTE ON FUNCTION auth_session_user(bytea) TO untraded_api;
GRANT EXECUTE ON FUNCTION close_auth_session(bytea) TO untraded_api;

-- ===========================================================================================
-- Play sessions and their report (computed by the worker, read by the API)
-- ===========================================================================================

-- A player's matches with at most one hour between the end of one and the start of the next.
-- The report compares the session with the player's own 30 days before it (untraded.reference).
CREATE TABLE play_session (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    steam_id          bigint NOT NULL REFERENCES player (steam_id),
    started_at        timestamptz NOT NULL,   -- start of the first match
    ended_at          timestamptz NOT NULL,   -- end of the last match
    matches           smallint NOT NULL,
    rounds            integer NOT NULL,
    reference_from    date NOT NULL,          -- inclusive
    reference_to      date NOT NULL,          -- inclusive: the day before the session
    reference_matches integer NOT NULL,
    reference_rounds  integer NOT NULL,
    enough            boolean NOT NULL,       -- the reference is shown (minimum matches and rounds)
    params            jsonb NOT NULL,         -- window_days, min_matches, min_rounds
    computed_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (steam_id, started_at)
);
CREATE INDEX play_session_recent ON play_session (steam_id, started_at DESC);

CREATE TABLE play_session_match (
    session_id uuid NOT NULL REFERENCES play_session (id) ON DELETE CASCADE,
    match_id   uuid NOT NULL REFERENCES match (id) ON DELETE CASCADE,
    PRIMARY KEY (session_id, match_id)
);
CREATE INDEX play_session_match_match ON play_session_match (match_id);

-- One row per value metric. Totals (kills, damage...) are compared per round (`basis`).
CREATE TABLE play_session_metric (
    session_id uuid NOT NULL REFERENCES play_session (id) ON DELETE CASCADE,
    metric_id  text NOT NULL,
    version    text NOT NULL,
    basis      text NOT NULL CHECK (basis IN ('value', 'per_round')),
    session    double precision,
    reference  double precision,              -- null when the reference is not enough
    delta      double precision,
    PRIMARY KEY (session_id, metric_id, version),
    FOREIGN KEY (metric_id, version) REFERENCES metric_definition (metric_id, version)
);

-- A user's own player.
CREATE FUNCTION own_player(p bigint) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    SELECT EXISTS (
        SELECT 1 FROM app_user WHERE id = current_app_user() AND steam_id = p
    )
$$;

-- A session is visible to its player, and to the workspaces that follow them.
ALTER TABLE play_session ENABLE ROW LEVEL SECURITY;
CREATE POLICY visible ON play_session USING (own_player(steam_id) OR followed_player(steam_id));
ALTER TABLE play_session_match ENABLE ROW LEVEL SECURITY;
CREATE POLICY visible ON play_session_match
    USING (EXISTS (SELECT 1 FROM play_session s WHERE s.id = session_id));
ALTER TABLE play_session_metric ENABLE ROW LEVEL SECURITY;
CREATE POLICY visible ON play_session_metric
    USING (EXISTS (SELECT 1 FROM play_session s WHERE s.id = session_id));

-- ===========================================================================================
-- What the API may read (row-level security still filters the rows)
-- ===========================================================================================
GRANT SELECT ON ALL TABLES IN SCHEMA public TO untraded_api;
REVOKE ALL ON auth_session, ingest_source, job FROM untraded_api;
