// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * Metrics the site does not show. HLTV Rating 1.0 and the community approximation of 2.0 are still
 * computed: 1.0 sets the Untraded Rating's scale and serves its validation (docs/winprob.md), but
 * the site rates players with its own rating.
 */
export const HIDDEN_METRICS: ReadonlySet<string> = new Set(["rating.hltv1", "rating.hltv2_approx"]);

/** Whether the site shows this metric. */
export const shown = (id: string): boolean => !HIDDEN_METRICS.has(id);
