-- SPDX-FileCopyrightText: 2026 The Untraded Authors
-- SPDX-License-Identifier: AGPL-3.0-only
--
-- Demos a player sends from the site (`POST /uploads`). The API writes the file to the uploads
-- directory, then `add_my_upload` records it: a `match` (pending, with the mode and date the
-- player gave), its `match_source` (kind 'upload', the player's 'upload' ingest_source) and an
-- `ingest_upload` job. The worker checks the file and hands it to `parse`.
--
-- `match_source.rejected` says why an upload was refused after it was received, as a stable
-- code the site translates: 'not_a_demo', 'corrupt', 'too_large', 'unsupported_mode',
-- 'not_a_player'. The match may still be analysed for another source (another player's copy).

ALTER TABLE match_source ADD COLUMN rejected text;

-- Why the signed-in player may not send a demo now: 'consent' (no consent to the analysis),
-- 'quota' (`per_day` uploads in the last 24 hours), 'busy' (`in_flight` uploads still being
-- processed); null when they may. Zero or less lifts a limit.
CREATE FUNCTION my_upload_refusal(per_day integer, in_flight integer) RETURNS text
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
    me uuid := current_app_user();
    agreed boolean;
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no signed-in user';
    END IF;
    SELECT analysis INTO agreed FROM consent_current WHERE user_id = me;
    IF agreed IS NOT TRUE THEN
        RETURN 'consent';
    END IF;
    IF per_day > 0 AND (
        SELECT count(*) FROM match_source ms
        JOIN ingest_source s ON s.id = ms.source_id
        WHERE s.user_id = me AND s.kind = 'upload' AND ms.received_at > now() - interval '1 day'
    ) >= per_day THEN
        RETURN 'quota';
    END IF;
    IF in_flight > 0 AND (
        SELECT count(*) FROM match_source ms
        JOIN ingest_source s ON s.id = ms.source_id
        JOIN match m ON m.id = ms.match_id
        WHERE s.user_id = me AND s.kind = 'upload' AND ms.rejected IS NULL
          AND m.status IN ('pending', 'downloading', 'parsing')
    ) >= in_flight THEN
        RETURN 'busy';
    END IF;
    RETURN NULL;
END;
$$;

-- Records a demo the signed-in player sent (`file`: its name in the uploads directory), unless
-- `my_upload_refusal` refuses it, which it returns. The player's 'upload' source is locked, so
-- two uploads at once cannot both pass the limits.
CREATE FUNCTION add_my_upload(
    upload uuid, file text, chosen match_mode, played timestamptz, per_day integer,
    in_flight integer
) RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
    me uuid := current_app_user();
    source uuid;
    refusal text;
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no signed-in user';
    END IF;
    SELECT id INTO source FROM ingest_source WHERE user_id = me AND kind = 'upload' FOR UPDATE;
    IF source IS NULL THEN
        INSERT INTO ingest_source (user_id, kind) VALUES (me, 'upload') RETURNING id INTO source;
    END IF;
    refusal := my_upload_refusal(per_day, in_flight);
    IF refusal IS NOT NULL THEN
        RETURN refusal;
    END IF;
    INSERT INTO match (id, mode, status, played_at) VALUES (upload, chosen, 'pending', played);
    INSERT INTO match_source (match_id, kind, external_id, source_id)
    VALUES (upload, 'upload', upload::text, source);
    INSERT INTO job (kind, payload, max_attempts)
    VALUES ('ingest_upload', jsonb_build_object('match_id', upload::text, 'file', file), 3);
    RETURN NULL;
END;
$$;

-- The signed-in player's uploads of the last `days` days, newest first. `match_id` is the
-- match the demo became: another one than the upload's when the demo was already known.
CREATE FUNCTION my_uploads(days integer)
RETURNS TABLE (
    upload_id uuid, match_id uuid, received_at timestamptz, mode text, status text,
    rejected text, map text, played_at timestamptz
)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    SELECT ms.external_id::uuid, m.id, ms.received_at, m.mode::text, m.status::text,
           ms.rejected, m.map, m.played_at
    FROM match_source ms
    JOIN ingest_source s ON s.id = ms.source_id
    JOIN match m ON m.id = ms.match_id
    WHERE s.user_id = current_app_user() AND s.kind = 'upload' AND ms.kind = 'upload'
      AND ms.received_at > now() - make_interval(days => days)
    ORDER BY ms.received_at DESC
$$;

REVOKE ALL ON FUNCTION my_upload_refusal(integer, integer),
    add_my_upload(uuid, text, match_mode, timestamptz, integer, integer), my_uploads(integer)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION my_upload_refusal(integer, integer),
    add_my_upload(uuid, text, match_mode, timestamptz, integer, integer), my_uploads(integer)
    TO untraded_api;
