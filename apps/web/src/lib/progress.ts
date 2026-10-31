// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// The progress page, the parts that need no server or browser (tested): which sessions a period
// holds, a key figure's series, how much it moved, and the drawing of its curve.

import type { Comparison, SessionSummary } from "./api";

/** The key figures every session summary carries (`headlines`), in the order shown. */
export const KEY_FIGURES = [
  "rating.untraded",
  "base.adr",
  "base.kast",
  "trade.untraded_deaths",
] as const;

export const PERIODS = ["last10", "days30", "days90", "all"] as const;
export type Period = (typeof PERIODS)[number];
export const DEFAULT_PERIOD: Period = "days30";

export function pickPeriod(value: string | undefined): Period {
  return (PERIODS as readonly string[]).includes(value ?? "") ? (value as Period) : DEFAULT_PERIOD;
}

/** How far back a period reaches, in days; `null` when it counts sessions or takes them all. */
export function periodDays(period: Period): number | null {
  return period === "days30" ? 30 : period === "days90" ? 90 : null;
}

/** The sessions of a period, oldest first, from a list given newest first (as the API does). */
export function inPeriod(
  newestFirst: SessionSummary[],
  period: Period,
  now: number,
): SessionSummary[] {
  const days = periodDays(period);
  const kept =
    period === "last10"
      ? newestFirst.slice(0, 10)
      : days === null
        ? newestFirst
        : newestFirst.filter((s) => now - Date.parse(s.started_at) <= days * 86_400_000);
  return [...kept].reverse();
}

export interface Point {
  sessionId: string;
  startedAt: string;
  value: number | null;
  /** `null` when the session had no reference (not enough history). */
  reference: number | null;
}

export interface Series {
  metricId: string;
  unit: string;
  basis: Comparison["basis"];
  better: Comparison["better"];
  points: Point[];
}

/** One key figure across sessions (oldest first); `null` when no session carries it. */
export function series(oldestFirst: SessionSummary[], metricId: string): Series | null {
  let shape: Comparison | undefined;
  const points = oldestFirst.map((session) => {
    const found = session.headlines.find((h) => h.metric_id === metricId);
    shape ??= found;
    return {
      sessionId: session.id,
      startedAt: session.started_at,
      value: found?.session ?? null,
      reference: session.enough ? (found?.reference ?? null) : null,
    };
  });
  if (!shape) return null;
  return { metricId, unit: shape.unit, basis: shape.basis, better: shape.better, points };
}

/**
 * How much a figure moved over the period, oriented (positive = better) in % of its first value:
 * from its first measured session to its last. `null` with fewer than two values.
 */
export function change(points: Point[], better: Comparison["better"]): number | null {
  const measured = points.filter((p) => p.value !== null) as (Point & { value: number })[];
  const first = measured[0];
  const last = measured.at(-1);
  if (!first || !last || measured.length < 2 || first.value === 0 || better === "neutral") {
    return null;
  }
  const moved = ((last.value - first.value) / Math.abs(first.value)) * 100;
  return better === "lower" ? -moved : moved;
}

export interface Geometry {
  width: number;
  height: number;
  /** The player's line, and the reference's (broken where a session had none). */
  line: string;
  referenceLine: string;
  dots: { x: number; y: number }[];
  /** Horizontal guides with their value, and dates under the axis. */
  ticks: { y: number; value: number }[];
  dates: { x: number; index: number }[];
  /** The band of each session, for pointing at it. */
  bands: { x: number; width: number }[];
  plot: { top: number; bottom: number };
}

/** The drawing widths: a wide card, and a narrow one (a phone), so text keeps its size. */
export const WIDE = 520;
export const NARROW = 340;
const H = 210;
const LEFT = 48;
const RIGHT = 12;
const TOP = 10;
const BOTTOM = 26;

/** Where to draw a series: one point per session, three value guides, about six dates. */
export function geometry(points: Point[], W: number = WIDE): Geometry {
  const values = points.flatMap((p) => [p.value, p.reference]).filter((v) => v !== null);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = (max - min) * 0.12 || Math.abs(max) * 0.05 || 1;
  const low = min - pad;
  const high = max + pad;
  const n = points.length;
  const x = (i: number) =>
    n === 1 ? (LEFT + W - RIGHT) / 2 : LEFT + (i * (W - LEFT - RIGHT)) / (n - 1);
  const y = (v: number) => TOP + (H - TOP - BOTTOM) * (1 - (v - low) / (high - low));
  const path = (pick: (p: Point) => number | null) => {
    let out = "";
    let drawing = false;
    points.forEach((p, i) => {
      const v = pick(p);
      if (v === null) {
        drawing = false;
        return;
      }
      out += `${drawing ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)} `;
      drawing = true;
    });
    return out.trim();
  };
  const every = Math.max(1, Math.ceil(n / (W < WIDE ? 4 : 6)));
  const dates: Geometry["dates"] = [];
  points.forEach((_, i) => {
    const last = i === n - 1;
    // Every few sessions, and the last one, unless it would touch the previous date.
    if ((i % every === 0 && (last || n - 1 - i >= every / 2)) || last) {
      dates.push({ x: x(i), index: i });
    }
  });
  const band = n === 1 ? W - LEFT - RIGHT : (W - LEFT - RIGHT) / (n - 1);
  return {
    width: W,
    height: H,
    line: path((p) => p.value),
    referenceLine: path((p) => p.reference),
    dots: points.flatMap((p, i) => (p.value === null ? [] : [{ x: x(i), y: y(p.value) }])),
    ticks: [min, (min + max) / 2, max].map((value) => ({ y: y(value), value })),
    dates,
    bands: points.map((_, i) => ({ x: x(i) - band / 2, width: band })),
    plot: { top: TOP, bottom: H - BOTTOM },
  };
}
