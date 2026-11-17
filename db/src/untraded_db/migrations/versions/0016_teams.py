# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Team workspaces: permissions checked in the database, invitation links, and the coaching
rows (sessions, advice, aggregates) closed to the workspaces that follow a player (ADR 0012).

Revision ID: 0016
Revises: 0015
"""

from __future__ import annotations

from pathlib import Path

from untraded_db.migrations.script import run_script

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

SQL = Path(__file__).with_name("0016_teams.sql")

# Teams go first: the downgrade cannot keep a team without the columns and functions it needs.
DOWNGRADE = """
SET LOCAL lock_timeout = '5s';
DELETE FROM workspace WHERE kind = 'team';
DELETE FROM job WHERE kind = 'refresh_team_access';

DROP FUNCTION
    has_permission(uuid, text), role_within(text[], text[]), my_permissions(uuid),
    team_caller(uuid), queue_team_access(bigint), follow_member(uuid, uuid),
    create_team(text, text, bigint), rename_team(uuid, text), delete_team(uuid),
    owners_besides(uuid, uuid), set_member_role(uuid, uuid, uuid), remove_member(uuid, uuid),
    transfer_team_ownership(uuid, uuid),
    create_team_invitation(uuid, uuid, bytea, uuid, integer),
    revoke_team_invitation(uuid, uuid), team_invitation_preview(bytea),
    accept_team_invitation(bytea, text), set_roster_member(uuid, bigint, roster_role),
    remove_roster_member(uuid, bigint), set_my_share_solo(uuid, boolean),
    queue_my_team_access(), open_auth_session(bigint, bytea, interval, bytea, text);

CREATE OR REPLACE FUNCTION request_erasure(steam bigint) RETURNS void
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
DROP FUNCTION team_refuse(text);

CREATE FUNCTION open_auth_session(steam bigint, token bytea, ttl interval)
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
REVOKE ALL ON FUNCTION open_auth_session(bigint, bytea, interval) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION open_auth_session(bigint, bytea, interval) TO untraded_api;

DROP POLICY own ON advice;
CREATE POLICY member ON advice USING (is_member(workspace_id));
DROP POLICY own ON metric_aggregate;
CREATE POLICY followed ON metric_aggregate USING (followed_player(steam_id));
DROP POLICY own ON play_session;
CREATE POLICY visible ON play_session USING (own_player(steam_id) OR followed_player(steam_id));

DROP TABLE team_invitation;
DROP INDEX workspace_player_steam, roster_member_steam, roster_member_current,
    roster_one_per_workspace;
ALTER TABLE membership DROP CONSTRAINT membership_role_in_workspace;
ALTER TABLE workspace_role DROP CONSTRAINT workspace_role_in_workspace;
ALTER TABLE workspace DROP CONSTRAINT workspace_team_slug,
    DROP CONSTRAINT workspace_personal_has_user,
    DROP CONSTRAINT workspace_created_by_fkey;
ALTER TABLE workspace ADD CONSTRAINT workspace_created_by_fkey
    FOREIGN KEY (created_by) REFERENCES app_user (id);
ALTER TABLE workspace ALTER COLUMN created_by SET NOT NULL;
"""


def upgrade() -> None:
    run_script(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    run_script(DOWNGRADE)
