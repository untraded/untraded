-- SPDX-FileCopyrightText: 2026 The Untraded Authors
-- SPDX-License-Identifier: AGPL-3.0-only
--
-- References by level: what players of a rating band do, from every player of the collected
-- matches (anonymous aggregates; players who opted out are left out). A session report falls
-- back on them when the player's own 30 days are not enough.

CREATE TABLE level_reference (
    mode           match_mode NOT NULL,
    band_low       integer NOT NULL,       -- the band asked for, e.g. 17500
    band_high      integer NOT NULL,       -- exclusive, e.g. 20000
    used_low       integer NOT NULL,       -- the ratings actually pooled, widened when the band
    used_high      integer NOT NULL,       -- alone has too few matches
    metric_id      text NOT NULL,
    version        text NOT NULL,
    basis          text NOT NULL CHECK (basis IN ('value', 'per_round')),
    value          double precision,
    player_matches integer NOT NULL,       -- (player, match) rows pooled
    players        integer NOT NULL,
    rounds         integer NOT NULL,
    computed_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (mode, band_low, metric_id, version),
    FOREIGN KEY (metric_id, version) REFERENCES metric_definition (metric_id, version)
);
-- Anonymous aggregates: readable by any signed-in user.
GRANT SELECT ON level_reference TO untraded_api;

-- Which reference a session report used: the player's own 30 days, a level, or none.
ALTER TABLE play_session
    ADD COLUMN reference_kind text NOT NULL DEFAULT 'self'
        CHECK (reference_kind IN ('self', 'level', 'none')),
    ADD COLUMN reference_level_low integer,
    ADD COLUMN reference_level_high integer;
