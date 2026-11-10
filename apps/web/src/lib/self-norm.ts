// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// A match against the player's own previous matches, for the top of the match page: five figures,
// each placed among the same figure over the player's last ready matches. Pure (tested without a
// browser).

import type { Locale } from "@/i18n/locale";
import type { MatchSummary } from "./api";
import { number } from "./format";
import { type Better, MIN_SPREAD_MATCHES, type Position, position } from "./position";

/** How many previous matches the match is compared with. */
export const PREVIOUS_MATCHES = 30;

/**
 * A previous match played for fewer rounds (a quick abandon, a match cut short) is left out: its
 * figures, per round above all, mean little. The same floor as the spread of the player's own
 * reference (`MIN_SPREAD_ROUNDS` in `untraded.reference`).
 */
export const MIN_ROUNDS = 10;

/** The five figures, in the order the page shows them. */
export const SELF_METRICS = [
  { id: "untraded", better: "higher" },
  { id: "adr", better: "higher" },
  { id: "kast", better: "higher" },
  { id: "kd", better: "higher" },
  { id: "untraded_deaths", better: "lower" },
] as const satisfies readonly { id: string; better: Better }[];

export type SelfMetric = (typeof SELF_METRICS)[number]["id"];

const finite = (x: number | null | undefined): x is number =>
  typeof x === "number" && Number.isFinite(x);

/**
 * One figure of the player in a match, from the match list's line: the Untraded Rating, ADR,
 * KAST, kills minus deaths, and deaths that went untraded per round played. `null` when the line
 * does not give it.
 */
export function lineValue(match: MatchSummary, id: SelfMetric): number | null {
  const line = match.my_line;
  if (!line) return null;
  switch (id) {
    case "kd":
      return finite(line.kills) && finite(line.deaths) ? line.kills - line.deaths : null;
    case "untraded_deaths": {
      const rounds = match.rounds_played;
      return finite(line.untraded_deaths) && finite(rounds) && rounds > 0
        ? line.untraded_deaths / rounds
        : null;
    }
    default: {
      const value = line[id];
      return finite(value) ? value : null;
    }
  }
}

/**
 * The player's matches played before `target`, newest first, at most `count`: ready, with the
 * player's line, dated, and played for at least `MIN_ROUNDS` rounds. `list` is the match list as
 * the API gives it (newest first, ties broken by the order it was collected in): the matches after
 * `target` in it were played before it. Before `target` is found in the list, the matches with an
 * earlier date are taken. A match seen twice (pages read while the list grows) counts once.
 */
export function previousMatches(
  list: MatchSummary[],
  target: { id: string; played_at: string | null },
  count = PREVIOUS_MATCHES,
): MatchSummary[] {
  const at = list.findIndex((m) => m.id === target.id);
  const played = target.played_at ? Date.parse(target.played_at) : Number.NaN;
  const before =
    at >= 0
      ? list.slice(at + 1)
      : Number.isFinite(played)
        ? list.filter((m) => m.played_at !== null && Date.parse(m.played_at) < played)
        : [];
  // Paged by offset, the list may show a match twice when one is collected meanwhile.
  const seen = new Set<string>();
  return before
    .filter(
      (m) =>
        m.id !== target.id &&
        m.status === "ready" &&
        m.my_line !== null &&
        m.played_at !== null &&
        Number.isFinite(Date.parse(m.played_at)) &&
        finite(m.rounds_played) &&
        m.rounds_played >= MIN_ROUNDS &&
        // Last, so that only a kept copy is remembered.
        !seen.has(m.id) &&
        seen.add(m.id),
    )
    .slice(0, Math.max(0, count));
}

/**
 * The `q` quantile (0 to 1) of values sorted in increasing order, interpolated linearly between
 * the order statistics: numpy's default (`method="linear"`), as `untraded.reference` computes the
 * spread of the player's own reference. `NaN` for no value.
 */
export function quantile(sorted: readonly number[], q: number): number {
  if (sorted.length === 0) return Number.NaN;
  const h = (sorted.length - 1) * Math.min(1, Math.max(0, q));
  const low = Math.floor(h);
  const high = Math.ceil(h);
  const a = sorted[low] as number;
  const b = sorted[high] as number;
  return a + (h - low) * (b - a);
}

/** What the previous matches give for one figure. */
export interface Norm {
  /** How many previous matches have a value. */
  count: number;
  mean: number;
  median: number;
  p10: number;
  p90: number;
}

/** The mean, median and 10th and 90th percentiles of `values`; `null` for none. */
export function norm(values: readonly number[]): Norm | null {
  const kept = values.filter(finite).sort((a, b) => a - b);
  if (kept.length === 0) return null;
  return {
    count: kept.length,
    mean: kept.reduce((sum, x) => sum + x, 0) / kept.length,
    median: quantile(kept, 0.5),
    p10: quantile(kept, 0.1),
    p90: quantile(kept, 0.9),
  };
}

/** Why a figure has no ruler. */
export type NoRuler =
  /** The match has no value for it. */
  | "noValue"
  /** No previous match has a value for it. */
  | "noHistory"
  /** Fewer previous values than `MIN_SPREAD_MATCHES`. */
  | "few"
  /** The previous values do not spread (their 10th and 90th percentiles are equal): no band. */
  | "flat";

export interface SelfRow {
  id: SelfMetric;
  better: Better;
  value: number | null;
  norm: Norm | null;
  /** The match's value minus the mean of the previous ones; `null` without both. */
  gap: number | null;
  /** On the ruler: band = 10th to 90th percentile of the previous values, tick = their median. */
  position: Position | null;
  /** Why `position` is `null`. */
  missing: NoRuler | null;
}

/** The five figures of `match` against the same figures over `previous`. */
export function selfRows(match: MatchSummary, previous: readonly MatchSummary[]): SelfRow[] {
  return SELF_METRICS.map(({ id, better }) => {
    const value = lineValue(match, id);
    const found = norm(previous.map((m) => lineValue(m, id)).filter(finite));
    const gap = value !== null && found ? value - found.mean : null;
    const placed =
      value !== null && found && found.count >= MIN_SPREAD_MATCHES
        ? position(value, found.median, found.p10, found.p90, better)
        : null;
    const missing: NoRuler | null = placed
      ? null
      : value === null
        ? "noValue"
        : !found
          ? "noHistory"
          : found.count < MIN_SPREAD_MATCHES
            ? "few"
            : "flat";
    return { id, better, value, norm: found, gap, position: placed, missing };
  });
}

/**
 * A number with `digits` decimals, always signed (`+`, or the minus sign `−`), unsigned when it
 * rounds to zero.
 */
export function signed(value: number | null, locale: Locale, digits = 0): string {
  if (value === null || !Number.isFinite(value)) return number(value, locale, digits);
  const rounded = Number(value.toFixed(digits));
  const text = number(Math.abs(value), locale, digits);
  return rounded > 0 ? `+${text}` : rounded < 0 ? `−${text}` : text;
}
