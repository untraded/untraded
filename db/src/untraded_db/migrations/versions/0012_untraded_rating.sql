-- SPDX-FileCopyrightText: 2026 The Untraded Authors
-- SPDX-License-Identifier: AGPL-3.0-only
--
-- The Untraded Rating in the wide view of the current values, next to HLTV 1.0: the match page
-- and the lists read their headline numbers from it. A new column goes last (CREATE OR REPLACE
-- VIEW keeps the existing ones), and the view still runs with the reader's rights (0002).

CREATE OR REPLACE VIEW metric_wide_current WITH (security_invoker = true) AS
SELECT v.match_id,
       v.steam_id,
       v.scope,
       max(v.value) FILTER (WHERE v.metric_id = 'base.kills')  AS kills,
       max(v.value) FILTER (WHERE v.metric_id = 'base.deaths') AS deaths,
       max(v.value) FILTER (WHERE v.metric_id = 'base.adr')    AS adr,
       max(v.value) FILTER (WHERE v.metric_id = 'base.kast')   AS kast,
       max(v.value) FILTER (WHERE v.metric_id = 'rating.hltv1') AS hltv1,
       max(v.value) FILTER (WHERE v.metric_id = 'trade.untraded_deaths') AS untraded_deaths,
       max(v.value) FILTER (WHERE v.metric_id = 'rating.untraded') AS untraded
FROM metric_value v
JOIN metric_current c USING (metric_id, version)
WHERE v.params_hash = 'default'
GROUP BY v.match_id, v.steam_id, v.scope;
