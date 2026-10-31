// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// What the match page derives from the API, pure (tested without a browser).

import type { Advice, MatchDetail, MetricValue } from "./api";

/** A round a priority flags in this match, and the moment the 2D viewer opens on. */
export interface FlaggedRound {
  round: number;
  /** The first flagged moment of the round, a few seconds before the event. */
  tick: number;
  /** That moment's event: `tick` is clamped to the demo's start, the event is not. */
  event: number;
  /** How many moments the priority flags in the round. */
  moments: number;
}

/** A priority of the match's session, with the rounds of this match it flags. */
export interface PriorityInMatch {
  advice: Advice;
  rounds: FlaggedRound[];
}

/** The session's priorities that flag rounds of this match, in their order, rounds sorted. */
export function prioritiesIn(advice: Advice[], matchId: string): PriorityInMatch[] {
  const found: PriorityInMatch[] = [];
  for (const item of [...advice].sort((a, b) => a.priority - b.priority)) {
    const byRound = new Map<number, FlaggedRound>();
    for (const event of item.evidence) {
      if (event.match_id !== matchId) continue;
      const known = byRound.get(event.round);
      if (!known)
        byRound.set(event.round, {
          round: event.round,
          tick: event.goto_tick,
          event: event.tick,
          moments: 1,
        });
      else {
        known.moments += 1;
        if (event.goto_tick < known.tick) {
          known.tick = event.goto_tick;
          known.event = event.tick;
        }
      }
    }
    if (byRound.size > 0) {
      found.push({ advice: item, rounds: [...byRound.values()].sort((a, b) => a.round - b.round) });
    }
  }
  return found;
}

export type Side = "CT" | "T";

/** The side the player's team played in a round. */
export function sideOf(match: MatchDetail, round: number): Side | null {
  const found = match.rounds.find((r) => r.round === round);
  if (!found || !match.my_team) return null;
  return found.ct_team === match.my_team ? "CT" : "T";
}

/** Whether the player's team won a round; `null` when unknown. */
export function wonRound(match: MatchDetail, round: number): boolean | null {
  const found = match.rounds.find((r) => r.round === round);
  if (!found || !match.my_team || !found.winner_team) return null;
  return found.winner_team === match.my_team;
}

/** How many rounds the player's team played on each side. */
export function roundsBySide(match: MatchDetail): Record<Side, number> {
  const count = { CT: 0, T: 0 };
  if (!match.my_team) return count;
  for (const round of match.rounds) count[round.ct_team === match.my_team ? "CT" : "T"] += 1;
  return count;
}

/** One metric on each side, `undefined` when the API did not give it. */
export function bySide(
  metrics: MetricValue[],
  id: string,
): { ct: number | null | undefined; t: number | null | undefined } {
  const value = (scope: "ct" | "t") =>
    metrics.find((m) => m.metric_id === id && m.scope === scope)?.value;
  return { ct: value("ct"), t: value("t") };
}

/** Minutes between the start and the end of a match; `null` when unknown. */
export function minutes(start: string | null, end: string | null): number | null {
  if (!start || !end) return null;
  const span = (Date.parse(end) - Date.parse(start)) / 60_000;
  return Number.isFinite(span) && span > 0 ? Math.round(span) : null;
}

/** The 2D viewer on a moment to review: opened at `tick` (before the event), the event at `event`,
 * and the priority's `rule`, which the round's banner names. */
export function momentHref(
  matchId: string,
  round: number,
  moment: { tick: number; event: number; rule: string },
): string {
  const query = `t=${moment.tick}&e=${moment.event}&p=${encodeURIComponent(moment.rule)}`;
  return `/matches/${matchId}/rounds/${round}?${query}`;
}
