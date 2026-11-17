-- SPDX-FileCopyrightText: 2026 The Untraded Authors
-- SPDX-License-Identifier: AGPL-3.0-only
--
-- A team's review (cadrage équipe § 5.5): comments on a round (and an optional instant of it),
-- free tags on a round, and ordered playlists of rounds from several matches.
--
-- Every row belongs to a team and a match. A member reads it with `matches.read`, and only for a
-- match the TEAM sees (its own `workspace_match` rows): a scrim between two teams on Untraded is
-- one match, and neither team reads the other's review, even when one user is in both. When the
-- team loses a match (roster changed, sharing withdrawn), its review of it is hidden, not
-- deleted; it comes back with the access.
--
-- Writes go through the SECURITY DEFINER functions below (ADR 0012): `review.comment` writes a
-- comment and edits or deletes one's own; `review.manage` sets tags, keeps the playlists and
-- deletes another member's comment (never edits it). Refusals are raised as in migration 0016
-- (SQLSTATE 'UT001', a stable code as the message).
--
-- A comment keeps its author's name as it was written (refreshed when its author edits it): the
-- name stays readable once the author leaves the team, which hides their account from the other
-- members. Erasing the account (the worker's `erase_player`) clears both the author and the name
-- at once ("former member" on the site); the text is not rewritten. A check refuses an author
-- cleared without the name, so an account cannot go while its name stays on a comment. Tags and
-- playlists keep no author.
--
-- The review refers to a match and a round number, not to the `round` rows, which a reanalysis
-- rewrites: it survives a reanalysis, and goes with its match or its team.

SET LOCAL lock_timeout = '5s';

-- ===========================================================================================
-- Tables
-- ===========================================================================================

CREATE TABLE review_comment (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    match_id     uuid NOT NULL REFERENCES match (id) ON DELETE CASCADE,
    round        smallint NOT NULL CHECK (round BETWEEN 1 AND 99),
    tick         integer CHECK (tick >= 0),
    body         text NOT NULL CHECK (char_length(body) BETWEEN 1 AND 2000),
    author_id    uuid REFERENCES app_user (id) ON DELETE SET NULL,
    author_name  text CHECK (char_length(author_name) BETWEEN 1 AND 64),
    created_at   timestamptz NOT NULL DEFAULT now(),
    edited_at    timestamptz,
    CONSTRAINT review_comment_author CHECK ((author_id IS NULL) = (author_name IS NULL))
);
CREATE INDEX review_comment_round ON review_comment (workspace_id, match_id, round);
CREATE INDEX review_comment_match ON review_comment (match_id);
CREATE INDEX review_comment_by_author ON review_comment (author_id);

CREATE TABLE review_tag (
    workspace_id uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    match_id     uuid NOT NULL REFERENCES match (id) ON DELETE CASCADE,
    round        smallint NOT NULL CHECK (round BETWEEN 1 AND 99),
    label        text NOT NULL CHECK (char_length(label) BETWEEN 1 AND 32),
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX review_tag_unique ON review_tag (workspace_id, match_id, round, lower(label));
CREATE INDEX review_tag_match ON review_tag (match_id);

CREATE TABLE review_playlist (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    name         text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 80),
    description  text NOT NULL DEFAULT '' CHECK (char_length(description) <= 280),
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, workspace_id)
);
CREATE INDEX review_playlist_workspace ON review_playlist (workspace_id);

-- A playlist's rounds carry its team, so that their policy is the comments' own.
CREATE TABLE review_playlist_round (
    playlist_id  uuid NOT NULL,
    workspace_id uuid NOT NULL,
    match_id     uuid NOT NULL REFERENCES match (id) ON DELETE CASCADE,
    round        smallint NOT NULL CHECK (round BETWEEN 1 AND 99),
    seq          integer NOT NULL,
    added_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (playlist_id, match_id, round),
    FOREIGN KEY (playlist_id, workspace_id) REFERENCES review_playlist (id, workspace_id)
        ON DELETE CASCADE
);
CREATE INDEX review_playlist_round_match ON review_playlist_round (match_id);

-- ===========================================================================================
-- Who reads
-- ===========================================================================================

-- Whether the signed-in user may read the team `w`'s review of the match `m`: they may read the
-- team's matches (a member with `matches.read`) and the team itself sees the match.
CREATE FUNCTION review_readable(w uuid, m uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
    SELECT has_permission(w, 'matches.read') AND EXISTS (
        SELECT 1 FROM workspace_match wm WHERE wm.workspace_id = w AND wm.match_id = m
    )
$$;

ALTER TABLE review_comment ENABLE ROW LEVEL SECURITY;
CREATE POLICY team ON review_comment USING (review_readable(workspace_id, match_id));
ALTER TABLE review_tag ENABLE ROW LEVEL SECURITY;
CREATE POLICY team ON review_tag USING (review_readable(workspace_id, match_id));
ALTER TABLE review_playlist ENABLE ROW LEVEL SECURITY;
CREATE POLICY team ON review_playlist USING (has_permission(workspace_id, 'matches.read'));
ALTER TABLE review_playlist_round ENABLE ROW LEVEL SECURITY;
CREATE POLICY team ON review_playlist_round USING (review_readable(workspace_id, match_id));
GRANT SELECT ON review_comment, review_tag, review_playlist, review_playlist_round
    TO untraded_api;

-- ===========================================================================================
-- Helpers
-- ===========================================================================================

-- The signed-in member of the team `w` (`team_caller`: the team's row locked, `team_not_found`
-- otherwise), who reads its matches and holds `permission` ('forbidden' otherwise).
CREATE FUNCTION review_caller(w uuid, permission text) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    me uuid := team_caller(w);
BEGIN
    IF NOT has_permission(w, 'matches.read') OR NOT has_permission(w, permission) THEN
        PERFORM team_refuse('forbidden');
    END IF;
    RETURN me;
END;
$$;

-- Raises unless the team `w` sees the match `m` ('match_not_found') and its round `r` is in the
-- database ('round_not_found': the match is parsed and has that round).
CREATE FUNCTION review_round(w uuid, m uuid, r integer) RETURNS void
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM workspace_match WHERE workspace_id = w AND match_id = m) THEN
        PERFORM team_refuse('match_not_found');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM round WHERE match_id = m AND round.round = r) THEN
        PERFORM team_refuse('round_not_found');
    END IF;
END;
$$;

-- Characters a text may not hold: controls (but tab and line feed), the direction marks,
-- overrides and isolates, which would make a text read differently from what it holds, the line
-- and paragraph separators, and the invisible zero-width space and byte order mark. The joiners
-- (U+200C, U+200D) stay: some scripts and emoji need them.
CREATE FUNCTION review_unsafe(t text) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path = pg_catalog AS $$
    SELECT t ~ '[\x01-\x08\x0b-\x1f\x7f\u061c\u200b\u200e\u200f\u2028\u2029\u202a-\u202e\u2066-\u2069\ufeff]'
$$;

-- A comment's text as stored: line breaks as `\n`, no blank space around it, 1 to 2,000
-- characters ('comment_invalid' otherwise).
CREATE FUNCTION review_body(t text) RETURNS text
LANGUAGE plpgsql IMMUTABLE SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    cleaned text := btrim(replace(replace(t, E'\r\n', E'\n'), E'\r', E'\n'), E' \t\n');
BEGIN
    IF cleaned IS NULL OR char_length(cleaned) NOT BETWEEN 1 AND 2000
       OR review_unsafe(cleaned) THEN
        PERFORM team_refuse('comment_invalid');
    END IF;
    RETURN cleaned;
END;
$$;

-- A one-line text as stored: blank space collapsed to one space and trimmed; `max_length`
-- characters at most and `min_length` at least, else the refusal `code`.
CREATE FUNCTION review_line(t text, min_length integer, max_length integer, code text)
RETURNS text
LANGUAGE plpgsql IMMUTABLE SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    cleaned text := btrim(regexp_replace(coalesce(t, ''), '\s+', ' ', 'g'));
BEGIN
    IF t IS NULL OR char_length(cleaned) NOT BETWEEN min_length AND max_length
       OR review_unsafe(cleaned) THEN
        PERFORM team_refuse(code);
    END IF;
    RETURN cleaned;
END;
$$;

-- The signed-in user's name, to sign a comment with; their account is locked against its erasure
-- (which locks it first, then the matches: a comment's match is locked after it here too).
CREATE FUNCTION review_author(me uuid) RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    found text;
BEGIN
    SELECT left(coalesce(nullif(btrim(display_name), ''), 'Player'), 64) INTO found
    FROM app_user WHERE id = me AND deleted_at IS NULL
    FOR KEY SHARE;
    IF found IS NULL THEN
        RAISE EXCEPTION 'no signed-in user';
    END IF;
    RETURN found;
END;
$$;

-- ===========================================================================================
-- Comments
-- ===========================================================================================

-- A comment of the signed-in member on the round `r` of the match `m`, at the instant `at_tick`
-- of the round when given; returns its id. 200 comments at most per round and 1,000 per match,
-- per team: the match page reads them all at once.
CREATE FUNCTION add_review_comment(w uuid, m uuid, r integer, at_tick integer, said text)
RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    me uuid := review_caller(w, 'review.comment');
    signed text := review_author(me);
    cleaned text;
    created uuid;
BEGIN
    PERFORM review_round(w, m, r);
    cleaned := review_body(said);
    IF at_tick IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM round
        WHERE match_id = m AND round.round = r AND at_tick BETWEEN start_tick AND end_tick
    ) THEN
        PERFORM team_refuse('tick_invalid');
    END IF;
    IF (SELECT count(*) FROM review_comment
        WHERE workspace_id = w AND match_id = m AND round = r) >= 200
       OR (SELECT count(*) FROM review_comment WHERE workspace_id = w AND match_id = m) >= 1000
    THEN
        PERFORM team_refuse('comment_limit');
    END IF;
    INSERT INTO review_comment (workspace_id, match_id, round, tick, body, author_id, author_name)
    VALUES (w, m, r, at_tick, cleaned, me, signed)
    RETURNING id INTO created;
    RETURN created;
END;
$$;

-- Its author changes a comment's text (and the name it is signed with is refreshed), while they
-- may still comment. Nobody else can, whatever their role.
CREATE FUNCTION edit_review_comment(w uuid, c uuid, said text) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    me uuid := team_caller(w);
    signed text := review_author(me);
    author uuid;
BEGIN
    SELECT author_id INTO author FROM review_comment
    WHERE id = c AND workspace_id = w AND review_readable(w, match_id)
    FOR UPDATE;
    IF NOT FOUND THEN
        PERFORM team_refuse('comment_not_found');
    END IF;
    IF author IS DISTINCT FROM me OR NOT has_permission(w, 'review.comment') THEN
        PERFORM team_refuse('forbidden');
    END IF;
    UPDATE review_comment
    SET body = review_body(said), author_name = signed, edited_at = now()
    WHERE id = c;
END;
$$;

-- Deletes a comment: its author, while they may comment, or a member with `review.manage`.
CREATE FUNCTION delete_review_comment(w uuid, c uuid) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    me uuid := team_caller(w);
    author uuid;
BEGIN
    SELECT author_id INTO author FROM review_comment
    WHERE id = c AND workspace_id = w AND review_readable(w, match_id)
    FOR UPDATE;
    IF NOT FOUND THEN
        PERFORM team_refuse('comment_not_found');
    END IF;
    -- `IS NOT DISTINCT FROM`: an erased author is null, which `=` would let through.
    IF NOT ((author IS NOT DISTINCT FROM me AND has_permission(w, 'review.comment'))
            OR has_permission(w, 'review.manage')) THEN
        PERFORM team_refuse('forbidden');
    END IF;
    DELETE FROM review_comment WHERE id = c;
END;
$$;

-- ===========================================================================================
-- Tags
-- ===========================================================================================

-- The round's tags become `labels` (cleaned, without repeats whatever their case, in the case
-- first written): 10 at most per round, 100 different ones at most in the team.
CREATE FUNCTION set_review_tags(w uuid, m uuid, r integer, labels text[]) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    wanted text[] := '{}';
    given text;
    cleaned text;
BEGIN
    PERFORM review_caller(w, 'review.manage');
    PERFORM review_round(w, m, r);
    FOREACH given IN ARRAY coalesce(labels, '{}') LOOP
        cleaned := review_line(given, 1, 32, 'tag_invalid');
        IF NOT lower(cleaned) = ANY (SELECT lower(x) FROM unnest(wanted) x) THEN
            wanted := wanted || cleaned;
        END IF;
    END LOOP;
    IF cardinality(wanted) > 10 THEN
        PERFORM team_refuse('tag_limit');
    END IF;
    DELETE FROM review_tag WHERE workspace_id = w AND match_id = m AND round = r;
    INSERT INTO review_tag (workspace_id, match_id, round, label)
    SELECT w, m, r, x FROM unnest(wanted) x;
    IF (SELECT count(DISTINCT lower(t.label)) FROM review_tag t WHERE t.workspace_id = w) > 100 THEN
        PERFORM team_refuse('tag_limit');
    END IF;
END;
$$;

-- ===========================================================================================
-- Playlists
-- ===========================================================================================

-- Creates a playlist of the team; returns its id. 50 at most per team.
CREATE FUNCTION create_review_playlist(w uuid, playlist_name text, about text) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    created uuid;
    clean_name text;
    clean_about text;
BEGIN
    PERFORM review_caller(w, 'review.manage');
    clean_name := review_line(playlist_name, 1, 80, 'name_invalid');
    clean_about := review_line(coalesce(about, ''), 0, 280, 'description_invalid');
    IF (SELECT count(*) FROM review_playlist WHERE workspace_id = w) >= 50 THEN
        PERFORM team_refuse('playlist_limit');
    END IF;
    INSERT INTO review_playlist (workspace_id, name, description)
    VALUES (w, clean_name, clean_about)
    RETURNING id INTO created;
    RETURN created;
END;
$$;

-- The playlist `p` of the team `w`, locked, for a member with `review.manage`.
CREATE FUNCTION review_playlist_managed(w uuid, p uuid) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    PERFORM review_caller(w, 'review.manage');
    PERFORM 1 FROM review_playlist WHERE id = p AND workspace_id = w FOR UPDATE;
    IF NOT FOUND THEN
        PERFORM team_refuse('playlist_not_found');
    END IF;
END;
$$;

-- Renames a playlist or changes its description (null: unchanged).
CREATE FUNCTION update_review_playlist(w uuid, p uuid, playlist_name text, about text)
RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    PERFORM review_playlist_managed(w, p);
    IF playlist_name IS NOT NULL THEN
        UPDATE review_playlist SET name = review_line(playlist_name, 1, 80, 'name_invalid')
        WHERE id = p;
    END IF;
    IF about IS NOT NULL THEN
        UPDATE review_playlist
        SET description = review_line(about, 0, 280, 'description_invalid')
        WHERE id = p;
    END IF;
    UPDATE review_playlist SET updated_at = now() WHERE id = p;
END;
$$;

CREATE FUNCTION delete_review_playlist(w uuid, p uuid) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    PERFORM review_playlist_managed(w, p);
    DELETE FROM review_playlist WHERE id = p;
END;
$$;

-- Adds the round `r` of the match `m` at the end of the playlist (nothing when it is in it
-- already). 100 rounds at most per playlist, hidden ones included.
CREATE FUNCTION add_review_playlist_round(w uuid, p uuid, m uuid, r integer) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    PERFORM review_playlist_managed(w, p);
    PERFORM review_round(w, m, r);
    IF EXISTS (SELECT 1 FROM review_playlist_round
               WHERE playlist_id = p AND match_id = m AND round = r) THEN
        RETURN;
    END IF;
    IF (SELECT count(*) FROM review_playlist_round WHERE playlist_id = p) >= 100 THEN
        PERFORM team_refuse('playlist_full');
    END IF;
    INSERT INTO review_playlist_round (playlist_id, workspace_id, match_id, round, seq)
    SELECT p, w, m, r, coalesce(max(seq) + 1, 0)
    FROM review_playlist_round WHERE playlist_id = p;
    UPDATE review_playlist SET updated_at = now() WHERE id = p;
END;
$$;

-- Takes a round the team sees out of the playlist (nothing when it is not in it).
CREATE FUNCTION remove_review_playlist_round(w uuid, p uuid, m uuid, r integer) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    PERFORM review_playlist_managed(w, p);
    DELETE FROM review_playlist_round
    WHERE playlist_id = p AND match_id = m AND round = r AND review_readable(w, m);
    IF FOUND THEN
        UPDATE review_playlist SET updated_at = now() WHERE id = p;
    END IF;
END;
$$;

-- Puts the playlist's rounds in the order of (`matches`[i], `rounds`[i]): exactly the rounds of
-- it the team sees ('order_invalid' otherwise). The hidden ones keep their order, after them.
CREATE FUNCTION order_review_playlist(w uuid, p uuid, matches uuid[], rounds integer[])
RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    n integer := coalesce(cardinality(matches), 0);
BEGIN
    PERFORM review_playlist_managed(w, p);
    IF n <> coalesce(cardinality(rounds), 0) OR EXISTS (
        SELECT 1 FROM unnest(matches, rounds) g(m, r) WHERE g.m IS NULL OR g.r IS NULL
    ) OR n <> (SELECT count(DISTINCT (g.m, g.r)) FROM unnest(matches, rounds) g(m, r))
    OR EXISTS (
        (SELECT g.m, g.r FROM unnest(matches, rounds) g(m, r))
        EXCEPT
        (SELECT match_id, round::integer FROM review_playlist_round
         WHERE playlist_id = p AND review_readable(w, match_id))
    ) OR EXISTS (
        (SELECT match_id, round::integer FROM review_playlist_round
         WHERE playlist_id = p AND review_readable(w, match_id))
        EXCEPT
        (SELECT g.m, g.r FROM unnest(matches, rounds) g(m, r))
    ) THEN
        PERFORM team_refuse('order_invalid');
    END IF;
    UPDATE review_playlist_round pr SET seq = n + h.rank
    FROM (
        SELECT match_id, round,
               row_number() OVER (ORDER BY seq, added_at, match_id, round) AS rank
        FROM review_playlist_round
        WHERE playlist_id = p AND NOT review_readable(w, match_id)
    ) h
    WHERE pr.playlist_id = p AND pr.match_id = h.match_id AND pr.round = h.round;
    UPDATE review_playlist_round pr SET seq = g.ord - 1
    FROM unnest(matches, rounds) WITH ORDINALITY g(m, r, ord)
    WHERE pr.playlist_id = p AND pr.match_id = g.m AND pr.round = g.r;
    UPDATE review_playlist SET updated_at = now() WHERE id = p;
END;
$$;

-- ===========================================================================================
-- What the API may run
-- ===========================================================================================

REVOKE ALL ON FUNCTION
    review_readable(uuid, uuid), review_caller(uuid, text), review_round(uuid, uuid, integer),
    review_unsafe(text), review_body(text), review_line(text, integer, integer, text),
    review_author(uuid),
    add_review_comment(uuid, uuid, integer, integer, text),
    edit_review_comment(uuid, uuid, text), delete_review_comment(uuid, uuid),
    set_review_tags(uuid, uuid, integer, text[]),
    create_review_playlist(uuid, text, text), review_playlist_managed(uuid, uuid),
    update_review_playlist(uuid, uuid, text, text), delete_review_playlist(uuid, uuid),
    add_review_playlist_round(uuid, uuid, uuid, integer),
    remove_review_playlist_round(uuid, uuid, uuid, integer),
    order_review_playlist(uuid, uuid, uuid[], integer[])
    FROM PUBLIC;
-- `review_readable` for the policies, which run as the API role.
GRANT EXECUTE ON FUNCTION
    review_readable(uuid, uuid),
    add_review_comment(uuid, uuid, integer, integer, text),
    edit_review_comment(uuid, uuid, text), delete_review_comment(uuid, uuid),
    set_review_tags(uuid, uuid, integer, text[]),
    create_review_playlist(uuid, text, text),
    update_review_playlist(uuid, uuid, text, text), delete_review_playlist(uuid, uuid),
    add_review_playlist_round(uuid, uuid, uuid, integer),
    remove_review_playlist_round(uuid, uuid, uuid, integer),
    order_review_playlist(uuid, uuid, uuid[], integer[])
    TO untraded_api;
