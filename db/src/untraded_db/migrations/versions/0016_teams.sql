-- SPDX-FileCopyrightText: 2026 The Untraded Authors
-- SPDX-License-Identifier: AGPL-3.0-only
--
-- Team workspaces (ADR 0012): an admin creates a team with its owner, members join through an
-- invitation link, and the team's roster and its players' sharing choices decide which matches
-- it sees (`workspace_match`, kept by the worker's `refresh_team_access` job).
--
-- Before any team exists, three things the personal space relied on are closed:
-- - a workspace that follows a player no longer reads their play sessions, advice or aggregates:
--   those are the player's own (`own_player`);
-- - every write goes through a SECURITY DEFINER function below that checks the caller's
--   permission in the database (`has_permission`): the API role still writes no table directly,
--   so a bug in a route cannot make a viewer an owner;
-- - erasing an owner is refused before the account is closed (`owner_must_hand_over`).
--
-- Refusals are raised with SQLSTATE 'UT001' and a stable code as the message (`forbidden`,
-- `role_too_high`, `last_owner`...), which the API turns into its HTTP errors. A raise rolls the
-- whole transaction back: a refused call leaves nothing behind.

SET LOCAL lock_timeout = '5s';

-- ===========================================================================================
-- Workspaces, roles and rosters
-- ===========================================================================================

-- A team has no creator: an admin creates it for its owner, and the ownership is the owner
-- role (`*`), so the admin can still be erased. A personal workspace keeps its user.
ALTER TABLE workspace ALTER COLUMN created_by DROP NOT NULL;
ALTER TABLE workspace DROP CONSTRAINT workspace_created_by_fkey;
ALTER TABLE workspace ADD CONSTRAINT workspace_created_by_fkey
    FOREIGN KEY (created_by) REFERENCES app_user (id) ON DELETE SET NULL;
ALTER TABLE workspace ADD CONSTRAINT workspace_personal_has_user
    CHECK (kind = 'team' OR created_by IS NOT NULL);
-- A team's slug is lower case, and never of the personal form `u-<steam id>`.
ALTER TABLE workspace ADD CONSTRAINT workspace_team_slug
    CHECK (kind = 'personal' OR (slug::text ~ '^[a-z0-9-]{3,32}$' AND slug::text !~ '^u-[0-9]+$'));

-- A member's role belongs to the member's workspace.
ALTER TABLE workspace_role ADD CONSTRAINT workspace_role_in_workspace UNIQUE (id, workspace_id);
ALTER TABLE membership ADD CONSTRAINT membership_role_in_workspace
    FOREIGN KEY (role_id, workspace_id) REFERENCES workspace_role (id, workspace_id);

-- One roster per team during the beta; a player is on it once at a time (the closed rows are
-- the history: who was on it, and when).
CREATE UNIQUE INDEX roster_one_per_workspace ON roster (workspace_id);
CREATE UNIQUE INDEX roster_member_current ON roster_member (roster_id, steam_id)
    WHERE valid_to IS NULL;
CREATE INDEX roster_member_steam ON roster_member (steam_id);
CREATE INDEX workspace_player_steam ON workspace_player (steam_id);

-- ===========================================================================================
-- Invitation links
-- ===========================================================================================
-- The link carries a random token; only its sha256 is stored, as for sign-in sessions. A link
-- lasts 7 days and lets `max_uses` people join (counted under the row's lock), with the role it
-- names, never the owner's. Opening it does nothing: joining is `accept_team_invitation`.
-- It also lets a new Steam account into the beta (`open_auth_session`): `signups` counts those,
-- so a link opens at most `max_uses` accounts, whether they join or not.

CREATE TABLE team_invitation (
    id           uuid PRIMARY KEY,
    workspace_id uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    token_hash   bytea NOT NULL UNIQUE CHECK (length(token_hash) = 32),
    role_id      uuid NOT NULL,
    max_uses     smallint NOT NULL CHECK (max_uses BETWEEN 1 AND 20),
    uses         smallint NOT NULL DEFAULT 0 CHECK (uses BETWEEN 0 AND max_uses),
    signups      smallint NOT NULL DEFAULT 0 CHECK (signups BETWEEN 0 AND max_uses),
    created_by   uuid REFERENCES app_user (id) ON DELETE SET NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    expires_at   timestamptz NOT NULL,
    revoked_at   timestamptz,
    FOREIGN KEY (role_id, workspace_id) REFERENCES workspace_role (id, workspace_id)
        ON DELETE CASCADE
);
CREATE INDEX team_invitation_workspace ON team_invitation (workspace_id);

-- ===========================================================================================
-- What a workspace that follows a player no longer reads
-- ===========================================================================================
-- Sessions, advice and aggregates are the player's coaching: a team sees matches, never these
-- (cadrage § 5.2). The session's matches and metrics follow `play_session` through their
-- policies (migration 0002).

DROP POLICY visible ON play_session;
CREATE POLICY own ON play_session USING (own_player(steam_id));
DROP POLICY followed ON metric_aggregate;
CREATE POLICY own ON metric_aggregate USING (own_player(steam_id));
DROP POLICY member ON advice;
CREATE POLICY own ON advice USING (is_member(workspace_id) AND own_player(steam_id));

-- ===========================================================================================
-- Permissions
-- ===========================================================================================

-- Whether the signed-in user's role in the workspace grants `permission` (`*` grants all).
CREATE FUNCTION has_permission(w uuid, permission text) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    SELECT EXISTS (
        SELECT 1 FROM membership m
        JOIN workspace_role r ON r.id = m.role_id
        WHERE m.workspace_id = w AND m.user_id = current_app_user()
          AND r.permissions && ARRAY['*', permission]
    )
$$;

-- Whether a role with `candidate` permissions is no stronger than one with `mine`.
CREATE FUNCTION role_within(candidate text[], mine text[]) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path = pg_catalog AS $$
    SELECT '*' = ANY (mine) OR (NOT ('*' = ANY (candidate)) AND candidate <@ mine)
$$;

-- The permissions of the signed-in user in the workspace (null when not a member).
CREATE FUNCTION my_permissions(w uuid) RETURNS text[]
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    SELECT r.permissions FROM membership m JOIN workspace_role r ON r.id = m.role_id
    WHERE m.workspace_id = w AND m.user_id = current_app_user()
$$;

CREATE FUNCTION team_refuse(code text) RETURNS void
LANGUAGE plpgsql VOLATILE SET search_path = pg_catalog AS $$
BEGIN
    RAISE EXCEPTION USING ERRCODE = 'UT001', MESSAGE = code;
END;
$$;

-- The signed-in user, a member of the team `w` (raises otherwise), with the team's row locked
-- (`FOR NO KEY UPDATE`): changes to one team's members happen one at a time, so two of them
-- cannot both remove "the other" owner. The lock does not block a membership's foreign key.
CREATE FUNCTION team_caller(w uuid) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
    me uuid := current_app_user();
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no signed-in user';
    END IF;
    PERFORM 1 FROM workspace WHERE id = w AND kind = 'team' FOR NO KEY UPDATE;
    IF NOT FOUND OR NOT is_member(w) THEN
        PERFORM team_refuse('team_not_found');
    END IF;
    RETURN me;
END;
$$;

-- Queues the recomputation of who sees the player's matches (`refresh_team_access`), once.
CREATE FUNCTION queue_team_access(steam bigint) RETURNS void
LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    INSERT INTO job (kind, payload, max_attempts)
    SELECT 'refresh_team_access', jsonb_build_object('steam_id', steam::text), 5
    WHERE NOT EXISTS (
        SELECT 1 FROM job
        WHERE kind = 'refresh_team_access' AND status = 'queued'
          AND payload->>'steam_id' = steam::text
    )
$$;

-- A member is a followed player of the team (`workspace_player`, where their sharing choice
-- lives); a registered user may not be a `player` yet if none of their matches was parsed.
CREATE FUNCTION follow_member(w uuid, member uuid) RETURNS bigint
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
    steam bigint;
    name text;
BEGIN
    SELECT steam_id, display_name INTO steam, name FROM app_user WHERE id = member;
    INSERT INTO player (steam_id, last_name) VALUES (steam, name) ON CONFLICT DO NOTHING;
    INSERT INTO workspace_player (workspace_id, steam_id) VALUES (w, steam) ON CONFLICT DO NOTHING;
    RETURN steam;
END;
$$;

-- ===========================================================================================
-- Teams (the admin creates them; the API's admin routes run as the owner of these functions)
-- ===========================================================================================

CREATE FUNCTION create_team(team_name text, team_slug text, owner_steam bigint) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
    owner_user uuid;
    space uuid;
    owner_role uuid;
BEGIN
    IF team_slug IS NULL OR team_slug !~ '^[a-z0-9-]{3,32}$' OR team_slug ~ '^u-[0-9]+$' THEN
        PERFORM team_refuse('slug_invalid');
    END IF;
    SELECT id INTO owner_user FROM app_user WHERE steam_id = owner_steam AND deleted_at IS NULL;
    IF owner_user IS NULL THEN
        PERFORM team_refuse('owner_unknown');
    END IF;
    BEGIN
        INSERT INTO workspace (kind, name, slug) VALUES ('team', team_name, team_slug)
        RETURNING id INTO space;
    EXCEPTION WHEN unique_violation THEN
        PERFORM team_refuse('slug_taken');
    END;
    INSERT INTO workspace_role (workspace_id, name, permissions)
    VALUES (space, 'owner', ARRAY['*'])
    RETURNING id INTO owner_role;
    INSERT INTO workspace_role (workspace_id, name, permissions) VALUES
        (space, 'coach', ARRAY['matches.read', 'matches.upload', 'review.comment',
                               'review.manage', 'roster.edit', 'members.manage']),
        (space, 'player', ARRAY['matches.read', 'matches.upload', 'review.comment']),
        (space, 'viewer', ARRAY['matches.read']);
    INSERT INTO roster (workspace_id, name) VALUES (space, team_name);
    INSERT INTO membership (workspace_id, user_id, role_id) VALUES (space, owner_user, owner_role);
    PERFORM follow_member(space, owner_user);
    RETURN space;
END;
$$;

CREATE FUNCTION rename_team(w uuid, team_name text) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
BEGIN
    PERFORM team_caller(w);
    IF NOT has_permission(w, 'settings.edit') THEN
        PERFORM team_refuse('forbidden');
    END IF;
    UPDATE workspace SET name = team_name WHERE id = w;
END;
$$;

-- Deletes the team, its roles, members, roster, invitations and access rows (cascade). The
-- matches stay: they are their players' matches.
CREATE FUNCTION delete_team(w uuid) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
BEGIN
    PERFORM team_caller(w);
    IF NOT has_permission(w, 'team.delete') THEN
        PERFORM team_refuse('forbidden');
    END IF;
    DELETE FROM workspace WHERE id = w AND kind = 'team';
END;
$$;

-- ===========================================================================================
-- Members
-- ===========================================================================================
-- No escalation: whoever has `members.manage` acts only on members whose role is no stronger
-- than theirs, and gives only roles no stronger than theirs, never one with `*` (ownership
-- moves by `transfer_team_ownership` only). The last owner can be neither removed nor demoted.

CREATE FUNCTION owners_besides(w uuid, member uuid) RETURNS bigint
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    SELECT count(*) FROM membership m JOIN workspace_role r ON r.id = m.role_id
    WHERE m.workspace_id = w AND m.user_id <> member AND '*' = ANY (r.permissions)
$$;

CREATE FUNCTION set_member_role(w uuid, member uuid, new_role uuid) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
    me uuid := team_caller(w);
    mine text[] := my_permissions(w);
    theirs text[];
    wanted text[];
BEGIN
    IF NOT has_permission(w, 'members.manage') THEN
        PERFORM team_refuse('forbidden');
    END IF;
    SELECT r.permissions INTO theirs FROM membership m JOIN workspace_role r ON r.id = m.role_id
    WHERE m.workspace_id = w AND m.user_id = member;
    IF theirs IS NULL THEN
        PERFORM team_refuse('not_a_member');
    END IF;
    IF member <> me AND NOT role_within(theirs, mine) THEN
        PERFORM team_refuse('forbidden');
    END IF;
    SELECT permissions INTO wanted FROM workspace_role WHERE id = new_role AND workspace_id = w;
    IF wanted IS NULL OR '*' = ANY (wanted) OR NOT role_within(wanted, mine) THEN
        PERFORM team_refuse('role_too_high');
    END IF;
    IF '*' = ANY (theirs) AND owners_besides(w, member) = 0 THEN
        PERFORM team_refuse('last_owner');
    END IF;
    UPDATE membership SET role_id = new_role WHERE workspace_id = w AND user_id = member;
END;
$$;

-- Removes a member (or the caller leaves): they leave the roster (an end date: the matches
-- played together before stay the team's) and stop sharing their solo matches with it.
CREATE FUNCTION remove_member(w uuid, member uuid) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
    me uuid := team_caller(w);
    theirs text[];
    steam bigint;
BEGIN
    SELECT r.permissions INTO theirs FROM membership m JOIN workspace_role r ON r.id = m.role_id
    WHERE m.workspace_id = w AND m.user_id = member;
    IF member <> me THEN
        IF NOT has_permission(w, 'members.manage') THEN
            PERFORM team_refuse('forbidden');
        END IF;
        IF theirs IS NULL THEN
            PERFORM team_refuse('not_a_member');
        END IF;
        IF NOT role_within(theirs, my_permissions(w)) THEN
            PERFORM team_refuse('forbidden');
        END IF;
    END IF;
    IF '*' = ANY (theirs) AND owners_besides(w, member) = 0 THEN
        PERFORM team_refuse('last_owner');
    END IF;
    SELECT steam_id INTO steam FROM app_user WHERE id = member;
    DELETE FROM membership WHERE workspace_id = w AND user_id = member;
    DELETE FROM workspace_player WHERE workspace_id = w AND steam_id = steam;
    UPDATE roster_member SET valid_to = current_date
    WHERE roster_id IN (SELECT id FROM roster WHERE workspace_id = w)
      AND steam_id = steam AND valid_to IS NULL;
    PERFORM queue_team_access(steam);
END;
$$;

-- The owner hands the team over to another member: the two swap roles, so nobody gains a role
-- they were not given, and the former owner may then be erased.
CREATE FUNCTION transfer_team_ownership(w uuid, member uuid) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
    me uuid := team_caller(w);
    my_role uuid;
    their_role uuid;
BEGIN
    IF NOT ('*' = ANY (my_permissions(w))) THEN
        PERFORM team_refuse('forbidden');
    END IF;
    -- Locked against the member's erasure request (request_erasure locks it too).
    SELECT m.role_id INTO their_role FROM membership m
    JOIN app_user u ON u.id = m.user_id AND u.deleted_at IS NULL
    WHERE m.workspace_id = w AND m.user_id = member
    FOR SHARE OF u;
    IF their_role IS NULL THEN
        PERFORM team_refuse('not_a_member');
    END IF;
    IF member = me THEN
        RETURN;
    END IF;
    SELECT role_id INTO my_role FROM membership WHERE workspace_id = w AND user_id = me;
    UPDATE membership SET role_id = their_role WHERE workspace_id = w AND user_id = me;
    UPDATE membership SET role_id = my_role WHERE workspace_id = w AND user_id = member;
END;
$$;

-- ===========================================================================================
-- Invitation links
-- ===========================================================================================

CREATE FUNCTION create_team_invitation(
    w uuid, invitation_id uuid, digest bytea, role_wanted uuid, uses_allowed integer
) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
    me uuid := team_caller(w);
    wanted text[];
BEGIN
    IF NOT has_permission(w, 'members.manage') THEN
        PERFORM team_refuse('forbidden');
    END IF;
    SELECT permissions INTO wanted FROM workspace_role WHERE id = role_wanted AND workspace_id = w;
    IF wanted IS NULL OR '*' = ANY (wanted) OR NOT role_within(wanted, my_permissions(w)) THEN
        PERFORM team_refuse('role_too_high');
    END IF;
    IF uses_allowed IS NULL OR uses_allowed NOT BETWEEN 1 AND 20 THEN
        PERFORM team_refuse('max_uses_invalid');
    END IF;
    INSERT INTO team_invitation (id, workspace_id, token_hash, role_id, max_uses, created_by,
                                 expires_at)
    VALUES (invitation_id, w, digest, role_wanted, uses_allowed, me, now() + interval '7 days');
END;
$$;

CREATE FUNCTION revoke_team_invitation(w uuid, invitation uuid) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
BEGIN
    PERFORM team_caller(w);
    IF NOT has_permission(w, 'members.manage') THEN
        PERFORM team_refuse('forbidden');
    END IF;
    UPDATE team_invitation SET revoked_at = now()
    WHERE id = invitation AND workspace_id = w AND revoked_at IS NULL;
END;
$$;

-- What an invitation link shows before signing in: the team's name, the role and the end.
-- Nothing for a link that is unknown, expired, used up or revoked. Reads only.
CREATE FUNCTION team_invitation_preview(token bytea)
RETURNS TABLE (team_name text, role text, expires_at timestamptz)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    SELECT w.name, r.name, i.expires_at
    FROM team_invitation i
    JOIN workspace w ON w.id = i.workspace_id
    JOIN workspace_role r ON r.id = i.role_id
    WHERE i.token_hash = token AND i.revoked_at IS NULL AND i.expires_at > now()
      AND i.uses < i.max_uses
$$;

-- The signed-in user joins the team of a valid link, with its role; returns the team's slug.
-- `consent_version` is the current consent text: the user must have agreed to it first.
CREATE FUNCTION accept_team_invitation(token bytea, consent_version text) RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
    me uuid := current_app_user();
    w uuid;
    invitation team_invitation;
    found_slug text;
BEGIN
    IF me IS NULL OR NOT EXISTS (SELECT 1 FROM app_user WHERE id = me AND deleted_at IS NULL) THEN
        RAISE EXCEPTION 'no signed-in user';
    END IF;
    -- The team first, then the link: the order every function that touches both follows.
    SELECT workspace_id INTO w FROM team_invitation WHERE token_hash = token;
    IF w IS NOT NULL THEN
        PERFORM 1 FROM workspace WHERE id = w FOR NO KEY UPDATE;
    END IF;
    SELECT * INTO invitation FROM team_invitation WHERE token_hash = token FOR UPDATE;
    IF invitation.id IS NULL OR invitation.revoked_at IS NOT NULL
       OR invitation.expires_at <= now() OR invitation.uses >= invitation.max_uses THEN
        PERFORM team_refuse('invitation_invalid');
    END IF;
    IF EXISTS (SELECT 1 FROM membership WHERE workspace_id = w AND user_id = me) THEN
        PERFORM team_refuse('already_member');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM consent_current c
        WHERE c.user_id = me AND c.analysis AND c.text_version = consent_version
    ) THEN
        PERFORM team_refuse('consent_required');
    END IF;
    INSERT INTO membership (workspace_id, user_id, role_id) VALUES (w, me, invitation.role_id);
    PERFORM follow_member(w, me);
    UPDATE team_invitation SET uses = uses + 1 WHERE id = invitation.id;
    SELECT slug::text INTO found_slug FROM workspace WHERE id = w;
    RETURN found_slug;
END;
$$;

-- ===========================================================================================
-- Roster and sharing
-- ===========================================================================================

-- Puts a member on the roster as a starter or a stand-in (or changes which).
CREATE FUNCTION set_roster_member(w uuid, steam bigint, as_role roster_role) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
    member uuid;
    team_roster uuid;
BEGIN
    PERFORM team_caller(w);
    IF NOT has_permission(w, 'roster.edit') THEN
        PERFORM team_refuse('forbidden');
    END IF;
    SELECT m.user_id INTO member FROM membership m
    JOIN app_user u ON u.id = m.user_id AND u.deleted_at IS NULL
    WHERE m.workspace_id = w AND u.steam_id = steam;
    IF member IS NULL THEN
        PERFORM team_refuse('not_a_member');
    END IF;
    PERFORM follow_member(w, member);
    SELECT id INTO team_roster FROM roster WHERE workspace_id = w;
    UPDATE roster_member SET role = as_role
    WHERE roster_id = team_roster AND steam_id = steam AND valid_to IS NULL;
    IF FOUND THEN
        RETURN;  -- already on it: the role changes, the matches it opens do not
    END IF;
    -- Taken off and put back the same day: the same row opens again.
    UPDATE roster_member SET role = as_role, valid_to = NULL
    WHERE roster_id = team_roster AND steam_id = steam AND valid_from = current_date;
    IF NOT FOUND THEN
        INSERT INTO roster_member (roster_id, steam_id, role) VALUES (team_roster, steam, as_role);
    END IF;
    PERFORM queue_team_access(steam);
END;
$$;

-- Takes a player off the roster: an end date, the history stays.
CREATE FUNCTION remove_roster_member(w uuid, steam bigint) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
BEGIN
    PERFORM team_caller(w);
    IF NOT has_permission(w, 'roster.edit') THEN
        PERFORM team_refuse('forbidden');
    END IF;
    UPDATE roster_member SET valid_to = current_date
    WHERE roster_id IN (SELECT id FROM roster WHERE workspace_id = w)
      AND steam_id = steam AND valid_to IS NULL;
    IF FOUND THEN
        PERFORM queue_team_access(steam);
    END IF;
END;
$$;

-- The signed-in member's own choice to share their solo matches with the team: nobody else can
-- make it for them, whatever their role.
CREATE FUNCTION set_my_share_solo(w uuid, share boolean) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
    me uuid := team_caller(w);
    steam bigint := follow_member(w, me);
BEGIN
    UPDATE workspace_player SET share_solo = share
    WHERE workspace_id = w AND steam_id = steam AND share_solo IS DISTINCT FROM share;
    IF FOUND THEN
        PERFORM queue_team_access(steam);
    END IF;
END;
$$;

-- After the signed-in user's consent changed: their teams see their matches again or no more.
CREATE FUNCTION queue_my_team_access() RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
    steam bigint;
BEGIN
    SELECT u.steam_id INTO steam FROM app_user u WHERE u.id = current_app_user();
    IF steam IS NOT NULL AND EXISTS (
        SELECT 1 FROM membership m JOIN workspace w ON w.id = m.workspace_id AND w.kind = 'team'
        WHERE m.user_id = current_app_user()
    ) THEN
        PERFORM queue_team_access(steam);
    END IF;
END;
$$;

-- ===========================================================================================
-- Sign-in with an invitation link, and erasure
-- ===========================================================================================

-- As in 0008, plus: a Steam account that is not invited yet comes in with a valid team link
-- (`team_invite`, the hash of its token), named `persona` (its Steam name, when the API could
-- read it). The link is not used up here (joining is `accept_team_invitation`), but each account
-- it opens counts against its `max_uses` (`signups`).
DROP FUNCTION open_auth_session(bigint, bytea, interval);
CREATE FUNCTION open_auth_session(
    steam bigint, token bytea, ttl interval, team_invite bytea DEFAULT NULL,
    persona text DEFAULT NULL
) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
    found uuid;
    invited text;
    space uuid;
    owner uuid;
BEGIN
    SELECT id INTO found FROM app_user WHERE steam_id = steam AND deleted_at IS NULL;
    IF found IS NULL THEN
        IF EXISTS (SELECT 1 FROM app_user WHERE steam_id = steam) THEN
            RETURN NULL;  -- a deleted user
        END IF;
        SELECT display_name INTO invited FROM invitation
        WHERE steam_id = steam AND accepted_at IS NULL
        FOR UPDATE;
        IF invited IS NULL AND team_invite IS NOT NULL THEN
            UPDATE team_invitation SET signups = signups + 1
            WHERE token_hash = team_invite AND revoked_at IS NULL AND expires_at > now()
              AND uses < max_uses AND signups < max_uses
            RETURNING coalesce(nullif(btrim(left(persona, 64)), ''), 'Player') INTO invited;
        END IF;
        IF invited IS NULL THEN
            RETURN NULL;  -- not invited
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
        UPDATE invitation SET accepted_at = now() WHERE steam_id = steam AND accepted_at IS NULL;
    END IF;
    INSERT INTO auth_session (token_hash, user_id, expires_at)
    VALUES (token, found, now() + ttl);
    RETURN found;
END;
$$;

-- As in 0009, plus: a team's owner must hand it over first. Refused before anything closes, so
-- they can still sign in to do it. The user's row is locked against a hand-over to them.
CREATE OR REPLACE FUNCTION request_erasure(steam bigint) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
    found uuid;
BEGIN
    SELECT id INTO found FROM app_user WHERE steam_id = steam FOR UPDATE;
    IF found IS NOT NULL AND EXISTS (
        SELECT 1 FROM membership m
        JOIN workspace w ON w.id = m.workspace_id AND w.kind = 'team'
        JOIN workspace_role r ON r.id = m.role_id
        WHERE m.user_id = found AND '*' = ANY (r.permissions)
    ) THEN
        PERFORM team_refuse('owner_must_hand_over');
    END IF;
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

-- ===========================================================================================
-- What the API may run and read
-- ===========================================================================================

REVOKE ALL ON FUNCTION
    has_permission(uuid, text), role_within(text[], text[]), my_permissions(uuid),
    team_refuse(text), team_caller(uuid), queue_team_access(bigint), follow_member(uuid, uuid),
    create_team(text, text, bigint), rename_team(uuid, text), delete_team(uuid),
    owners_besides(uuid, uuid), set_member_role(uuid, uuid, uuid), remove_member(uuid, uuid),
    transfer_team_ownership(uuid, uuid),
    create_team_invitation(uuid, uuid, bytea, uuid, integer),
    revoke_team_invitation(uuid, uuid), team_invitation_preview(bytea),
    accept_team_invitation(bytea, text), set_roster_member(uuid, bigint, roster_role),
    remove_roster_member(uuid, bigint), set_my_share_solo(uuid, boolean),
    queue_my_team_access(), open_auth_session(bigint, bytea, interval, bytea, text)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
    has_permission(uuid, text), my_permissions(uuid), rename_team(uuid, text),
    delete_team(uuid), set_member_role(uuid, uuid, uuid), remove_member(uuid, uuid),
    transfer_team_ownership(uuid, uuid),
    create_team_invitation(uuid, uuid, bytea, uuid, integer),
    revoke_team_invitation(uuid, uuid), team_invitation_preview(bytea),
    accept_team_invitation(bytea, text), set_roster_member(uuid, bigint, roster_role),
    remove_roster_member(uuid, bigint), set_my_share_solo(uuid, boolean),
    queue_my_team_access(), open_auth_session(bigint, bytea, interval, bytea, text)
    TO untraded_api;

-- The invitations of a team, to those who manage its members; never the token's hash.
ALTER TABLE team_invitation ENABLE ROW LEVEL SECURITY;
CREATE POLICY manage ON team_invitation USING (has_permission(workspace_id, 'members.manage'));
GRANT SELECT (id, workspace_id, role_id, max_uses, uses, created_at, expires_at, revoked_at)
    ON team_invitation TO untraded_api;
