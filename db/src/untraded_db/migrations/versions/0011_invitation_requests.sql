-- SPDX-FileCopyrightText: 2026 The Untraded Authors
-- SPDX-License-Identifier: AGPL-3.0-only
--
-- Invitation requests: a Steam account that signs in without being invited may ask for an
-- invitation. Steam has proved the account, so a request is one row per account; the admin
-- invites it (the request goes) or dismisses it.

CREATE TABLE invitation_request (
    steam_id     bigint PRIMARY KEY,
    persona_name text,                    -- the Steam name when it could be read, to help the admin
    requested_at timestamptz NOT NULL DEFAULT now()
);

-- Records a request for a signed-out visitor whose Steam account the API has just checked. Does
-- nothing for an account that is already a user or invited, or that already asked. Returns
-- whether a request was recorded.
CREATE FUNCTION request_invitation(steam bigint, persona text) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM app_user WHERE steam_id = steam AND deleted_at IS NULL)
       OR EXISTS (SELECT 1 FROM invitation WHERE steam_id = steam AND accepted_at IS NULL) THEN
        RETURN false;
    END IF;
    INSERT INTO invitation_request (steam_id, persona_name)
    VALUES (steam, left(persona, 64))
    ON CONFLICT (steam_id) DO NOTHING;
    RETURN FOUND;
END;
$$;

REVOKE ALL ON FUNCTION request_invitation(bigint, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION request_invitation(bigint, text) TO untraded_api;
