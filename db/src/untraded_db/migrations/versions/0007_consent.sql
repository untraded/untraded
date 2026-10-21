-- SPDX-FileCopyrightText: 2026 The Untraded Authors
-- SPDX-License-Identifier: AGPL-3.0-only
--
-- What each player agreed to, and when: one row per agreement, never updated, so the history
-- stays. A player's consent is their latest row. The text itself lives with the operator; a row
-- names its version.

CREATE TABLE consent (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         uuid NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    text_version    text NOT NULL,
    analysis        boolean NOT NULL,      -- collect and analyse the matches (required to use it)
    research_corpus boolean NOT NULL,      -- keep the raw demos in the research corpus
    recorded_at     timestamptz NOT NULL DEFAULT now(),
    recorded_by     text NOT NULL,         -- how it was given, e.g. "collector cli"
    CHECK (analysis OR NOT research_corpus)
);
CREATE INDEX consent_user ON consent (user_id, recorded_at DESC);

CREATE VIEW consent_current WITH (security_invoker = true) AS
SELECT DISTINCT ON (user_id) user_id, text_version, analysis, research_corpus, recorded_at
FROM consent
ORDER BY user_id, recorded_at DESC, id DESC;

ALTER TABLE consent ENABLE ROW LEVEL SECURITY;
CREATE POLICY self ON consent USING (user_id = current_app_user());
GRANT SELECT ON consent, consent_current TO untraded_api;
