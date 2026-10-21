-- SPDX-FileCopyrightText: 2026 The Untraded Authors
-- SPDX-License-Identifier: AGPL-3.0-only
--
-- Erasing a player: asked by the player (their right to erasure) or by an admin. The account
-- is marked deleted at once, so they can no longer sign in and the collector stops following
-- them; the worker's `erase_player` job then deletes their data (untraded_worker.erase).

CREATE FUNCTION request_erasure(steam bigint) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
    found uuid;
BEGIN
    SELECT id INTO found FROM app_user WHERE steam_id = steam;
    IF found IS NOT NULL THEN
        UPDATE app_user SET deleted_at = coalesce(deleted_at, now()) WHERE id = found;
        UPDATE ingest_source SET enabled = false WHERE user_id = found;
        DELETE FROM auth_session WHERE user_id = found;
    END IF;
    DELETE FROM invitation WHERE steam_id = steam AND accepted_at IS NULL;
    INSERT INTO job (kind, payload, max_attempts)
    VALUES ('erase_player', jsonb_build_object('steam_id', steam::text), 10);
END;
$$;
REVOKE ALL ON FUNCTION request_erasure(bigint) FROM PUBLIC;

-- The signed-in player erases themselves.
CREATE FUNCTION request_my_erasure() RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
    steam bigint;
BEGIN
    SELECT steam_id INTO steam FROM app_user
    WHERE id = current_app_user() AND deleted_at IS NULL;
    IF steam IS NULL THEN
        RAISE EXCEPTION 'no signed-in user';
    END IF;
    PERFORM request_erasure(steam);
END;
$$;
REVOKE ALL ON FUNCTION request_my_erasure() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION request_my_erasure() TO untraded_api;
