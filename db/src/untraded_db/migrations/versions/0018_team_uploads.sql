-- SPDX-FileCopyrightText: 2026 The Untraded Authors
-- SPDX-License-Identifier: AGPL-3.0-only
--
-- Demos a team sends for itself (cadrage équipe § 5.3): a member with `matches.upload` sends a
-- scrim or an official FACEIT or ESEA match from the team's space. The match counts for the team
-- alone, never for a player's own account: anyone can edit a demo, and one naming five players
-- must not fill their accounts. So the source belongs to the workspace, not to a user, and
-- `credited()` (the worker's `credit.py`) never counts it for anyone: no sessions, no references,
-- no personal list. The team sees it through its own source (`workspace_match.reason = 'team'`,
-- migration 0017), as soon as the worker admits it: 3 players of its roster on the date of the
-- match, on the same side (`not_enough_roster` otherwise, and the demo goes).
--
-- The limits are those of a player's uploads (migration 0010), counted per team. Refusals before
-- the file is read come back as a code (`team_upload_refusal`); a caller who is not a member
-- gets the team functions' `team_not_found` (SQLSTATE 'UT001', migration 0016).

SET LOCAL lock_timeout = '5s';

-- A source is a user's or a workspace's, never both. A workspace sends uploads only (MatchZy,
-- E5, will add its own kind), one source per kind.
ALTER TABLE ingest_source ALTER COLUMN user_id DROP NOT NULL;
ALTER TABLE ingest_source
    ADD COLUMN workspace_id uuid REFERENCES workspace (id) ON DELETE CASCADE;
ALTER TABLE ingest_source ADD CONSTRAINT ingest_source_one_owner
    CHECK ((user_id IS NULL) <> (workspace_id IS NULL));
ALTER TABLE ingest_source ADD CONSTRAINT ingest_source_workspace_kind
    CHECK (workspace_id IS NULL OR kind = 'upload');
CREATE UNIQUE INDEX ingest_source_workspace ON ingest_source (workspace_id, kind)
    WHERE workspace_id IS NOT NULL;

-- Who sent a team's upload, for the team's history. Not in `match_source`: a scrim two teams sent
-- is one match, and the other team must not learn who sent it. The API role does not read this
-- table; `team_uploads` does. Erasing the sender erases it, and so does deleting the team.
CREATE TABLE upload_sender (
    kind        ingest_kind NOT NULL DEFAULT 'upload' CHECK (kind = 'upload'),
    external_id text NOT NULL,
    user_id     uuid NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    PRIMARY KEY (kind, external_id),
    FOREIGN KEY (kind, external_id) REFERENCES match_source (kind, external_id) ON DELETE CASCADE
);
CREATE INDEX upload_sender_user ON upload_sender (user_id);
ALTER TABLE upload_sender ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON upload_sender FROM untraded_api;

-- `match_source` now says which team brought a match: the API role reads it only for the matches
-- the user sees (it had no policy, and no route reads it).
ALTER TABLE match_source ENABLE ROW LEVEL SECURITY;
CREATE POLICY visible ON match_source USING (visible_match(match_id));

-- Why the signed-in member may not send a demo for the team `w` now: 'forbidden' (no
-- `matches.upload`), 'consent' (they do not consent to the analysis), 'not_enough_roster' (fewer
-- than 3 consenting registered players were ever on the roster: no demo can pass the rule),
-- 'quota' (`per_day` uploads of the team in the last 24 hours), 'busy' (`in_flight` of them still
-- being processed); null when they may. Zero or less lifts a limit. Raises `team_not_found` for
-- someone who is not a member.
CREATE FUNCTION team_upload_refusal(w uuid, per_day integer, in_flight integer) RETURNS text
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    me uuid := current_app_user();
    agreed boolean;
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no signed-in user';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM workspace WHERE id = w AND kind = 'team') OR NOT is_member(w) THEN
        PERFORM team_refuse('team_not_found');
    END IF;
    IF NOT has_permission(w, 'matches.upload') THEN
        RETURN 'forbidden';
    END IF;
    SELECT analysis INTO agreed FROM consent_current WHERE user_id = me;
    IF agreed IS NOT TRUE THEN
        RETURN 'consent';
    END IF;
    IF (
        SELECT count(DISTINCT rm.steam_id) FROM roster r
        JOIN roster_member rm ON rm.roster_id = r.id
        JOIN app_user u ON u.steam_id = rm.steam_id AND u.deleted_at IS NULL
        JOIN consent_current c ON c.user_id = u.id AND c.analysis
        WHERE r.workspace_id = w AND r.active
    ) < 3 THEN
        RETURN 'not_enough_roster';
    END IF;
    IF per_day > 0 AND (
        SELECT count(*) FROM match_source ms
        JOIN ingest_source s ON s.id = ms.source_id
        WHERE s.workspace_id = w AND s.kind = 'upload' AND ms.received_at > now() - interval '1 day'
    ) >= per_day THEN
        RETURN 'quota';
    END IF;
    IF in_flight > 0 AND (
        SELECT count(*) FROM match_source ms
        JOIN ingest_source s ON s.id = ms.source_id
        JOIN match m ON m.id = ms.match_id
        WHERE s.workspace_id = w AND s.kind = 'upload' AND ms.rejected IS NULL
          AND m.status IN ('pending', 'downloading', 'parsing')
    ) >= in_flight THEN
        RETURN 'busy';
    END IF;
    RETURN NULL;
END;
$$;

-- Records a demo the signed-in member sent for the team `w` (`file`: its name in the uploads
-- directory), unless `team_upload_refusal` refuses it, which it returns. The team's row is
-- locked first (`team_caller`, the order of every team function), then its source: two uploads
-- at once cannot both pass the limits.
CREATE FUNCTION add_team_upload(
    w uuid, upload uuid, file text, chosen match_mode, played timestamptz, per_day integer,
    in_flight integer
) RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    me uuid := team_caller(w);
    source uuid;
    refusal text;
BEGIN
    SELECT id INTO source FROM ingest_source WHERE workspace_id = w AND kind = 'upload' FOR UPDATE;
    IF source IS NULL THEN
        INSERT INTO ingest_source (workspace_id, kind) VALUES (w, 'upload') RETURNING id INTO source;
    END IF;
    refusal := team_upload_refusal(w, per_day, in_flight);
    IF refusal IS NOT NULL THEN
        RETURN refusal;
    END IF;
    INSERT INTO match (id, mode, status, played_at) VALUES (upload, chosen, 'pending', played);
    INSERT INTO match_source (match_id, kind, external_id, source_id)
    VALUES (upload, 'upload', upload::text, source);
    INSERT INTO upload_sender (external_id, user_id) VALUES (upload::text, me);
    INSERT INTO job (kind, payload, max_attempts)
    VALUES ('ingest_upload', jsonb_build_object('match_id', upload::text, 'file', file), 3);
    RETURN NULL;
END;
$$;

-- The team's uploads of the last `days` days, newest first, for a member with `matches.read`
-- (nothing otherwise). `sent_by` is the sender's name, null once their account is erased.
CREATE FUNCTION team_uploads(w uuid, days integer)
RETURNS TABLE (
    upload_id uuid, match_id uuid, received_at timestamptz, mode text, status text,
    rejected text, map text, played_at timestamptz, sent_by text
)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
    SELECT ms.external_id::uuid, m.id, ms.received_at, m.mode::text, m.status::text,
           ms.rejected, m.map, m.played_at, u.display_name
    FROM ingest_source s
    JOIN match_source ms ON ms.source_id = s.id AND ms.kind = 'upload'
    JOIN match m ON m.id = ms.match_id
    LEFT JOIN upload_sender us ON us.kind = ms.kind AND us.external_id = ms.external_id
    LEFT JOIN app_user u ON u.id = us.user_id AND u.deleted_at IS NULL
    WHERE s.workspace_id = w AND s.kind = 'upload' AND has_permission(w, 'matches.read')
      AND ms.received_at > now() - make_interval(days => days)
    ORDER BY ms.received_at DESC
$$;

-- As in 0016, plus: the matches the team sent go with it, unless they count for a registered
-- user or another live source brought them too. The rows and files are the worker's to delete
-- (`drop_team_matches`, which checks each match again): the team's source goes with the team
-- here, so nobody sees those matches from now on.
CREATE OR REPLACE FUNCTION delete_team(w uuid) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    sent uuid[];
BEGIN
    PERFORM team_caller(w);
    IF NOT has_permission(w, 'team.delete') THEN
        PERFORM team_refuse('forbidden');
    END IF;
    -- The members' accounts first, in a stable order, as an erasure locks its account first.
    PERFORM 1 FROM app_user u
    WHERE u.id IN (SELECT user_id FROM membership WHERE workspace_id = w)
    ORDER BY u.id
    FOR SHARE;
    SELECT array_agg(DISTINCT ms.match_id ORDER BY ms.match_id) INTO sent
    FROM match_source ms JOIN ingest_source s ON s.id = ms.source_id
    WHERE s.workspace_id = w;
    -- Who sent them goes now: a match that stays (it counts for someone else) keeps no trace of a
    -- team that no longer exists.
    DELETE FROM upload_sender us USING match_source ms, ingest_source s
    WHERE us.kind = ms.kind AND us.external_id = ms.external_id AND ms.source_id = s.id
      AND s.workspace_id = w;
    DELETE FROM workspace WHERE id = w AND kind = 'team';
    IF sent IS NOT NULL THEN
        INSERT INTO job (kind, payload, max_attempts)
        VALUES ('drop_team_matches', jsonb_build_object('match_ids', to_jsonb(sent)), 10);
    END IF;
END;
$$;

REVOKE ALL ON FUNCTION team_upload_refusal(uuid, integer, integer),
    add_team_upload(uuid, uuid, text, match_mode, timestamptz, integer, integer),
    team_uploads(uuid, integer)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION team_upload_refusal(uuid, integer, integer),
    add_team_upload(uuid, uuid, text, match_mode, timestamptz, integer, integer),
    team_uploads(uuid, integer)
    TO untraded_api;
