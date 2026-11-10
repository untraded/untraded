// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// Where a value stands among the reference's usual values, for the graduated ruler. Pure (tested
// without a browser).

/**
 * The fewest values a band needs: `reference.min_spread_matches` in `untraded.reference`
 * (`MIN_SPREAD_MATCHES`), which the API does not expose. A percentile of a handful of values is the
 * extreme of a handful of values. The report says it to explain a missing ruler, and the match page
 * computes its own band from the player's previous matches with the same floor: keep it in step
 * with the API.
 */
export const MIN_SPREAD_MATCHES = 10;

/** Which way is an improvement, as the API says it. */
export type Better = "higher" | "lower" | "neutral";

/** 0 below the 10th percentile of "better", 1 below the 30th, 2 below the 70th, 3 below the 90th, 4 above. */
export type Zone = 0 | 1 | 2 | 3 | 4;

export interface Position {
  /** Approximate percentile among the reference's values, from 1 to 99, oriented so that 99 is
   * the best whatever way the metric runs. Rebuilt from three landmarks (10th, median and 90th
   * percentile), not computed from every value. */
  percentile: number;
  zone: Zone;
  /** Where the value sits on the axis, 0 to 100. The axis always runs towards better on the
   * right, so it is reversed when lower is better. */
  at: number;
  /** The median of the reference on the same axis. */
  median: number;
  /** The common values (10th to 90th percentile) on the same axis, `bandFrom` < `bandTo`. */
  bandFrom: number;
  bandTo: number;
}

/** How far the axis runs past the band, in shares of the distance between the band's edge and the median. */
const OVERSHOOT = 0.6;
/** Keeps the axis finite when the median sits on an edge of the band. */
const MIN_TAIL = 0.1;

const clamp = (x: number, low: number, high: number) => Math.min(high, Math.max(low, x));

/**
 * The position of `session` among the reference's values, given their median (`reference`) and
 * their 10th and 90th percentiles. `null` when it cannot be drawn faithfully, and the caller keeps
 * the plain gap bar: a neutral metric (no better way), a missing landmark, a band with no width, a
 * median outside the band, or a value that is not a number. Landmarks given the wrong way round
 * (`p10` > `p90`) are put back in order.
 */
export function position(
  session: number | null | undefined,
  reference: number | null | undefined,
  p10: number | null | undefined,
  p90: number | null | undefined,
  better: Better,
): Position | null {
  if (better === "neutral") return null;
  const values = [session, reference, p10, p90];
  if (!values.every((x): x is number => typeof x === "number" && Number.isFinite(x))) return null;
  const [value, median, a, b] = values as [number, number, number, number];
  const low = Math.min(a, b);
  const high = Math.max(a, b);
  if (!(high > low) || median < low || median > high) return null;

  const left = Math.max(median - low, MIN_TAIL * (high - low));
  const right = Math.max(high - median, MIN_TAIL * (high - low));
  const start = low - OVERSHOOT * left;
  const end = high + OVERSHOOT * right;

  // Piecewise linear through the landmarks: 10 at p10, 50 at the median, 90 at p90.
  // Strictly outside the band first; inside it, a value on the median is always 50, even when the
  // median sits on an edge of the band (many metrics are zero for at least a tenth of players).
  let raw: number;
  if (value < low) raw = Math.max(1, (10 * (value - start)) / (low - start));
  else if (value > high) raw = Math.min(99, 90 + (9 * (value - high)) / (end - high));
  else if (value <= median) raw = median > low ? 10 + (40 * (value - low)) / (median - low) : 50;
  else raw = 50 + (40 * (value - median)) / (high - median);

  const flip = better === "lower";
  const percentile = flip ? 100 - raw : raw;
  const zone: Zone =
    percentile < 10 ? 0 : percentile < 30 ? 1 : percentile < 70 ? 2 : percentile < 90 ? 3 : 4;
  const at = (x: number) => {
    const t = clamp((x - start) / (end - start), 0, 1);
    return (flip ? 1 - t : t) * 100;
  };
  const edges = [at(low), at(high)];
  return {
    percentile: Math.round(percentile),
    zone,
    at: at(value),
    median: at(median),
    bandFrom: Math.min(...edges),
    bandTo: Math.max(...edges),
  };
}

/** The trend a zone reads as: the two lowest are worse, the two highest better. */
export function zoneTrend(zone: Zone): "better" | "worse" | "same" {
  return zone <= 1 ? "worse" : zone >= 3 ? "better" : "same";
}
